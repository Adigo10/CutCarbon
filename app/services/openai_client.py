"""One lazy Responses client per event loop; credentials never enter logs."""
import asyncio
import weakref
from openai import AsyncOpenAI
from app.config import settings

_clients = weakref.WeakKeyDictionary()


class AIUnavailableError(RuntimeError):
    pass


def get_client() -> AsyncOpenAI:
    if not settings.OPENAI_API_KEY:
        raise AIUnavailableError("OPENAI_API_KEY is not configured")
    loop = asyncio.get_running_loop()
    client = _clients.get(loop)
    if client is None:
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY, max_retries=1)
        _clients[loop] = client
    return client


async def close_client() -> None:
    client = _clients.pop(asyncio.get_running_loop(), None)
    if client is not None:
        await client.close()
