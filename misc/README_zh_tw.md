# Aplex 輕鬆上手

[![構造狀態](https://travis-ci.org/lunluen/aplex.svg?branch=master)](https://travis-ci.org/lunluen/aplex)
[![codecov](https://codecov.io/gh/lunluen/aplex/branch/master/graph/badge.svg)](https://codecov.io/gh/lunluen/aplex)
[![平台](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-orange.svg)](https://github.com/lunluen/aplex)
[![支援的Python版本](https://img.shields.io/pypi/pyversions/aplex.svg?style=flat)](https://pypi.org/project/aplex/)
[![套件版本](https://img.shields.io/pypi/v/aplex.svg?style=flat)](https://pypi.org/project/aplex/)
[![授權](https://img.shields.io/github/license/lunluen/aplex.svg?style=flat)](https://github.com/lunluen/aplex/blob/master/LICENSE)
[![維護](https://img.shields.io/maintenance/yes/2019.svg?style=flat)](https://github.com/lunluen/aplex)

Aplex 是 asynchronous pool executor 的縮寫，用於結合 asyncio 與
 multiprocessing 和 threading 的 Python 套件。

- Aplex 幫助你在其他 process 或 thread 中執行 coroutine 和 function。
- Aplex 提供的使用方式與標準庫 `concurrent.futures` 相同，直覺又熟悉。
- Aplex 讓你執行負載平衡，如果有需要的話。

## 安裝

對一般使用者只須使用管理套件 [pip](https://pypi.org/project/aplex/) 來安裝 aplex.

```bash
pip install aplex
```

如需貢獻代碼, 建議使用 pipenv：

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

名稱解釋：
> 所謂 `work` 指的是你想執行在其他 process 或 thread 並基於 asyncio 的
> `callable`，其可以是 coroutine function 或就是一般的 function。

以下情況中，`work` 指的是 coroutine function `demo`。

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

*注意*: 如果是Windows使用者，`if __name__ == '__main__':` 就是必須的。
這是 multiprocessing 本身的設計。

執行結果：

```bash
Status: 200
```

### Map

當有許多重複的工作時，試試 `map`:

```python
iterable = ('http://httpbin.org' for __ in range(10))
for status in pool.map(demo, iterable, timeout=10):
    print('Status: %d.' % status)
```

### 異步(Asynchronously)等待結果

Aplex 也提供使用 `await` 來等待結果的方法，非常簡單。

只需把keyword argument `awaitable` 設置成 `True`！

例如：

```python
pool = ProcessAsyncPoolExecutor(awaitable=True)
```

然後就可以

```python
future = pool.submit(demo, 'http://httpbin.org')
status = await future
```

那 `map` 呢?

```python
async for status in pool.map(demo, iterable, timeout=10):
    print('Status: %d.' % status)
```

### 負載平衡

於 aplex，每個執行 work 的 worker 其實就是個同台電腦上的 process 或 thread，所以它們有著相同的運算能力。*但*，你的 work 可能會吃掉不等量的效能，那麼你就會需要負載平衡器。

Aplex 提供了一些有用的負載平衡器。有：`RoundRobin`，`Random`，`Average`。預設採用`RoundRobin`。

簡單的在產生物件時傳入你想要的給 keyword argument 即可：

```python
from aplex.load_balancers import Average

if __name__ == '__main__':
    pool = ProcessAsyncPoolExecutor(load_balancer=Average)
```

就是如此簡單。 :100:

你也可以自己實作一個：

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

如何實作負載平衡器詳見：[LoadBalancer in API Reference](https://aplex.readthedocs.io/en/latest/api.html#module-aplex.load_balancers)

### Worker loop factory

此外，如果你認為asyncio內建的loop太慢了：

```python
import uvloop

if __name__ == '__main__':
    pool = ProcessAsyncPoolExecutor(worker_loop_factory=uvloop.Loop)
```

## 喜歡嗎?

往上滑並按下 `Watch - Releases only` 和 `Star` 來點個讚！ :+1:

## 任何意見?

歡迎開 issue (只要別濫用即可)。

或連繫我：`mas581301@gmail.com` :mailbox:

任何有關 aplex 都很歡迎，像問題回報、系統設計、變數命名，甚至註解的英文文法可以！

## 如何貢獻

歡迎貢獻。

提問或給建議也都是種貢獻。

請看 [CONTRIBUTING.md](https://github.com/lunluen/aplex/blob/master/CONTRIBUTING.md)

## 授權

[MIT](https://github.com/lunluen/aplex/blob/master/LICENSE)
