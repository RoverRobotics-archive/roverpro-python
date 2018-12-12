import asyncio
from typing import AsyncIterable


async def alist(aiterable: AsyncIterable):
    result = []
    async for d in aiterable:
        result.append(d)
    return result


async def timeout_each(delay: float, aiterable: AsyncIterable):
    assert delay >= 0
    iter = aiterable.__aiter__()
    try:
        while True:
            item = await asyncio.wait_for(asyncio.create_task(iter.__anext__()), delay)
            yield item
    except asyncio.TimeoutError:
        pass
    except StopAsyncIteration:
        raise


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
    iter = aiterable.__aiter__()
    sleep_task = asyncio.create_task(asyncio.sleep(delay))
    while True:
        next_task = asyncio.create_task(iter.__anext__())
        try:
            await asyncio.wait([sleep_task, next_task], return_when=asyncio.FIRST_COMPLETED)
            if next_task.done():
                yield next_task.result()
            if sleep_task.done():
                raise StopAsyncIteration
        except StopAsyncIteration:
            sleep_task.cancel()
            next_task.cancel()
            raise
        except Exception as e:
            pass
            raise
