import asyncio
import inspect

import pytest

from aplex.futures import AsyncioFuture


@pytest.fixture(scope='function', autouse=True)
def mock_handler_thread(mocker):
    mocker.patch('aplex.executor._HandlerThread', auto_spec=True)


async def async_work():
    pass


def sync_work():
    pass


@pytest.fixture(scope='function', params=[True, False])
def future(request, executor_factory):
    executor = executor_factory(awaitable=request.param)

    yield executor.submit(async_work)

    executor.shutdown()


class TestCancel:

    def test_cancel_pending(self, future):
        assert future.cancel()

        if isinstance(future, AsyncioFuture):
            self._call_soon_threadsafe_consumer()

        assert future.cancelled()

    @pytest.mark.parametrize('work', [async_work, sync_work])
    @pytest.mark.parametrize('awaitable', [True, False])
    def test_cancel_running(self, executor_factory, awaitable, work):
        executor = executor_factory(awaitable=awaitable)
        future = executor.submit(work)

        if isinstance(future, AsyncioFuture):
            future._future.set_running_or_notify_cancel()
        else:
            future.set_running_or_notify_cancel()

        if inspect.iscoroutinefunction(work):
            assert future.cancel()
        else:
            assert not future.cancel()

    def test_cancel_cancelled(self, future):
        future.cancel()
        if isinstance(future, AsyncioFuture):
            self._call_soon_threadsafe_consumer()
        assert future.cancelled()

        if isinstance(future, AsyncioFuture):
            assert not future.cancel() and future.cancelled()
        else:
            assert future.cancel() and future.cancelled()

    def test_cancel_finished(self, future):
        if isinstance(future, AsyncioFuture):
            future._future.set_result(...)
            self._call_soon_threadsafe_consumer()
        else:
            future.set_result(...)

        assert future.done() and not future.cancel()

    def _call_soon_threadsafe_consumer(self):
        loop = asyncio.get_event_loop()
        loop.stop()
        loop.run_forever()
