import asyncio
from functools import wraps, partial
import inspect
import itertools
from typing import AsyncGenerator, Callable, Generator, TypeVar, Coroutine, Awaitable, Union

Args = TypeVar('Args')
S = TypeVar('S')
T = TypeVar('T')


def unasync_asyncgenfunction(f: Callable[[Args], AsyncGenerator], *, item_timeout: float = None) -> Callable[[Args], Generator]:
    @wraps(f)
    def wrapper(*args, **kwargs):
        yield from unasync_asyncgen(f(*args, **kwargs))

    return wrapper


def unasync_coroutinefunction(f: Callable[[Args], Coroutine], *, timeout: float = None) -> Callable[[Args], Coroutine]:
    @wraps(f)
    def wrapper(*args, **kwargs):
        promise = asyncio.wait_for(f(*args, **kwargs), timeout=timeout)
        return asyncio.get_event_loop().run_until_complete(promise)

    return wrapper


def unasync_awaitable(a: Awaitable[T], *, timeout: float = None) -> T:
    promise = asyncio.wait_for(a, timeout)
    return unasync(asyncio.get_event_loop().run_until_complete(promise))


def unasync_asyncgen(g: AsyncGenerator[S, T], *, timeout: float = None) -> Generator[S, T, None]:
    def genfunction():
        send = unasync_coroutinefunction(g.asend)
        throw = unasync_coroutinefunction(g.athrow)
        close = unasync_coroutinefunction(g.aclose)

        value = None
        while True:
            try:
                value = yield send(value)
            except StopAsyncIteration as e:
                return
            except GeneratorExit:
                close()
            except Exception as e:
                throw(e)

    return genfunction()


def unasync(obj=None, **kwargs):
    """Decorator for turning async code into blocking code. This was needed since pytest-asyncio doesn't work well with fixtures"""
    if obj is None:
        return partial(unasync, **kwargs)

    timeout = kwargs.get('timeout', None)

    """Decorator to turn an asynchronous value/function/generator into a synchronous one."""
    if inspect.isasyncgenfunction(obj):
        return unasync_asyncgenfunction(obj, item_timeout=timeout)

    if inspect.iscoroutinefunction(obj):
        return unasync_coroutinefunction(obj)

    if inspect.isawaitable(obj):
        return unasync_awaitable(obj)

    if inspect.isasyncgen(obj):
        return unasync_asyncgen(obj)

    raise Exception(f'Could not unasync {obj}:{type(obj)}')
