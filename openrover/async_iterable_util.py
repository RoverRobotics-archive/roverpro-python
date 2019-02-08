import trio
from typing import AsyncIterable


async def alist(aiterable: AsyncIterable):
    result = []
    async for d in aiterable:
        result.append(d)
    return result


async def timeout_each(delay: float, aiterable: AsyncIterable):
    assert delay >= 0
    iter = aiterable.__aiter__()
    while True:
        with trio.fail_after(delay):
            yield await  iter.__anext__()


async def limit(limit: int, aiterable: AsyncIterable):
    assert limit >= 0
    iter = aiterable.__aiter__()
    try:
        for i in range(limit):
            yield await iter.__anext__()
    except StopAsyncIteration:
        raise


async def timeout_all(delay: float, aiterable: AsyncIterable):
    assert delay >= 0
    with trio.fail_after(delay):
        async for i in aiterable:
            yield i