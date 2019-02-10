import threading

import pytest

import aplex
from aplex.executor import (_HandlerThread, ResultItem,
                                WorkStates, WorkerStates)
from aplex.futures import ConcurrentFuture


@pytest.fixture(scope='function', autouse=True)
def handler(mocker):
    mocker.patch('aplex.executor.BaseAsyncPoolExecutor', auto_spec=True)
    executor = aplex.executor.BaseAsyncPoolExecutor()

    mocker.patch('aplex.executor.BaseWorkerManager', auto_spec=True)
    BaseWorkerManager = aplex.executor.BaseWorkerManager
    BaseWorkerManager.return_value = BaseWorkerManager  # Mock instantiation.

    handler = _HandlerThread(executor=executor,
                             pool_size=2,
                             max_works_per_worker=3,
                             load_balancer=None,
                             worker_loop_factory=None,
                             WorkerManager=BaseWorkerManager)

    BaseWorkerManager.return_value = None  # Useless now, so break cycle.
    return handler


class TestReceive:

    def test_receive_worker_state_closing(self, handler):
        worker_id = 666
        mock = handler._worker_manager
        mock.wait_return_item.return_value = ResultItem.worker_state_form(
            WorkerStates.CLOSING, worker_id)
        mock.all_workers_closed.return_value = True

        handler._executor_shutdown_called = True  # To pass assertion inside.

        handler.start()
        handler.join()

        mock.remove_closed_worker.assert_called_once_with(worker_id=worker_id)

    def test_receive_worker_state_broken(self, handler):
        mock = handler._worker_manager
        mock.wait_return_item.side_effect = ConnectionAbortedError()

        handler.start()
        handler.join()

        mock.close.assert_called_once_with()

    def test_receive_worker_state_exception(self, handler):
        mock = handler._worker_manager
        mock.wait_return_item.return_value = ResultItem.worker_state_form(
            WorkerStates.ERROR, BaseException())

        handler.start()
        handler.join()

        mock.close.assert_called_once_with()

    @pytest.mark.parametrize('result_item', [
        ResultItem.work_state_form(666, WorkStates.SUCCESS, object()),
        ResultItem.work_state_form(666, WorkStates.CANCELLED, None),
        ResultItem.work_state_form(666, WorkStates.EXCEPTION, Exception()),
    ])
    def test_receive_work_state(self, handler, result_item, mocker):
        future = mocker.Mock()
        
        condition = mocker.MagicMock()
        condition.__enter__.return_value = None
        future._condition = condition

        is_cancelled = result_item.work_state == WorkStates.CANCELLED
        future._cancel_interface_called = is_cancelled

        mocker.patch.dict(handler._running_futures,
                          {result_item.work_id: future})

        trigger_close_item = ResultItem.worker_state_form(
            WorkerStates.BROKEN, None)

        mock = handler._worker_manager
        mock.wait_return_item.side_effect = [result_item,
                                             trigger_close_item]

        handler.start()
        handler.join()

        if result_item.work_state == WorkStates.SUCCESS:
            future.set_result.assert_called_once_with(
                result_item.work_state_meta)
        elif result_item.work_state == WorkStates.CANCELLED:
            future._cancel_running.assert_called_once_with()
        elif result_item.work_state == WorkStates.EXCEPTION:
            future.set_exception.assert_called_once_with(
                result_item.work_state_meta)
        else:
            assert False, 'Should be unreachable here.'
