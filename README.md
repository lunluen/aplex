# Aplex Quickstart

[![Build Status](https://travis-ci.org/lunluen/aplex.svg?branch=master)](https://travis-ci.org/lunluen/aplex)
[![codecov](https://codecov.io/gh/lunluen/aplex/branch/master/graph/badge.svg)](https://codecov.io/gh/lunluen/aplex)
[![platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-orange.svg)](https://github.com/lunluen/aplex)
[![supported pythons](https://img.shields.io/pypi/pyversions/aplex.svg?style=flat)](https://pypi.org/project/aplex/)
[![package version](https://img.shields.io/pypi/v/aplex.svg?style=flat)](https://pypi.org/project/aplex/)
[![license](https://img.shields.io/github/license/lunluen/aplex.svg?style=flat)](https://github.com/lunluen/aplex/blob/master/LICENSE)
[![maintenance](https://img.shields.io/maintenance/yes/2019.svg?style=flat)](https://github.com/lunluen/aplex)

Translations:
[简体中文](https://github.com/lunluen/aplex/blob/master/misc/README_zh_cn.md)
|
[繁體中文](https://github.com/lunluen/aplex/blob/master/misc/README_zh_tw.md)

"Aplex", short for "**a**synchronous **p**oo**l** **ex**ecutor", is a Python
library for combining asyncio with multiprocessing and threading.

- Aplex helps you run coroutines and functions in other processes
  or threads with asyncio concurrently and in parallel (if with processes).
- Aplex provides a usage like that of standard library `concurrent.futures`,
  which is familiar to you and intuitive.
- Aplex lets you do load balancing in a simple way if you need.

## Installation

For general users, use the package manager [pip](https://pip.pypa.io/en/stable/) to
install aplex.

```bash
pip install aplex
```

For contributors, install with pipenv:

```bash
git clone https://github.com/lunluen/aplex.git
cd aplex
pipenv install --dev
```

or with setuptools:

```bash
git clone https://github.com/lunluen/aplex.git
cd aplex
python setup.py develop
```

## Usage

Definition to know:
> A `work` is a `callable` you want to run with asyncio and multiprocessing or threading.
> It can be a coroutine function or just a function.

In below case, the `work` is the coroutine function `demo`.

### Submit

You can submit your work like:

```python
import aiohttp
from aplex import ProcessAsyncPoolExecutor

async def demo(url):
    async with aiohttp.request('GET', url) as response:
        return response.status

if __name__ == '__main__':
    pool = ProcessAsyncPoolExecutor(pool_size=8)
    future = pool.submit(demo, 'http://httpbin.org')
    print('Status: %d.' % future.result())
```

*Note*: If you are running python on windows, `if __name__ == '__main__':`
is necessary. That's the design of multiprocessing.

Result:

```bash
Status: 200
```

### Map

For multiple works, try `map`:

```python
iterable = ('http://httpbin.org' for __ in range(10))
for status in pool.map(demo, iterable, timeout=10):
    print('Status: %d.' % status)
```

### Awaiting results

Aplex allows one to `await` results with the event loop that already exists.
It's quite simple.

Just set keyword argument `awaitable`  to `True`!

For example:

```python
pool = ProcessAsyncPoolExecutor(awaitable=True)
```

Then

```python
future = pool.submit(demo, 'http://httpbin.org')
status = await future
```

How about `map`?

```python
async for status in pool.map(demo, iterable, timeout=10):
    print('Status: %d.' % status)
```

### Load balancing

In aplex, each worker running your works is the process or thread on your
computer. That is, they have the same capability computing.
*But*, your works might have different workloads. Then you need a load balancer.

Aplex provides some useful load balancers. They are `RoundRobin`, `Random`, and `Average`. The default is `RoundRobin`.

Simply set what you want in the keyword argument of contruction:

```python
from aplex import ProcessAsyncPoolExecutor
from aplex.load_balancers import Average

if __name__ == '__main__':
    pool = ProcessAsyncPoolExecutor(load_balancer=Average)
```

Done. So easy. :100:

You can also customize one:

```python
from aplex import LoadBalancer

class MyAwesomeLoadBalancer(LoadBalancer):
    def __init__(*args, **kwargs):
        super().__init__(*args, **kwargs)  # Don't forget this.
        awesome_attribute = 'Hello Aplex!'

    def get_proper_worker(self):
        the_poor_guy = self.workers[0]
        return the_poor_guy
```

See details of how to implement a load balancer at: [LoadBalancer | API Reference](https://aplex.readthedocs.io/en/latest/api.html#module-aplex.load_balancers)

### Worker loop factory

By the way, if you think the build-in asyncio loop is too slow:

```python
import uvloop
from aplex import ProcessAsyncPoolExecutor

if __name__ == '__main__':
    pool = ProcessAsyncPoolExecutor(worker_loop_factory=uvloop.Loop)
```

## Graceful Exit

Takeing Python3.6 for example, a graceful exit without aplex would be something like this:

```python
try:
    loop.run_forever()
finally:
    try:
        tasks = asyncio.Task.all_tasks()
        if tasks:
            for task in tasks:
                task.cancel()
            gather = asyncio.gather(*tasks)
            loop.run_until_complete(gather)
        loop.run_until_complete(loop.shutdown_asyncgens())
    finally:
        loop.close()
```

...It's definitely a joke.

Here, just treat pool as a context manager:

```python
with ProcessAsyncPoolExecutor() as pool:
    do_something()
```

or remember to call `pool.shutdown()`.
These help you deal with that joke.

...

What? You forget to call `pool.shutdown()`?!

Ok, fine. It will shut down automatically when the program exits or it's garbage-collected.

## Like this?

Scroll up and click `Watch - Releases only` and `Star` as a thumbs up! :+1:

## Any feedback?

Feel free to open a issue (just don't abuse it).

Or contact me: `mas581301@gmail.com` :mailbox:

Anything about aplex is welcome, such like bugs, system design, variable naming, even English grammer of docstrings!

## How to contribute

Contribution are welcome.

Asking and advising are also kinds of contribution.

Please see [CONTRIBUTING.md](https://github.com/lunluen/aplex/blob/master/CONTRIBUTING.md)

## License

[MIT](https://github.com/lunluen/aplex/blob/master/LICENSE)
