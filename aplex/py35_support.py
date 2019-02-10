"""A lazy imported module for Python3.5 support.

If statement with variable condition can not prevent Python3.5
from compiling function to bytecode, causing syntax error::

    Python3.5 does not support async generator.

"""
import asyncio
import time
from typing import AsyncGenerator, List

from .futures import AsyncioFuture


async def _map_async_gen(self,
                         futures: List[AsyncioFuture],
                         end_time=None) -> AsyncGenerator:
    """The async generator that ``map`` return when ``awaitable`` is True
    for Python3.6 and above.
    """
    try:
        while futures:
            future = futures.pop(0)
            if end_time is not None:
                results = await asyncio.wait_for(
                    future, end_time - time.time(), loop=self._loop)
            else:
                results = await future
            # According to PEP525, `yield from` can not be used in
            # an async generator, making things complicate here.
            for result in results:
                yield result
    # Finally clause for generator exit and timeout.
    finally:
        future.cancel()  # This future may have been done.
        for future in futures:
            future.cancel()
