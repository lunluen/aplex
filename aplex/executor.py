"""Contains executor implementation for aplex."""

import asyncio
import atexit
import concurrent.futures
import enum
import inspect
import itertools
import os
import queue
import signal
import threading
import time
import warnings
import weakref
from typing import (Any, AsyncIterator, Callable, Dict, Generator,
                    Iterable, List, Optional, Set, Tuple, Union)

from . import compat
from .futures import ConcurrentFuture, AsyncioFuture
from .load_balancers import LoadBalancer, RoundRobin
if compat.PY36:
    from typing import AsyncGenerator


DEFAULT_POOL_SIZE = os.cpu_count() or 2  # os.cpu_count() may return None.
DEFAULT_MAX_WORKS_PER_WORKER = 300

# XXX(Lun): Let users choose whether to shut down if broken or exception
# happens in worker? Below are both true for now.
# SHUTDOWN_IF_BROKEN = False
# SHUTDOWN_IF_EXCEPTION = False

_executor_track_set_lock = threading.Lock()
_executor_track_set = weakref.WeakSet()  # type: Set[BaseAsyncPoolExecutor]


class AplexWorkerError(OSError):
    """The executor are broken or an BaseException raised."""


class HandlerCommands(enum.Enum):
    """Commands sent from handler to workers."""

    CANCEL = 'Cancel'
    CLOSE = 'Close'


class WorkStates(enum.Enum):
    """States of work in workers."""

    SUCCESS = 'Success'
    CANCELLED = 'Cancelled'
    EXCEPTION = 'Exception'


class WorkerStates(enum.Enum):
    """States of workers."""

    BROKEN = 'Broken'  # For worker closed due to unknown reason.
    ERROR = 'Error'  # For BaseException raised in worker.
    CLOSING = 'Closing'


class SubmitForms(enum.Enum):
    """Forms of submit items."""

    WORK = 'Work'
    COMMAND = 'Command'


class ResultForms(enum.Enum):
    """Forms of result items."""

    WORK_STATE = 'Work state'
    WORKER_STATE = 'Worker state'


class SubmitItem(object):
    """Object sent from executor to workers"""

    __slots__ = (['form'] +
                 ['work', 'args', 'kwargs',
                  'work_id', 'load_balancing_meta'] +
                 ['command', 'command_meta'])

    @classmethod
    def work_form(cls,
                  work: Callable,
                  args: Tuple[Any],
                  kwargs: Dict[str, Any],
                  work_id: int,
                  load_balancing_meta: Optional[Any] = None
                  ) -> 'SubmitItem':
        """Generates a submit item in work form."""

        item = cls.__new__(cls)
        item.form = SubmitForms.WORK

        item.work = work  # Named "work" to differentiate from asyncio task.
        item.args = args
        item.kwargs = kwargs
        item.work_id = work_id
        item.load_balancing_meta = load_balancing_meta
        return item

    @classmethod
    def command_form(cls,
                     command: HandlerCommands,
                     command_meta: Optional[Any] = None
                     ) -> 'SubmitItem':
        """Generates a submit item in command form."""

        item = cls.__new__(cls)
        item.form = SubmitForms.COMMAND

        item.command = command
        item.command_meta = command_meta
        return item


class ResultItem(object):
    """Object received from workers."""

    __slots__ = (['form'] +
                 ['work_id', 'work_state', 'work_state_meta'] +
                 ['worker_state', 'worker_state_meta'])

    @classmethod
    def work_state_form(cls,
                        work_id: int,
                        work_state: WorkStates,
                        work_state_meta: Optional[Any] = None,
                        ) -> 'ResultItem':
        """Generates a result item in work state form."""

        item = cls.__new__(cls)
        item.form = ResultForms.WORK_STATE

        item.work_id = work_id
        item.work_state = work_state
        item.work_state_meta = work_state_meta
        return item

    @classmethod
    def worker_state_form(cls,
                          worker_state: WorkerStates,
                          worker_state_meta: Optional[Any] = None
                          ) -> 'ResultItem':
        """Generates a result item in worker state form."""

        item = cls.__new__(cls)
        item.form = ResultForms.WORKER_STATE

        item.worker_state = worker_state
        item.worker_state_meta = worker_state_meta
        return item


