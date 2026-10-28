import asyncio
from functools import wraps


def set_timeout(seconds):
    """
    Decorator that enforces a timeout on an async function.
    Raises asyncio.TimeoutError if the function exceeds the timeout.
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await asyncio.wait_for(func(*args, **kwargs), timeout=seconds)

        return wrapper

    return decorator
