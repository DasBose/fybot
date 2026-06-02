from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor


def dispatch_async(
    executor: ThreadPoolExecutor,
    fn: Callable[..., None],
    *args: object,
) -> None:
    """Submit work to the pool so the caller's thread stays non-blocking."""
    executor.submit(fn, *args)
