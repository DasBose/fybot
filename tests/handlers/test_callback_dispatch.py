from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock

from handlers.callback_dispatch import dispatch_async


def test_dispatch_async_submits_to_executor() -> None:
    executor = MagicMock(spec=ThreadPoolExecutor)
    fn = MagicMock()

    dispatch_async(executor, fn, "arg1", 2)

    executor.submit.assert_called_once_with(fn, "arg1", 2)
