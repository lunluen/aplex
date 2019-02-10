"""Defines the futures returned to users."""

import asyncio
import concurrent.futures
from concurrent.futures._base import PENDING


class ConcurrentFuture(concurrent.futures.Future):
    """A concurrent.futures.Future subclass that cancels like asyncio.Task.
    """
    def __init__(self, cancel_interface):
        super().__init__()
        self._cancel_interface = cancel_interface
        
        # A flag to avoid cancelling twice and that work finishs
        # before the cancellation function scheduled.
        self._cancel_interface_called = False

    def cancel(self):
        """Tries to cancel the work submitted to worker.

        *Unlike* ``concurrent.futures``, the *running* work is *cancellable*
        as long as it's a ``coroutine function``.

        Returns:
            True if cancellable, False otherwise.

        """
        with self._condition:
            if super().cancel():
                # Cancellable if it's pending.
                return True
            else:
                # Running or finished.
                if self.running():
                    # The interface didn't be provided to this future, since
                    # the submitted work is not a coroutine function.
                    if self._cancel_interface is None:
                        return False

                    # Avoid cancelling twice.
                    if not self._cancel_interface_called:
                        self._cancel_interface_called = True
                        self._cancel_interface(self)
                    return True  # Returns True as asyncio.Task.cancel() does.
                else:
                    return False

    def _cancel_running(self):
        """A method called by executor's handler to force the running
        futures into cancelled state.
        """
        with self._condition:
            assert self.running() and self._cancel_interface_called
            self._state = PENDING  # Unable to cancel if its RUNNING.
            super().cancel()
            self.set_running_or_notify_cancel()
            return True


class AsyncioFuture(asyncio.Future):
    """Asyncio.Future subclass that cancels like asyncio.Task.
    """

    def __init__(self, concurrent_future, loop=None):
        super().__init__(loop=loop)
        self._future = concurrent_future

        # TODO(Lun): Not to use _chain_future, since it's private.
        asyncio.futures._chain_future(self._future, self)

    def cancel(self):
        """Tries to cancel the work submitted to worker.

        *Unlike* ``concurrent.futures``, the *running* work is *cancellable*
        as long as it's a ``coroutine function``.

        Returns:
            True if cancellable, False otherwise.

        """
        # This method will call by users and be called again by the
        # callback scheduled in the chained concurrent future.
        # When called by a callback, ``asyncio.Future.cancel`` will
        # be executed via super().cancel().

        # The chained future will be cancelled if and only if the work is
        # done by cancelling. Then just run ``asyncio.Future.cancel``.
        if self._future.cancelled():
            return super().cancel()

        # The below block will be executed when it's called by the user.
        self._log_traceback = False
        return self._future.cancel()
