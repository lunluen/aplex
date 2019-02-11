.. _api:

API
===

.. module:: aplex

Executor Objects
----------------

.. autoclass:: ProcessAsyncPoolExecutor
    :members:
    :inherited-members:

.. autoclass:: ThreadAsyncPoolExecutor
    :members:
    :inherited-members:

Future Objects
--------------

.. module:: aplex.futures

.. autoclass:: ConcurrentFuture
    :members:

.. autoclass:: AsyncioFuture
    :members:

Load Balancer Objects
---------------------

.. module:: aplex.load_balancers

.. autoclass:: LoadBalancer
    :members:

.. autoclass:: RoundRobin
    :members:
    :inherited-members:

.. autoclass:: Random
    :members:
    :inherited-members:

.. autoclass:: Average
    :members:
    :inherited-members:
