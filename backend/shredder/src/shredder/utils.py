import asyncio
import socket
from functools import wraps


def worker_identity(job_context) -> dict:
    """Which machine and worker are running this job. worker_id says nothing about the VM."""
    return {"machine": socket.gethostname(), "worker_name": job_context.worker_name}


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
