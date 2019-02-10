import pytest

from aplex.load_balancers import RoundRobin, Random, Average


POOL_SIZE = 5
max_works_per_worker = 7

_workers = [*range(POOL_SIZE)]
_loads = (7, 3, 7, 2, 7)
_workloads = dict(zip(_workers, _loads))
_proper_worker = {
    RoundRobin: 1,
    Random: None,  # Any available is proper.
    Average: 3,
}


@pytest.fixture(params=[RoundRobin, Random, Average])
def load_balancer(request):
    yield request.param(_workers, _workloads,
                        max_works_per_worker)


class TestLoadbalancing:

    def test_get_proper_worker(self, load_balancer):
        worker = load_balancer.get_proper_worker(None)

        if isinstance(load_balancer, Random):
            # For Random, all available workers are proper.
            assert _workloads[worker] < max_works_per_worker
            return
        assert worker == _proper_worker[type(load_balancer)]


def test_protected(load_balancer):
    with pytest.raises(TypeError, match=r'not support item assignment'):
        load_balancer._workers[0] = 0

    with pytest.raises(TypeError, match=r'not support item assignment'):
        load_balancer._workloads[0] = 0
