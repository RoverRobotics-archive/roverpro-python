import asyncio
from functools import partial, wraps
import inspect
from types import ModuleType
from typing import AsyncGenerator, Awaitable, Callable, Coroutine, Generator, Optional, Type, TypeVar

Args = TypeVar('Args')
S = TypeVar('S')
T = TypeVar('T')


def unasync_asyncgenfunction(f: Callable[[Args], AsyncGenerator], **kwargs) -> Callable[[Args], Generator]:
    @wraps(f)
    def wrapper(*args, **fkwargs):
        yield from unasync_asyncgen(f(*args, **fkwargs), **kwargs)

    return wrapper


def unasync_coroutinefunction(f: Callable[[Args], Coroutine], *, timeout: float = None, **kwargs) -> Callable[[Args], Coroutine]:
    @wraps(f)
    def wrapper(*args, **fkwargs):
        promise = asyncio.wait_for(f(*args, **fkwargs), timeout=timeout)
        return asyncio.get_event_loop().run_until_complete(promise)

    return wrapper


def unasync_awaitable(a: Awaitable[T], *, timeout: float = None, **kwargs) -> T:
    promise = asyncio.wait_for(a, timeout)
    return unasync(asyncio.get_event_loop().run_until_complete(promise))


def unasync_asyncgen(g: AsyncGenerator[S, T], **kwargs) -> Generator[S, T, None]:
    def genfunction():
        send = unasync_coroutinefunction(g.asend, **kwargs)
        throw = unasync_coroutinefunction(g.athrow, **kwargs)
        close = unasync_coroutinefunction(g.aclose, **kwargs)

        value = None
        while True:
            try:
                value = yield send(value)
            except StopAsyncIteration:
                return
            except GeneratorExit:
                close()
            except Exception as e:
                throw(e)

    return genfunction()


def unasync_class(class_: Type, **kwargs):
    new_class = type(f'@unasync({class_.__name__})', (class_,), {})

    async_to_sync_methods = {
        # async iterator methods
        '__aiter__':  '__iter__',
        '__anext__':  '__next__',
        '__await__':  'value',
        # async context manager
        '__aenter__': '__enter__',
        '__aexit__':  '__exit__',
        # coroutine methods
        'asend':      'send',
        'athrow':     'throw',
        'aclose':     'close',
    }

    for (af, sf) in async_to_sync_methods.items():
        if hasattr(new_class, af) and not hasattr(new_class, sf):
            setattr(new_class, sf, unasync(getattr(new_class, af), **kwargs))

    return new_class


def unasync_module(module: ModuleType, **kwargs):
    new_module = ModuleType(f'@unasync({module.__name__})')
    for p in dir(module):
        if p.startswith('_'):
            continue
        wrapped = getattr(module, p)
        try:
            wrapped = unasync(wrapped, **kwargs)
        except UnasyncError:
            pass
        setattr(new_module, p, wrapped)
    return new_module


def unasync_callable(f: Callable, **kwargs):
    @wraps(f)
    def wrapper(*args, **fkwargs):
        result = f(*args, **fkwargs)
        try:
            return unasync(result, **kwargs)
        except UnasyncError:
            return result

    return wrapper


class UnasyncError(NotImplementedError):
    def __str__(self):
        return f'Could not unasync {self.args[0]} of type {type(self.args[0])}. Is it an asynchronous object?'


def unasync(obj=None, *, timeout: Optional[float] = None, **kwargs):
    """Decorator for turning async code into blocking code. This was needed since pytest-asyncio doesn't work well with fixtures"""
    if timeout is not None:
        kwargs['timeout'] = timeout

    if obj is None:
        return partial(unasync, **kwargs)

    if inspect.isclass(obj):
        return unasync_class(obj, **kwargs)

    if inspect.ismodule(obj):
        return unasync_module(obj, **kwargs)

    if inspect.isasyncgenfunction(obj):
        return unasync_asyncgenfunction(obj, **kwargs)

    if inspect.iscoroutinefunction(obj):
        return unasync_coroutinefunction(obj, **kwargs)

    if inspect.isawaitable(obj):
        return unasync_awaitable(obj, **kwargs)

    if inspect.isasyncgen(obj):
        return unasync_asyncgen(obj, **kwargs)

    raise UnasyncError(obj)
