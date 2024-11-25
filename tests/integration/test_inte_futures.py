import asyncio
import inspect
import time
from concurrent.futures import CancelledError

import pytest


async def async_long_work():
    await asyncio.sleep(2)


def sync_long_work():
    time.sleep(2)


@pytest.fixture(scope='function', params=[True, False])
def future(request, executor_factory):
    executor = executor_factory(awaitable=request.param)

    yield executor.submit(async_long_work)

    executor.shutdown()


class TestCancel:

    @pytest.mark.parametrize('work', [async_long_work, sync_long_work])
    @pytest.mark.parametrize('awaitable', [True, False])
    def test_cancel_running(self, executor_factory, awaitable, work):
        executor = executor_factory(awaitable=awaitable)
        future = executor.submit(work)

        concurrent_fut = future._future if awaitable else future
        while not concurrent_fut.running():
            time.sleep(0.1)
        assert not future.done()

        if inspect.iscoroutinefunction(work):
            assert future.cancel()

            with pytest.raises(CancelledError):
                print(concurrent_fut.result())

            if awaitable:
                self._call_soon_threadsafe_consumer()

            assert future.cancelled()
        else:
            assert not future.cancel()

            concurrent_fut.result()

            if awaitable:
                self._call_soon_threadsafe_consumer()

            future.result()  # Will raise if test fail.
            assert True

    def _call_soon_threadsafe_consumer(self):
        loop = asyncio.get_event_loop()
        loop.stop()
        loop.run_forever()
