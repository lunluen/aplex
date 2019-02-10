import pytest

from aplex import ProcessAsyncPoolExecutor, ThreadAsyncPoolExecutor


# TODO(Lun): write code to just select one.
@pytest.fixture(params=[ProcessAsyncPoolExecutor, ThreadAsyncPoolExecutor])
def executor_factory(request):
    executor = None

    def instantiate(*args, **kwargs):
        nonlocal executor
        executor = request.param(*args, **kwargs)
        return executor

    yield instantiate

    executor.shutdown()


@pytest.fixture
def executor(executor_factory):
    executor = executor_factory()

    yield executor

    executor.shutdown()
