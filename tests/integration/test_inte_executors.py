import asyncio
import time
from concurrent.futures import CancelledError

import pytest

from aplex.executor import AplexWorkerError


POOL_SIZE = 2
max_works_per_worker = 3


async def async_work(arg):
    if isinstance(arg, BaseException):
        raise arg
    return arg


def sync_work(arg):
    if isinstance(arg, BaseException):
        raise arg
    return arg


async def async_long_work(arg):
    await asyncio.sleep(1)
    return arg


def sync_long_work(arg):
    time.sleep(0.1)
    return arg


class TestSubmit:

    @pytest.mark.parametrize('work_arg',
                             [666, Exception('666'), BaseException()])
    @pytest.mark.parametrize('work', [async_work, sync_work])
    def test_submit_work(self, executor, work, work_arg):
        future = executor.submit(work, work_arg)

        if isinstance(work_arg, Exception):
            exc = future.exception()
            assert (type(exc) == type(work_arg) and
                    exc.args == work_arg.args)
        elif isinstance(work_arg, BaseException):
            executor._handler_thread.join()

            fut_exc = future.exception()
            executor_exc = executor._exception
            assert (isinstance(executor_exc, AplexWorkerError) and
                    isinstance(fut_exc, CancelledError) and
                    fut_exc.__cause__ is executor_exc)
        else:
            assert future.result() == work_arg

    def test_exceed_max_runnings(self, executor_factory):
        executor = executor_factory(
            pool_size=POOL_SIZE,
            max_works_per_worker=max_works_per_worker)

        futures = []
        for __ in range(2 * POOL_SIZE * max_works_per_worker + 1):
            future = executor.submit(async_long_work, None)
            futures.append(future)

        assert not futures[-1].done()

        futures[-1].result()
        assert all(future.done() for future in futures)


async def async_map_work(arg_1, arg_2, arg_3):
    return (arg_1, arg_2, arg_3)


def sync_map_work(arg_1, arg_2, arg_3):
    return (arg_1, arg_2, arg_3)


class TestMap:

    @pytest.mark.parametrize('awaitable', [True, False])
    @pytest.mark.parametrize('work', [async_map_work, sync_map_work])
    def test_map_return_order(self, executor_factory, work, awaitable):
        executor = executor_factory(
            pool_size=POOL_SIZE,
            max_works_per_worker=max_works_per_worker,
            awaitable=awaitable)

        map_len = 2 * POOL_SIZE * max_works_per_worker + 1
        target = tuple((i, i, i) for i in range(map_len))
        iterables = [range(map_len)] * 3

        map_results = executor.map(work, *iterables, chunksize=2)
        if awaitable:
            results = tuple(self._async_for_consumer(map_results))
        else:
            results = tuple(j for j in map_results)

        assert results == target

    @pytest.mark.parametrize('awaitable', [True, False])
    @pytest.mark.parametrize(('exception', 'expect_error'), [
        (Exception(), Exception),
        (BaseException(), CancelledError),
    ])
    @pytest.mark.parametrize('work', [async_work, sync_work])
    def test_map_work_raise(self, executor_factory,
                            work, exception, expect_error, awaitable):
        executor = executor_factory(
            pool_size=POOL_SIZE,
            max_works_per_worker=max_works_per_worker,
            awaitable=awaitable)

        iterables = [[None] * (POOL_SIZE * max_works_per_worker)]
        iterables[0][max_works_per_worker] = exception
        map_results = executor.map(work, *iterables, chunksize=1)

        with pytest.raises(expect_error):
            if awaitable:
                self._async_for_consumer(map_results)
            else:
                for __ in map_results:
                    ...

        # To avoid shutdown called by pytest fixture right after broken.
        if type(exception) == BaseException:
            executor._handler_thread.join()

    def _async_for_consumer(self, agen_or_aiter):

        async def consume(target):
            results = []

            # Asynchronous comprehensions is not Py3.5 compatible.
            async for result in target:
                results.append(result)
            return results

        loop = asyncio.get_event_loop()
        return loop.run_until_complete(consume(agen_or_aiter))