class BaseWorkerMixin(object):
    """Implementation of worker.
    
    This is a mixin for threading.Thread and multiprocessing.Process.
    """
    _submit_queue = None

    def __init__(self, result_queue, loop_factory=None):
        super().__init__()

        self._result_queue = result_queue
        self._loop_factory = loop_factory

    def submit(self, item: SubmitItem):
        self._submit_queue.put(item)

    def cancel_work_by_id(self, work_id):
        self._submit_queue.put(
            SubmitItem.command_form(HandlerCommands.CANCEL,
                                    command_meta=work_id))

    def close(self):
        """"""
        self._submit_queue.put(
            SubmitItem.command_form(HandlerCommands.CLOSE, None))

    def clear(self):
        self._submit_queue = None
        self._result_queue = None

    def run(self):
        """Target for threading.Thread and multiprocessing.Process."""

        # Subtasks generated in corouines are not included to prevent
        # from cancel a task twice. Users have to handle CancelledError
        # properly to cancel their subtasks.
        running_tasks = {}

        def cancel(work_id):
            # Although not creating task for callables that are not
            # a coroutine function, The work id here must map to
            # a task, since only this type of work is allowed
            # to call cancel interface.
            try:
                running_tasks[work_id].cancel()
            except KeyError:
                pass  # Task has been done and popped.

        def run_uncancellable(uncancellable, args, kwargs, work_id):
            """Runs uncancellable, i.e., works that are not coroutine
            functions.
            """
            try:
                result = uncancellable(*args, **kwargs)
            except Exception as e:
                item = ResultItem.work_state_form(work_id,
                                                  WorkStates.EXCEPTION,
                                                  self._make_picklable(e))
            else:
                item = ResultItem.work_state_form(work_id,
                                                  WorkStates.SUCCESS,
                                                  result)
            self._send_result_back(work_id, item)

        def task_done_callback(task):
            work_id = task.work_id
            running_tasks.pop(work_id)

            if task.cancelled():
                item = ResultItem.work_state_form(work_id,
                                                  WorkStates.CANCELLED,
                                                  None)
            else:
                exception = task.exception()
                if exception is not None:
                    exception = self._make_picklable(exception)
                    item = ResultItem.work_state_form(work_id,
                                                      WorkStates.EXCEPTION,
                                                      exception)
                else:
                    item = ResultItem.work_state_form(work_id,
                                                      WorkStates.SUCCESS,
                                                      task.result())
            self._send_result_back(work_id, item)

        def run_coroutine(coro_function, args, kwargs, work_id):
            """Creates a task of the coroutine generated from 
            coroutine function work.
            """
            task = loop.create_task(coro_function(*args, **kwargs))
            task.work_id = work_id
            running_tasks[work_id] = task
            task.add_done_callback(task_done_callback)

        # TODO(Lun): Wrap this with try-except to catch
        # unexpected exception and than close worker.
        def handle_submit_queue(loop):
            """Target for the thread handling submit queue."""
            while True:
                item = self._submit_queue.get()

                # Prevents from doing anything after a BaseException raises.
                if item is None:
                    return

                if item.form == SubmitForms.COMMAND:
                    # XXX(Lun): Use dict as switch in C if too many cases.
                    if item.command == HandlerCommands.CLOSE:
                        loop.call_soon_threadsafe(loop.stop)
                        return
                    elif item.command == HandlerCommands.CANCEL:
                        work_id = item.command_meta
                        loop.call_soon_threadsafe(cancel, work_id)
                        continue
                    assert False, 'Should be unreachable here.'

                if not inspect.iscoroutinefunction(item.work):
                    # Not create future for a callable that is not a
                    # coroutine function since it can not be cancelled.
                    loop.call_soon_threadsafe(
                        run_uncancellable,
                        item.work, item.args, item.kwargs, item.work_id)
                else:
                    loop.call_soon_threadsafe(
                        run_coroutine,
                        item.work, item.args, item.kwargs, item.work_id)

        def cancel_tasks(*tasks):
            if not tasks:
                return
            for task in tasks:
                task.cancel()
            loop.run_until_complete(
                asyncio.gather(*tasks, return_exceptions=True))

        try:
            if self._loop_factory is None:
                loop = asyncio.new_event_loop()
            else:
                loop = self._loop_factory()
            asyncio.set_event_loop(loop)

            handle_submit_thread = threading.Thread(
                target=handle_submit_queue, args=(loop,), daemon=True)
            handle_submit_thread.start()

            loop.run_forever()
        except BaseException as e:
            # Close handle submit thread so that any command from
            # handler is not allowed.
            self._submit_queue.put(None)  # Close handle submit thread.

            self._result_queue.put(
                ResultItem.worker_state_form(WorkerStates.ERROR,
                                             self._make_picklable(e)))
        finally:
            try:
                cancel_tasks(*running_tasks.values())

                # Cancels tasks the user forgot to handle when
                # asyncio.CancelledError is raised.
                if compat.PY37:
                    # Must pass loop for get_running_loop().
                    orphan_tasks = asyncio.tasks.all_tasks(loop)
                else:
                    orphan_tasks = asyncio.Task.all_tasks()
                cancel_tasks(*orphan_tasks)

                if compat.PY36:
                    loop.run_until_complete(loop.shutdown_asyncgens())

                    # Run scheduled callbacks.
                    loop.call_soon(loop.stop)
                    loop.run_forever()

                # Should report only when close command is received and
                # cancellation succeeds. See annotation in below except
                # BaseException clause.
                self._result_queue.put(
                    ResultItem.worker_state_form(WorkerStates.CLOSING,
                                                 self.ident))
            except BaseException as e:
                # Cancellation fails with new BaseException when closing
                # or fails due to previous BaseException. See details in
                # asyncio.Task._wakeup. The previous BaseException would
                # raised again due to `future.result()``.

                self._result_queue.put(
                    ResultItem.worker_state_form(WorkerStates.ERROR,
                                                 self._make_picklable(e)))
            finally:
                loop.close()

    def _send_result_back(self, work_id, item):
        try:
            self._result_queue.put(item)
        except TypeError as e:
            # Item unpicklable.
            item = ResultItem.work_state_form(work_id,
                                              WorkStates.EXCEPTION,
                                              self._make_picklable(e))
            self._result_queue.put(item)

    def _make_picklable(self, stuff):
        """Makes some stuff picklable or not loss information when pickling.

        This should be overwritten by ProcessWorker subclass.
        """
        return stuff


