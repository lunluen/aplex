import asyncio
import multiprocessing
import queue
import sys
import time

import pytest

from aplex.executor import (SubmitItem, HandlerCommands,
                                WorkStates, WorkerStates)
from aplex.process import _ProcessWorker
from aplex.thread import _ThreadWorker


@pytest.fixture(scope='function', params=[
    (_ProcessWorker, multiprocessing.SimpleQueue),
    (_ThreadWorker, queue.Queue),
    ])
def worker(request):
    Worker, ResultQueue = request.param
    worker = Worker(ResultQueue())
    worker.start()

    yield worker

    worker.close()


async def async_work(meta):
    if isinstance(meta, Exception):
        raise meta
    return meta


def sync_work(meta):
    if isinstance(meta, Exception):
        raise meta
    return meta


async def work_to_cancel():
    await asyncio.sleep(999)


class TestReceive:

    @pytest.mark.parametrize(('work_state', 'work_state_meta'), [
        (WorkStates.SUCCESS, 'result'),
        (WorkStates.EXCEPTION, Exception('exc')),
    ])
    @pytest.mark.parametrize('work', [async_work, sync_work])
    def test_receive_work(self, worker, work, work_state, work_state_meta):
        item = SubmitItem.work_form(work=work,
                                    args=(work_state_meta,),
                                    kwargs={},
                                    work_id=666,
                                    load_balancing_meta=None)
        worker.submit(item)
        result_item = worker._result_queue.get()

        assert result_item.work_state == work_state

        if work_state == WorkStates.EXCEPTION:
            returned_meta = result_item.work_state_meta

            # Compare two exceptions.
            assert (type(returned_meta) == type(work_state_meta) and
                    returned_meta.args == work_state_meta.args)
        else:
            assert result_item.work_state_meta == work_state_meta

    @pytest.mark.parametrize(('command', 'command_meta'), [
        (HandlerCommands.CANCEL, 666),
        (HandlerCommands.CLOSE, None),
    ])
    def test_receive_command(self, worker, command, command_meta):
        work_id = 666
        item = SubmitItem.work_form(work=work_to_cancel,
                                    args=(),
                                    kwargs={},
                                    work_id=work_id,
                                    load_balancing_meta=None)
        worker.submit(item)

        item = SubmitItem.command_form(command=command,
                                       command_meta=command_meta)
        worker.submit(item)

        # Close command will also trigger cancellation.
        result_item = worker._result_queue.get()
        assert (result_item.work_id == work_id and
                result_item.work_state == WorkStates.CANCELLED)

        if command == HandlerCommands.CLOSE:
            result_item = worker._result_queue.get()
            assert (result_item.worker_state == WorkerStates.CLOSING and
                    result_item.worker_state_meta == worker.ident)


async def async_raise_base_exc():
    raise BaseException('base_exception')


def sync_raise_base_exc():
    raise BaseException('base_exception')


@pytest.mark.parametrize('work',
                         [async_raise_base_exc, sync_raise_base_exc])
def test_base_exception_raised(worker, work):
    item = SubmitItem.work_form(work=work, args=(), kwargs={},
                                work_id=666, load_balancing_meta=None)
    worker.submit(item)

    item = worker._result_queue.get()
    assert item.worker_state == WorkerStates.ERROR

    time.sleep(2)
    assert not worker.is_alive()


@pytest.mark.parametrize('loop_factory', [
    asyncio.SelectorEventLoop,
    pytest.param('asyncio.ProactorEventLoop',
                 marks=pytest.mark.skipif(sys.platform != 'win32',
                                          reason='Windows only.')),
    pytest.param('uvloop.Loop',
                 marks=pytest.mark.skipif(sys.platform == 'win32',
                                          reason='Not support Windows.')),
])
@pytest.mark.parametrize('worker_factory', [_ProcessWorker, _ThreadWorker])
def test_loop_factory(worker_factory, loop_factory):
    if loop_factory == 'asyncio.ProactorEventLoop':
        loop_factory = asyncio.ProactorEventLoop
    elif loop_factory == 'uvloop.Loop':
        import uvloop
        loop_factory = uvloop.Loop

    if worker_factory == _ProcessWorker:
        q = multiprocessing.SimpleQueue()
    else:
        q = queue.Queue()
    worker = worker_factory(q, loop_factory)

    worker.start()
    time.sleep(3)
    assert worker.is_alive()

    worker.close()
