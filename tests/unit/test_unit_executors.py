import inspect

import pytest

from aplex.executor import AplexWorkerError
from aplex.futures import AsyncioFuture, ConcurrentFuture


@pytest.fixture(scope='function', autouse=True)
def mock_handler_thread(mocker):
    mocker.patch('aplex.executor._HandlerThread', auto_spec=True)


async def async_work():
    pass


def sync_work():
    pass


class TestSubmit:

    @pytest.mark.parametrize(('awaitable', 'expected'), [
     (True, AsyncioFuture),
     (False, ConcurrentFuture),
    ])
    def test_submit_awaitable(self, executor_factory, awaitable, expected):
        executor = executor_factory(awaitable=awaitable)
        future = executor.submit(sync_work)
        assert isinstance(future, expected)

    @pytest.mark.parametrize('work', [async_work, sync_work])
    def test_submit_future_cancel_interface(self, executor, work):
        concurrent_future = executor.submit(work)

        if inspect.iscoroutinefunction(work):
            assert (concurrent_future._cancel_interface is
                    executor._handler_thread.cancel_work)
        else:
            assert concurrent_future._cancel_interface is None


class TestMap:

    def test_empty_iterable(self, executor):
        assert executor.map(sync_work, ()) == []


class TestShutdown:
    # TODO(Lun): Set test order. Shutdown should be tested
    # first considering shutting down executor fixture.

    def test_shutdown_close_handler(self, executor):
        handler_thread = executor._handler_thread

        executor.shutdown()

        handler_thread.close.assert_called_once_with()

    @pytest.mark.parametrize('wait', [True, False])
    def test_shutdown_wait(self, executor, wait):
        handler_thread = executor._handler_thread

        executor.shutdown(wait=wait)
        if wait:
            handler_thread.join.assert_called_once_with()
        else:
            handler_thread.join.assert_not_called()

    def test_public_methods_after_shutdown(self, executor):
        executor.shutdown(wait=False)

        with pytest.raises(RuntimeError):
            executor.set_future_loop(None)

        with pytest.raises(RuntimeError):
            executor.submit(sync_work)

        with pytest.raises(RuntimeError):
            executor.map(sync_work, 'some iterable')

        executor.shutdown()


class TestWithException:

    @pytest.fixture(autouse=True)
    def executor_with_exc(self, executor):
        executor._exception = AplexWorkerError()
        yield executor

    def test_public_methods_with_exception(self, executor_with_exc):
        with pytest.raises(AplexWorkerError):
            executor_with_exc.set_future_loop(None)

        with pytest.raises(AplexWorkerError):
            executor_with_exc.submit(sync_work)

        with pytest.raises(AplexWorkerError):
            executor_with_exc.map(sync_work, 'some iterable')

        handler_thread = executor_with_exc._handler_thread

        executor_with_exc.shutdown()
        handler_thread.close.assert_not_called()