class BaseWorkerManager(object):
    """A manager of worker, or in other words, a broker."""

    # All workers of a executor share a common result queue.
    _result_queue = None
    _Worker = None

    def __init__(self,
                 pool_size,
                 max_works_per_worker,
                 load_balancer,
                 worker_loop_factory):
        self._workers = []
        for __ in range(pool_size):
            worker = self._Worker(self._result_queue, worker_loop_factory)
            worker.start()
            self._workers.append(worker)

        self._work_owner = {}  # To find worker with work_id.
        # Dict for load balancing, shared with self._load_balancer.
        self._workloads = dict.fromkeys(self._workers, 0)

        self._load_balancer = load_balancer(self._workers,
                                            self._workloads,
                                            max_works_per_worker)

    def submit(self, item: SubmitItem, future, load_balancing_meta):
        work_id = item.work_id
        worker = self._load_balancer.get_proper_worker(load_balancing_meta)

        # Caculates workload here.
        self._work_owner[work_id] = worker
        self._workloads[worker] += 1

        def work_done_callback(done_future):
            worker = self._work_owner.pop(work_id)
            self._workloads[worker] -= 1

        future.add_done_callback(work_done_callback)
        worker.submit(item)

    def cancel_work(self, future: ConcurrentFuture):
        work_id = id(future)

        worker = self._work_owner[work_id]
        worker.cancel_work_by_id(work_id)

    def wait_return_item(self) -> ResultItem:
        """Waits for workers until result item is returned
        
        Returns:
            Result item from some worker.
        
        Raises:
            ConnectionAbortedError: If some workers are broken.
        """
        raise NotImplementedError()

    def remove_closed_worker(self, worker_id):
        for worker in self._workers:
            if worker.ident == worker_id:
                target = worker
                break
        assert self._workloads[target] == 0

        target.clear()
        self._workers.remove(target)
        del self._workloads[target]

        return target  # For subclass' super(). No need to find it again.

    def are_all_workers_closed(self):
        return False if self._workers else True

    def wakeup(self):
        """To wake up form wait_return_item method."""
        self._result_queue.put(None)

    def close(self):
        for worker in self._workers:
            worker.close()

    def join(self):
        # XXX(Lun): Join removed worker?
        for worker in self._workers:
            worker.join()

    def clear(self):
        self._result_queue = None
        for worker in self._workers:
            worker.clear()
        self._workers.clear()
        self._workloads.clear()


