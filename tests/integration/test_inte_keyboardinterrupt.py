import multiprocessing
import os
import signal
import time

import pytest

from aplex import ProcessAsyncPoolExecutor, ThreadAsyncPoolExecutor


def sync_work():
    time.sleep(2)


def run(executor_factory):
    executor = executor_factory()
    future = executor.submit(sync_work)
    future.result()


@pytest.mark.xfail(reason='Signal handler does not work in this test '
                          'on Windows. But it works fine out of test.')
@pytest.mark.parametrize('executor_factory', [
    ProcessAsyncPoolExecutor,
    ThreadAsyncPoolExecutor,
])
def test_keyboardinterrupt(executor_factory):
    env_process = multiprocessing.Process(target=run,
                                          args=(executor_factory,))
    env_process.start()
    time.sleep(0.5)  # To ensure setup

    os.kill(env_process.ident, signal.SIGINT)
    env_process.join()
    assert not env_process.is_alive()


def test_not_keyboardinterrupt_worker_process():
    executor = ProcessAsyncPoolExecutor()
    workers = executor._handler_thread._worker_manager._workers

    for worker in workers:
        os.kill(worker.ident, signal.SIGINT)
    time.sleep(1.5)

    alive = (worker.is_alive() for worker in workers)
    assert all(alive)

    executor.shutdown()
