"""Shared aiohttp session used for outbound HTTP calls."""
import aiohttp

_session: aiohttp.ClientSession | None = None
_headers = {"User-Agent": "Atom-Discord-Bot"}


def get_shared_session() -> aiohttp.ClientSession:
    """Get the shared aiohttp session, creating one if needed."""
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession(headers=_headers)
    return _session


async def close_shared_session():
    """Close the shared aiohttp session."""
    global _session
    if _session and not _session.closed:
        await _session.close()
    _session = None