class _HandlerThread(threading.Thread):
    """Handler of executor."""

    def __init__(self, executor, pool_size, max_works_per_worker,
                 load_balancer, worker_loop_factory,
                 WorkerManager):
        super().__init__()

        self._queue = queue.Queue()
        self._executor = weakref.ref(executor)

        self._running_futures = {}
        self._max_runnings = pool_size * max_works_per_worker

        self._worker_manager = WorkerManager(pool_size,
                                             max_works_per_worker,
                                             load_balancer,
                                             worker_loop_factory)

        self._executor_shutdown_called = False
        self._close_lock = threading.Lock()

    def submit(self, item: Tuple[SubmitItem, ConcurrentFuture, Any]):
        self._queue.put(item)

        # To wake up from wait_return_item in self.run().
        self._worker_manager.wakeup()

    def cancel_work(self, future: ConcurrentFuture):
        """An interface set in future to cancel work."""
        self._worker_manager.cancel_work(future)

    def close(self):
        with self._close_lock:
            self._executor_shutdown_called = True
            self._worker_manager.close()

    def run(self):
        try:
            self._run()
        except AplexWorkerError:
            pass  # TODO(Lun): logger.error
        except BaseException:
            # Close workers if some bug happens.
            self._worker_manager.close()
            raise
        else:
            self._worker_manager.join()
        finally:
            self._clear()

    def _run(self):
        while True:
            with self._close_lock:
                if not self._executor_shutdown_called:
                    self._transfer_to_worker_manager()

            try:
                # Blocks here until some result is returned or
                # some worker is terminated.
                item = self._worker_manager.wait_return_item()
            except ConnectionAbortedError as e:
                item = ResultItem.worker_state_form(WorkerStates.BROKEN, e)

            if item is None:
                # Just a wakeup sentinel from wait_return_item to take a
                # new work submitted by the user.
                continue

            # Handles worker state information.

            if item.form == ResultForms.WORKER_STATE:
                self._handle_worker_state(item.worker_state,
                                          item.worker_state_meta)
                if self._worker_manager.are_all_workers_closed():
                    break
                else:
                    continue

            # Handles received result from finished or cancelled work.

            future = self._running_futures.pop(item.work_id)
            state = item.work_state

            # A condition to avoid cancelling by the user.
            with future._condition:
                if state == WorkStates.CANCELLED:
                    future._cancel_running()
                elif future._cancel_interface_called:
                    exc = concurrent.futures.CancelledError(
                        'Work was done before cancellation function '
                        'is scheduled.')
                    future.set_exception(exc)
                elif state == WorkStates.SUCCESS:
                    future.set_result(item.work_state_meta)
                elif state == WorkStates.EXCEPTION:
                    # concurrent.futures.asyncio.CancelledError and
                    # asyncio.CancelledError are included here.
                    future.set_exception(item.work_state_meta)
                else:
                    assert False, 'Should be unreachable here.'

    def _transfer_to_worker_manager(self):
        """Sends received work to worker manager, i.e., broker."""

        while True:
            # All workers reach the limit of max works per worker.
            if len(self._running_futures) >= self._max_runnings:
                return

            try:
                item = self._queue.get(block=False)
            except queue.Empty:
                return
            else:
                submit_item, future, load_balancing_meta = item
                if future.set_running_or_notify_cancel():
                    self._running_futures[submit_item.work_id] = future
                    self._worker_manager.submit(
                        submit_item, future, load_balancing_meta)

    def _handle_worker_state(self,
                             state: WorkerStates,
                             state_meta: Optional[BaseException]):
        if state == WorkerStates.CLOSING:
            # This will happen only if executor shutdown is called by users.
            assert self._executor_shutdown_called

            # Removes this worker from listening list and clear pending
            # works. All the remaining running works will be cancelled by
            # the other alive workers.

            # Make sure removal is after closing.
            with self._close_lock:
                # This will not cause bugs since submit are not
                # allowed after closing.
                self._worker_manager.remove_closed_worker(
                    worker_id=state_meta)

            # Putting to queue is not allowed after executor.shutdown.
            # Thus no thread-safty issue. Just use deque.
            for __, pending_future, __ in self._queue.queue:
                pending_future.cancel()
                pending_future.set_running_or_notify_cancel()
            self._queue.queue.clear()

        elif state in (WorkerStates.BROKEN, WorkerStates.ERROR):
            # Worker not closed correctly. Work raised
            # BaseException or some worker was terminated abruptly.

            # TODO(Lun): Add worker type information in the reasons.

            # Sets exception reason to executor.
            if state == WorkerStates.BROKEN:
                worker_error = AplexWorkerError(
                    'Aplex worker was terminated abruptly.')
            elif state == WorkerStates.ERROR:
                worker_error = AplexWorkerError(
                    'Aplex worker was terminated since the event '
                    'loop has crashed due to raised BaseException.')
            worker_error.__cause__ = state_meta

            executor = self._executor()
            if executor is not None:
                with executor._lock:
                    executor._exception = worker_error
                executor = None

            # Sets exception reason to undone futures.
            future_error = concurrent.futures.CancelledError()
            future_error.__cause__ = worker_error
            for __, pending_future, in self._queue.queue:
                pending_future.set_exception(future_error)
            for running_future in self._running_futures.values():
                running_future.set_exception(future_error)

            self._worker_manager.close()  # Closes all related workers.

            raise worker_error  # Forces handler thread to terminate.

    def _clear(self):
        self._queue.queue.clear()  # I.e., deque.clear().
        self._running_futures.clear()

        self._worker_manager.join()
        self._worker_manager.clear()


