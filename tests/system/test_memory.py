import asyncio
import gc

import pytest

from aplex import compat
# from memory_profiler import memory_usage


def executor(executor_factory):
    yield executor_factory(pool_size=1)


async def async_work():
    await asyncio.sleep(0.5)


def get_all_tasks():
    if compat.PY37:
        return len(asyncio.tasks.all_tasks())
    else:
        return len(asyncio.Task.all_tasks())


# TODO(Lun): This should be an integration test.
# TODO(Lun): Test cancellation and raising exception.
@pytest.mark.xfail(reasons='This sometimes fails.')
def test_tasks_collected(executor):
    for __ in range(100):
        executor.submit(async_work)

    future = executor.submit(async_work)
    future.result()  # Wait for all works.

    future = executor.submit(gc.collect)
    future.result()  # Wait collections.

    future = executor.submit(get_all_tasks)
    assert future.result() == 0
