"""This module contains load balancer base class and some implementations.

Users can inherit LoadBalancer, the base class, from this module to write
their own load balancers.

Attributes:
    LoadBalancer: The base class.
    RoundRobin: A load balancer based on round-robin algorithm.
    Random: A load balancer that chooses proper worker randomly.
    Average: A load balancer that tries to equalize the workloads of all
        the workers. To put it otherwise, it assign work to the worker
        having minimun workload.

"""
import itertools
import random
import typing
from abc import ABCMeta, abstractmethod
from typing import (Any, Dict, Generic, Iterator, List,
                    Mapping, Optional, Sequence, TypeVar)

from .protect import protect
if typing.TYPE_CHECKING:
    from .process import _ProcessWorker
    from .thread import _ThreadWorker

__all__ = ['LoadBalancer']
__all__ += ['RoundRobin', 'Random', 'Average']


Worker = TypeVar('Worker', '_ProcessWorker', '_ThreadWorker')


class LoadBalancer(Generic[Worker], metaclass=ABCMeta):
    """The base class of all load balancers.

    Users can inherit this to write their own load balancers.
    """
    def __init__(self,
                 workers: List[Worker],
                 workloads: Dict[Worker, int],
                 max_works_per_worker: int):
        """Initialization.

        Note: Must call ``super().__init__(*args, **kwargs)`` in the
        beginning of the ``__init__`` block if you are trying to
        overwrite this.

        Args:
            workers: A argument for ``workers`` property.
            workloads: A argument for ``workloads`` property.
            max_works_per_worker: A argument for ``max_works_per_worker``
                property.

        """
        self._workers = protect(workers)
        self._workloads = protect(workloads)
        self._max_works_per_worker = max_works_per_worker

    @property
    def workers(self) -> Sequence[Worker]:
        """Returns worker list."""
        return self._workers

    @property
    def workloads(self) -> Mapping[Worker, int]:
        """Returns worker workload mapping."""
        return self._workloads

    @property
    def max_works_per_worker(self) -> int:
        """Returns tha max number of works a worker can run at the same time.
        """
        return self._max_works_per_worker

    def get_available_workers(self) -> Iterator[Worker]:
        """Returns the workers that does not reach the
        ``max_works_per_worker`` limit.

        Returns:
            A iterator of the available workers.

        """
        return filter(self.is_available, self.workers)

    def is_available(self, worker: Worker) -> bool:
        """Returns if the given worker reaches the ``max_works_per_worker``
        limit.

        Args:
            worker: A worker object.

        Returns:
            True if available, else False.

        """
        return self.workloads[worker] < self.max_works_per_worker

    @abstractmethod
    def get_proper_worker(self,
                          load_balancing_meta: Optional[Any]) -> Worker:
        """The method to be implemented by users. Returns an available worker.

        Note:
            There is always at least an available worker when this method
            is called.

        Args:
            load_balancing_meta: An optional argument specified in ``submit``
                and ``map`` methods that users may need for choosing a
                proper worker.

        Returns:
            A worker that is available for work assignment.

        """
        raise NotImplementedError()


class RoundRobin(LoadBalancer):
    """A load balancer based on round-robin algorithm."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._round_robin = itertools.cycle(self.workers)

    def get_proper_worker(self,
                          load_balancing_meta: Optional[Any]) -> Worker:
        """Returns the next available worker.

        Args:
            load_balancing_meta: An optional argument specified in ``submit``
                and ``map`` methods that users may need for choosing a
                proper worker.

        Returns:
            A worker that is available for work assignment.

        """
        for __ in range(len(self.workers)):
            worker = next(self._round_robin)
            if self.is_available(worker):
                return worker
        assert False, 'At least one worker is available.'


class Random(LoadBalancer):
    """A load balancer that chooses proper worker randomly."""

    def get_proper_worker(self,
                          load_balancing_meta: Optional[Any]) -> Worker:
        """Randomly picks an avaiable worker.

        Args:
            load_balancing_meta: An optional argument specified in ``submit``
                and ``map`` methods that users may need for choosing a
                proper worker.

        Returns:
            A worker that is available for work assignment.

        """
        return random.choice(tuple(self.get_available_workers()))


class Average(LoadBalancer):
    """A load balancer that tries to equalize the workloads of all the workers.

    To put it otherwise, it assign work to the worker having minimun workload.
    """
    def get_proper_worker(self,
                          load_balancing_meta: Optional[Any]) -> Worker:
        """Returns the worker with minimum workload.

        Args:
            load_balancing_meta: An optional argument specified in ``submit``
                and ``map`` methods that users may need for choosing a
                proper worker.

        Returns:
            A worker that is available for work assignment.

        """
        return min(self.get_available_workers(), key=self._sort_key)

    def _sort_key(self, worker):
        return self.workloads[worker]
