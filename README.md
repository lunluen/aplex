# Aplex

[![build](https://img.shields.io/travis/com/lunluen/aplex.svg?style=flat)]()
[![coverage](https://img.shields.io/codecov/c/github/lunluen/aplex.svg?style=flat)](https://github.com/lunluen/aplex)
[![platform]()]()
[![supported pythons](https://img.shields.io/pypi/pyversions/aplex.svg?style=flat)]()
[![package version](https://img.shields.io/pypi/v/aplex.svg?style=flat)]()
[![license](https://img.shields.io/github/license/lunluen/aplex.svg?style=flat)]()
[![maintenance](https://img.shields.io/maintenance/yes/2019.svg?style=flat)]()

Translation: 
[简体中文](https://github.com/lunluen/aplex/blob/master/README_zh_cn.md)
|
[繁體中文](https://github.com/lunluen/aplex/blob/master/misc/README_zh_tw.md)

Aplex is a Python library for combining asyncio with
multiprocessing and threading.

- Aplex helps you run coroutines and functions in other process
  or thread with asyncio.
- Aplex provides a usage like that of  standard library `concurrent.futures`,
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
or with setuptools

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

Aplex allows one to await results with loop that already exists. It's quite simple.

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

How about map?

```python
async for status in pool.map(demo, iterable, timeout=10):
    print('Status: %d.' % status)
```

### Load balancing

In aplex, each worker is the process or thread on your computer. That is, they have the same capability computing.
*But*, your works might have different workloads. Then you need a load balancer.

Aplex provides some useful load balancers. They are `RoundRobin`, `Random`, and `Average`. The default is `RoundRobin`.

Simply set this in contruction keyword argument:

```python
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

See details of how to implement a load balancer at: []()


### Worker loop factory

By the way, if you think the build-in asyncio loop is too slow:

```python
import uvloop

if __name__ == '__main__':
    pool = ProcessAsyncPoolExecutor(worker_loop_factory=uvloop.Loop)
```

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
