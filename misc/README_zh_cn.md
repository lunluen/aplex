# Aplex 轻松上手

[![构造状态](https://travis-ci.org/lunluen/aplex.svg?branch=master)](https://travis-ci.org/lunluen/aplex)
[![codecov](https://codecov.io/gh/lunluen/aplex/branch/master/graph/badge.svg)](https://codecov.io/gh/lunluen/aplex)
[![平台](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-orange.svg)](https://github.com/lunluen/aplex)
[![支援的Python版本](https://img.shields.io/pypi/pyversions/aplex.svg?style=flat)](https://pypi.org/project/aplex/)
[![套件版本](https://img.shields.io/pypi/v/aplex.svg?style=flat)](https://pypi.org/project/aplex/)
[![授权](https://img.shields.io/github/license/lunluen/aplex.svg?style=flat)](https://github.com/lunluen/aplex/blob/master/LICENSE)
[![维护](https://img.shields.io/maintenance/yes/2019.svg?style=flat)](https://github.com/lunluen/aplex)

Aplex 是 asynchronous pool executor 的缩写，用于结合 asyncio 与
 multiprocessing 和 threading 的 Python 套件。

- Aplex 帮助你在其他 process 或 thread 中执行 coroutine 和 function。
- Aplex 提供的使用方式与标准库 `concurrent.futures` 相同，直觉又熟悉。
- Aplex 让你执行负载平衡，如果有需要的话。

## 安装

对一般使用者只须使用管理套件 [pip](https://pypi.org/project/aplex/) 来安装 aplex.

```bash
pip install aplex
```

如需贡献代码, 建议使用 pipenv：

```bash
git clone https://github.com/lunluen/aplex.git
cd aplex
pipenv install --dev
```

也可以使用 setuptools：

```bash
git clone https://github.com/lunluen/aplex.git
cd aplex
python setup.py develop
```

## 使用方法

名称解释：
> 所谓 `work` 指的是你想执行在其他 process 或 thread 并基于 asyncio 的
> `callable`，其可以是 coroutine function 或就是一般的 function。

以下情况中，`work` 指的是 coroutine function `demo`。

### Submit

你可以如此提交你的工作：

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

*注意*: 如果是Windows使用者，`if __name__ == '__main__':` 就是必须的。
这是 multiprocessing 本身的设计。

执行结果：

```bash
Status: 200
```

### Map

当有许多重复的工作时，试试 `map`:

```python
iterable = ('http://httpbin.org' for __ in range(10))
for status in pool.map(demo, iterable, timeout=10):
    print('Status: %d.' % status)
```

### 异步(Asynchronously)等待结果

Aplex 也提供使用 `await` 来等待结果的方法，非常简单。

只需把keyword argument `awaitable` 设置成 `True`！

例如：

```python
pool = ProcessAsyncPoolExecutor(awaitable=True)
```

然后就可以

```python
future = pool.submit(demo, 'http://httpbin.org')
status = await future
```

那 `map` 呢?

```python
async for status in pool.map(demo, iterable, timeout=10):
    print('Status: %d.' % status)
```

### 负载平衡

于 aplex，每个执行 work 的 worker 其实就是个同台电脑上的 process 或 thread，所以它们有着相同的运算能力。 *但*，你的 work 可能会吃掉不等量的效能，那么你就会需要负载平衡器。

Aplex 提供了一些有用的负载平衡器。有：`RoundRobin`，`Random`，`Average`。预设采用`RoundRobin`。

简单的在产生物件时传入你想要的给 keyword argument 即可：

```python
from aplex.load_balancers import Average

if __name__ == '__main__':
    pool = ProcessAsyncPoolExecutor(load_balancer=Average)
```

就是如此简单。 :100:

你也可以自己实作一个：

```python
from aplex import LoadBalancer

class MyAwesomeLoadBalancer(LoadBalancer):
    def __init__(*args, **kwargs):
        super().__init__(*args, **kwargs) # Don't forget this.
        awesome_attribute = 'Hello Aplex!'

    def get_proper_worker(self):
        the_poor_guy = self.workers[0]
        return the_poor_guy
```

如何实作负载平衡器详见：[LoadBalancer in API Reference](https://aplex.readthedocs.io/en/latest/api.html#module-aplex.load_balancers)

### Worker loop factory

此外，如果你认为asyncio内建的loop太慢了：

```python
import uvloop

if __name__ == '__main__':
    pool = ProcessAsyncPoolExecutor(worker_loop_factory=uvloop.Loop)
```

## 喜欢吗?

往上滑并按下 `Watch - Releases only` 和 `Star` 来点个赞！ :+1:

## 任何意见?

欢迎开 issue (只要别滥用即可)。

或连系我：`mas581301@gmail.com` :mailbox:

任何有关 aplex 都很欢迎，像问题回报、系统设计、变数命名，甚至注解的英文文法可以！

## 如何贡献

欢迎贡献。

提问或给建议也都是种贡献。

请看 [CONTRIBUTING.md](https://github.com/lunluen/aplex/blob/master/CONTRIBUTING.md)

## 授权

[MIT](https://github.com/lunluen/aplex/blob/master/LICENSE)
