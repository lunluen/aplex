import asyncio
import time

import pytest

from aplex.load_balancers import RoundRobin


POOL_SIZE = 3
max_works_per_worker = 5


@pytest.fixture(params=[RoundRobin])
def executor(request, executor_factory):
    executor = executor_factory(
        pool_size=POOL_SIZE,
        max_works_per_worker=max_works_per_worker,
        load_balancer=request.param)

    yield executor

    executor.shutdown()


async def async_heavy_work():
    await asyncio.sleep(4)


async def async_light_work():
    await asyncio.sleep(1.5)  # Need to be large enough to submit time


class TestLoadbalancing:

    def test_find_available_worker(self, executor):
        for i in range(POOL_SIZE * max_works_per_worker - 1):
            if (i + 1) % POOL_SIZE == 0:
                executor.submit(async_light_work)
            else:
                executor.submit(async_heavy_work)

        future = executor.submit(async_light_work)

        # Wait to ensure the last worker is idle. All the
        # others should be busy.
        future.result()
        executor.submit(async_heavy_work)

        time.sleep(0.5)  # Wait handler thread to handle submit.
        manager = executor._handler_thread._worker_manager
        assert manager._workloads[manager._workers[-1]] == 1