# It's needed to define these here since a local object is not pickable.
async def _handle_chunk_async(work, chunk: Iterable[Iterable]) -> List:
    return await asyncio.gather(*(work(*args) for args in chunk),
                                return_exceptions=False)


def _handle_chunk(work, chunk: Iterable[Iterable]) -> List:
    return [work(*args) for args in chunk]


class BaseAsyncPoolExecutor(object):
    """Executor implementation."""

    _WorkerManager = None

    def __init__(self, *,
                 pool_size: Optional[int] = DEFAULT_POOL_SIZE,
                 max_works_per_worker:
                     Optional[int] = DEFAULT_MAX_WORKS_PER_WORKER,
                 load_balancer: Optional[LoadBalancer] = RoundRobin,
                 awaitable: Optional[bool] = False,
                 future_loop: asyncio.AbstractEventLoop = None,
                 worker_loop_factory:
                     Optional[asyncio.AbstractEventLoop] = None):
        """Setups executor and adds self to executor track set.

        Args:
            pool_size: Number of workers, i.e., number of threads or processes.
            max_works_per_worker: The max number of works a worker can run at
                the same time. This does not **limit** the number of asyncio
                tasks of a worker.
            load_balancer: A subclass of aplex.LoadBalancer for submitted
                item load balancing that has implemented abstract method
                ``get_proper_worker``.
            awaitable: If it's set to True, futures returned from ``submit``
                method will be awaitable, and ``map`` will return async
                generator(async iterator if python3.5).
            future_loop: Loop instance set in awaitable futures returned from
                ``submit`` method.

                If specified, ``awaitable`` must be set to true.

                This loop can also be set in ``set_future_loop`` method.
            worker_loop_factory: A factory to generate loop instance for
                workers to run their job.

        Raises:
            ValueError:
                ``future_loop`` is specified while ``awaitable`` is False.

        """
        if future_loop and not awaitable:
            raise ValueError('Awaitable should be set to True if '
                             'future_loop is specified.')

        with _executor_track_set_lock:
            _executor_track_set.add(self)

        self._awaitable = awaitable
        self._loop = future_loop

        self._closed = False
        self._exception = None
        self._lock = threading.Lock()

        self._handler_thread = _HandlerThread(self,
                                              pool_size,
                                              max_works_per_worker,
                                              load_balancer,
                                              worker_loop_factory,
                                              self._WorkerManager)

        # Important to set thread daemon to True such that one can
        # trigger functions registerd to atexit, closing workers gracefully.
        self._handler_thread.setDaemon(True)
        self._handler_thread.start()

    def set_future_loop(self, loop: asyncio.AbstractEventLoop):
        """Sets loop for awaitable futures to await results.

        This loop can also be set in initialization.

        Args:
            loop: The Loop needed for awaitable futures.

        Raises:
            RuntimeError: If executor has been shut down, or
                executor is set to be unawaitable.
            AplexWorkerError: If some workers are broken or raise
                BaseException.

        """
        with self._lock:
            if self._closed:
                raise RuntimeError('Executor has been shut down.')
            elif self._exception:
                raise self._exception

            if not self._awaitable:
                raise RuntimeError('Assigning event loop to an unawaitable')
            self._loop = loop

    def submit(self,
               work: Callable,
               *args: Tuple,
               load_balancing_meta: Optional[Any] = None,
               **kwargs: Dict
    ) -> Union[AsyncioFuture, ConcurrentFuture]:
        """submits your work like the way in concurrent.futures.

        The work submitted will be sent to the specific worker that
        the load balancer choose.

        Note:
            The work you submit should be a callable, And a ``coroutine``
            is **not** a callable. You should submit a ``coroutine function``
            and specify its args and kwargs here instead.

        Args:
            work: The callable that will be run in a worker.
            *args: Position arguments for work.
            load_balancing_meta: This will be passed to load balancer for
                the choice of proper worker.
            **kwargs: Keyword arguments for work.

        Returns:
            A future.

            The future will be awaitable like that in asyncio if ``awaitable``
            is set to True in executor construction, otherwise, unawaitable
            like that in concurrent.futures.

        Raises:
            RuntimeError: If executor has been shut down.
            AplexWorkerError: If some workers are broken or raise
                BaseException.
            TypeError: If work is not a callable.

        """
        with self._lock:
            if self._closed:
                raise RuntimeError('Executor has been shut down.')
            elif self._exception:
                raise self._exception

            if not callable(work):
                raise TypeError('{} is not a callable to run.'.format(work))

            # For running callables, only coroutine can be cancelled.
            cancel_interface = None
            if inspect.iscoroutinefunction(work):
                cancel_interface = self._handler_thread.cancel_work

            concurrent_future = ConcurrentFuture(cancel_interface)
            if self._awaitable:
                # Chain these two futures before submit for thread-safty.
                asyncio_future = AsyncioFuture(concurrent_future,
                                               self._loop)

            item = SubmitItem.work_form(work, args, kwargs,
                                        id(concurrent_future))
            self._handler_thread.submit((item, concurrent_future,
                                         load_balancing_meta))
            return asyncio_future if self._awaitable else concurrent_future

    if compat.PY36:
        _MapReturnAsync = AsyncGenerator
    else:
        _MapReturnAsync = AsyncIterator

    def map(self,
            work: Callable,
            *iterables: Tuple[Iterable],
            timeout: Optional[float] = None,
            chunksize: int = 1,
            load_balancing_meta: Optional[Any] = None
    ) -> Union[_MapReturnAsync, Generator]:
        """map your work like the way in concurrent.futures.

        The work submitted will be sent to the specific worker that
        the load balancer choose.

        Note:
            The work you submit should be a callable, And a ``coroutine``
            is **not** a callable. You should submit a ``coroutine function``
            and specify its args and kwargs here instead.

        Args:
            work: The callable that will be run in a worker.
            *iterables: Position arguments for work. All of them are iterable
                and have same length.
            timeout: The time limit for waiting results.
            chunksize: Works are gathered, partitioned as chunks in this size,
                and then sent to workers.
            load_balancing_meta: This will be passed to load balancer for
                the choice of proper worker.

        Returns:
            A async generator yielding the map results if ``awaitable`` is set
            to True, otherwise a generator. In python3.5, async iterator is
            used to replace async generator.

            If a exception is raised in a work, it will be re-raised in the
            generator, and the remaining works will be cancelled.

        Raises:
            ValueError: If chunksize is less than 1.
            TypeError: If work is not a callable.
        """
        if chunksize < 1:
            raise ValueError('Chunksize should be at least 1.')

        if inspect.iscoroutinefunction(work):
            work_on_chunk = _handle_chunk_async
        elif callable(work):
            work_on_chunk = _handle_chunk
        else:
            raise TypeError('{} is not a callable to run.'.format(work))

        # Include internal process/thread communication time.
        end_time = timeout + time.time() if timeout is not None else None

        futures = []
        total = zip(*iterables)
        chunk = tuple(itertools.islice(total, chunksize))
        while chunk:
            futures.append(
                self.submit(work_on_chunk, work, chunk,
                            load_balancing_meta=load_balancing_meta))
            chunk = tuple(itertools.islice(total, chunksize))

        if not futures:
            return []

        if self._awaitable:
            if not compat.PY36:
                return self._MapAsyncIterator(futures, end_time, self._loop)
            return self._map_async_gen(futures, end_time)
        else:
            return self._map_gen(futures, end_time)


    if compat.PY36:
        # If statement with variable condition can not prevent Python3.5
        # from compiling this function to bytecode, causing syntax error
        # in Python3.5, which does not support async generator.

        from .py35_support import _map_async_gen
    else:
        # According to PEP525: `asynchronous generators are 2x faster
        # than an equivalent implemented as an asynchronous iterator`,
        # async iterator is used only for python3.5, which does not
        # support async generator.

        class _MapAsyncIterator(object):
            """A async iterator to replace async generator in python3.5."""

            def __init__(self,
                         futures: AsyncioFuture,
                         end_time=None,
                         loop=None):
                self._futures = futures
                self._end_time = end_time
                self._loop = loop

                self._results = None

            if compat.PY352:
                def __aiter__(self):
                    return self
            else:
                async def __aiter__(self):
                    return self

            async def __anext__(self):
                if not self._results:
                    if not self._futures:
                        raise StopAsyncIteration()

                    future = self._futures.pop(0)
                    try:
                        if self._end_time is not None:
                            self._results = await asyncio.wait_for(
                                future, self._end_time - time.time(), loop=self._loop)
                        else:
                            self._results = await future
                    except Exception:
                        future.cancel()
                        for future in self._futures:
                            future.cancel()
                        raise
                return self._results.pop(0)


    def _map_gen(self,
                 futures: List[ConcurrentFuture],
                 end_time=None) -> Generator:
        """The generator that ``map`` return when ``awaitable`` is False."""

        try:
            while futures:
                future = futures.pop(0)
                if end_time is not None:
                    yield from future.result(end_time - time.time())
                else:
                    yield from future.result()
        # Finally clause for generator exit and timeout.
        finally:
            future.cancel()  # This future may have been done.
            for future in futures:
                future.cancel()

    def shutdown(self, wait: bool = True):
        """Shuts down the executor and frees the resource.

        Args:
            wait: Whether to block until shutdown is finished.

        """
        import concurrent
        with self._lock:
            if self._closed:
                return
            self._closed = True

        # Handler may has already been closed.
        if self._exception is None:
            self._handler_thread.close()

        if wait:
            self._handler_thread.join()

        self._handler_thread = None
        self._loop = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown(wait=True)

    def __del__(self):
        # XXX
        if not self._closed and self._exception is None:
            warnings.warn('{} got garbage-collected. Started to '
                          'shutdown'.format(self))
            self.shutdown(wait=False)


@atexit.register  # This decorator will return _ensure_close back.
def _ensure_close():
    """Closes all workers for graceful exit."""

    # Use tuple to construct strong ref to avoid gc-collection during the loop.
    for executor in tuple(_executor_track_set):
        executor.shutdown(wait=True)


def _register_keyboard_interrupt_handler():
    origin = signal.getsignal(signal.SIGINT)

    def handler(signum, stack):
        _ensure_close()
        print(signum)
        origin(signum, stack)

    signal.signal(signal.SIGINT, handler)


_register_keyboard_interrupt_handler()
