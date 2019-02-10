"""Inherits base classes in executor.py for threading."""

import threading
import queue

from .executor import (BaseAsyncPoolExecutor, BaseWorkerManager,
                       BaseWorkerMixin, ResultItem)

__all__ = ['ThreadAsyncPoolExecutor']


class _ThreadWorker(BaseWorkerMixin, threading.Thread):

    def __init__(self, *args, **kwargs):
        self._submit_queue = queue.Queue()

        super().__init__(*args, **kwargs)


class _ThreadWorkerManager(BaseWorkerManager):

    _Worker = _ThreadWorker

    def __init__(self, *args, **kwargs):
        self._result_queue = queue.Queue()

        super().__init__(*args, **kwargs)

    def wait_return_item(self) -> ResultItem:
        return self._result_queue.get(block=True)


class ThreadAsyncPoolExecutor(BaseAsyncPoolExecutor):
    _WorkerManager = _ThreadWorkerManager
