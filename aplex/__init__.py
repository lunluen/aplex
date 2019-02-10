"""Run your coroutines and functions in child processes or threads like
the way using concurrnet.futures.

Users can prosess works concurrently and in parallel.

Example:

    Below is a example sending http request using aplex with the helps
    of aiohttp and uvloop::

        import aiohttp
        import uvloop
        from aplex import ProcessAsyncPoolExecutor

        async def demo(url):
            async with aiohttp.request('GET', url) as response:
                return response.status

        if __name__ == '__main__':
            pool = ProcessAsyncPoolExecutor(pool_size=8,
                                            worker_loop_factory=uvloop.Loop)
            future = pool.submit(demo, 'http://httpbin.org')
            print('Status: %d.' % future.result())

    The result will be::

        Status: 200

    **Note**: If you are running python on windows,
    ``if __name__ == '__main__':`` is necessary. That's the design of
    multiprocessing.

"""
from.__version__ import __version__
from .futures import AsyncioFuture, ConcurrentFuture
from .load_balancers import LoadBalancer
from .process import ProcessAsyncPoolExecutor
from .thread import ThreadAsyncPoolExecutor
