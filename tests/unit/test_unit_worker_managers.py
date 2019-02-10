import itertools
import threading
import time

import pytest

import aplex
from aplex.executor import SubmitItem
from aplex.futures import ConcurrentFuture
from aplex.process import _ProcessWorkerManager
from aplex.thread import _ThreadWorkerManager


POOL_SIZE = 2


@pytest.fixture(scope='function',
                params=[_ProcessWorkerManager, _ThreadWorkerManager])
def manager(request, mocker):
    Manager = request.param
    Worker = Manager._Worker
    mocker.patch.object(Manager, '_Worker', auto_spec=True)
    Manager._Worker.side_effect = lambda x, y: mocker.Mock(spec=Worker)

    mocker.patch('aplex.load_balancers.RoundRobin', auto_spec=True)
    RoundRobin = aplex.load_balancers.RoundRobin

    manager = Manager(pool_size=POOL_SIZE,
                      max_works_per_worker=3,
                      load_balancer=RoundRobin,
                      worker_loop_factory=None)
    # Patch againg due to instantiation.
    manager._load_balancer = RoundRobin  # It's a mock here.
    RoundRobin.get_proper_worker.side_effect = itertools.cycle(
        manager._workers)

    yield manager

    manager.close()


def empty_func():
    pass


def test_calculate_loadings(manager):
    # Choose pool size = 2.
    assert (manager._workloads[manager._workers[0]] == 0 and
            manager._workloads[manager._workers[1]] == 0)

    futures = []
    for i in range(5):
        item = SubmitItem.work_form(work=empty_func,
                                    args=(),
                                    kwargs={},
                                    work_id=i,
                                    load_balancing_meta=None)
        future = ConcurrentFuture(cancel_interface=None)
        futures.append(future)
        manager.submit(item, future, load_balancing_meta=None)

    assert (manager._workloads[manager._workers[0]] == 3 and
            manager._workloads[manager._workers[1]] == 2)

    for future in futures:
        future.set_result(None)

    assert (manager._workloads[manager._workers[0]] == 0 and
            manager._workloads[manager._workers[1]] == 0)


# _ProcessWorkerManager only.
def test_detect_broken():
    load_balancer = aplex.load_balancers.RoundRobin
    manager = _ProcessWorkerManager(pool_size=POOL_SIZE,
                                    max_works_per_worker=3,
                                    load_balancer=load_balancer,
                                    worker_loop_factory=None)

    def terminate_worker():
        time.sleep(1)
        manager._workers[1].terminate()

    t = threading.Thread(target=terminate_worker)
    t.start()

    with pytest.raises(ConnectionAbortedError):
        manager.wait_return_item()

    t.join()
    manager.close()
