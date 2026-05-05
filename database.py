"""
GitHub Gist-based database layer for the Discord bot.
Provides persistent storage using GitHub Gists with local caching.
"""

import asyncio
import json
import os
import time
from typing import Any, Optional

import aiohttp
from dotenv import load_dotenv

load_dotenv()


class GistDatabase:
    """Async GitHub Gist database with caching support."""

    def __init__(self):
        self.token: Optional[str] = os.getenv("GITHUB_TOKEN")
        self.gist_id: Optional[str] = os.getenv("GIST_ID")
        self._session: Optional[aiohttp.ClientSession] = None
        self._cache: dict[str, Any] = {}
        self._cache_timestamps: dict[str, float] = {}
        self._lock = asyncio.Lock()
        self._initialized = False
        self._auto_create = os.getenv("GIST_AUTO_CREATE", "true").lower() == "true"

        # Cache settings
        self._cache_ttl = 60  # seconds

        if not self.token:
            raise ValueError("GITHUB_TOKEN environment variable is required")

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={
                    "Authorization": f"token {self.token}",
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "Atom-Discord-Bot",
                }
            )
        return self._session

    async def close(self):
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def initialize(self) -> bool:
        """Initialize the database by fetching existing gist or creating a new one."""
        async with self._lock:
            if self._initialized:
                return True

            try:
                if self.gist_id:
                    # Try to fetch existing gist
                    success = await self._fetch_gist()
                    if success:
                        self._initialized = True
                        return True

                    if not self._auto_create:
                        raise RuntimeError(
                            f"Failed to fetch gist with ID: {self.gist_id}"
                        )

                # Create new gist if auto_create is enabled
                if self._auto_create:
                    self.gist_id = await self._create_gist()
                    if self.gist_id:
                        # Update .env file with new gist ID
                        self._update_env_file()
                        self._initialized = True
                        print(f"[Database] Created new gist with ID: {self.gist_id}")
                        return True
                    else:
                        raise RuntimeError("Failed to create new gist")
                else:
                    raise RuntimeError(
                        "Gist not found and GIST_AUTO_CREATE is disabled"
                    )

            except Exception as e:
                print(f"[Database] Initialization failed: {e}")
                raise

    async def _fetch_gist(self) -> bool:
        """Fetch gist data and populate cache."""
        try:
            session = await self._get_session()
            url = f"https://api.github.com/gists/{self.gist_id}"

            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    files = data.get("files", {})

                    # Parse each file in the gist
                    for filename, file_data in files.items():
                        content = file_data.get("content", "{}")
                        try:
                            self._cache[filename] = json.loads(content)
                        except json.JSONDecodeError:
                            self._cache[filename] = {}
                        self._cache_timestamps[filename] = time.time()

                    print(
                        f"[Database] Loaded gist with {len(files)} files: {list(files.keys())}"
                    )
                    return True
                elif response.status == 404:
                    print(f"[Database] Gist {self.gist_id} not found")
                    return False
                else:
                    print(
                        f"[Database] Failed to fetch gist: {response.status} {response.reason}"
                    )
                    return False

        except Exception as e:
            print(f"[Database] Error fetching gist: {e}")
            return False

    async def _create_gist(self) -> Optional[str]:
        """Create a new gist with initial empty files."""
        try:
            session = await self._get_session()
            url = "https://api.github.com/gists"

            payload = {
                "description": "Atom Discord Bot Database",
                "public": False,
                "files": {
                    "cats.json": {"content": "{}"},
                    "qotd.json": {"content": "{}"},
                    "sticky.json": {"content": "{}"},
                    "trap.json": {"content": "{}"},
                },
            }

            async with session.post(url, json=payload) as response:
                if response.status in (200, 201):
                    data = await response.json()
                    gist_id = data.get("id")

                    # Initialize cache with empty data
                    for filename in payload["files"]:
                        self._cache[filename] = {}
                        self._cache_timestamps[filename] = time.time()

                    return gist_id
                else:
                    print(
                        f"[Database] Failed to create gist: {response.status} {response.reason}"
                    )
                    return None

        except Exception as e:
            print(f"[Database] Error creating gist: {e}")
            return None

    def _update_env_file(self):
        """Update .env file with the new gist ID."""
        env_path = ".env"
        lines = []

        if os.path.exists(env_path):
            with open(env_path, "r") as f:
                lines = f.readlines()

        # Update or add GIST_ID
        gist_line_found = False
        for i, line in enumerate(lines):
            if line.startswith("GIST_ID="):
                lines[i] = f"GIST_ID={self.gist_id}\n"
                gist_line_found = True
                break

        if not gist_line_found:
            lines.append(f"\nGIST_ID={self.gist_id}\n")

        with open(env_path, "w") as f:
            f.writelines(lines)

    def _is_cache_valid(self, filename: str) -> bool:
        """Check if cached data is still valid."""
        if filename not in self._cache_timestamps:
            return False
        age = time.time() - self._cache_timestamps[filename]
        return age < self._cache_ttl

    async def _save_gist(self, filename: str):
        """Save a specific file to the gist."""
        try:
            session = await self._get_session()
            url = f"https://api.github.com/gists/{self.gist_id}"

            content = json.dumps(self._cache.get(filename, {}), indent=2)

            payload = {
                "files": {filename: {"content": content}}
            }

            async with session.patch(url, json=payload) as response:
                if response.status in (200, 201):
                    self._cache_timestamps[filename] = time.time()
                else:
                    print(
                        f"[Database] Failed to save {filename}: {response.status} {response.reason}"
                    )

        except Exception as e:
            print(f"[Database] Error saving {filename}: {e}")

    async def _save_gist_multiple(self, filenames: list[str]):
        """Save multiple files to the gist in one request."""
        try:
            session = await self._get_session()
            url = f"https://api.github.com/gists/{self.gist_id}"

            files_payload = {}
            for filename in filenames:
                content = json.dumps(self._cache.get(filename, {}), indent=2)
                files_payload[filename] = {"content": content}

            payload = {"files": files_payload}

            async with session.patch(url, json=payload) as response:
                if response.status in (200, 201):
                    for filename in filenames:
                        self._cache_timestamps[filename] = time.time()
                else:
                    print(
                        f"[Database] Failed to save files: {response.status} {response.reason}"
                    )

        except Exception as e:
            print(f"[Database] Error saving files: {e}")

    # Public API methods

    async def get(self, filename: str, key: str, default: Any = None) -> Any:
        """Get a value from a gist file."""
        if not self._initialized:
            await self.initialize()

        # Use cache if valid, otherwise fetch fresh
        if not self._is_cache_valid(filename):
            await self._fetch_gist()

        data = self._cache.get(filename, {})
        return data.get(key, default)

    async def set(
        self, filename: str, key: str, value: Any, immediate: bool = True
    ):
        """Set a value in a gist file."""
        if not self._initialized:
            await self.initialize()

        async with self._lock:
            if filename not in self._cache:
                self._cache[filename] = {}

            self._cache[filename][key] = value
            self._cache_timestamps[filename] = time.time()

            if immediate:
                await self._save_gist(filename)

    async def get_all(self, filename: str) -> dict:
        """Get all data from a gist file."""
        if not self._initialized:
            await self.initialize()

        # Use cache if valid, otherwise fetch fresh
        if not self._is_cache_valid(filename):
            await self._fetch_gist()

        return self._cache.get(filename, {}).copy()

    async def set_all(self, filename: str, data: dict, immediate: bool = True):
        """Set all data for a gist file."""
        if not self._initialized:
            await self.initialize()

        async with self._lock:
            self._cache[filename] = data.copy()
            self._cache_timestamps[filename] = time.time()

            if immediate:
                await self._save_gist(filename)

    async def save(self, filename: str):
        """Manually trigger save for a file."""
        if not self._initialized:
            await self.initialize()

        async with self._lock:
            await self._save_gist(filename)

    async def save_multiple(self, filenames: list[str]):
        """Manually trigger save for multiple files."""
        if not self._initialized:
            await self.initialize()

        async with self._lock:
            await self._save_gist_multiple(filenames)

    def get_cached(self, filename: str, key: str, default: Any = None) -> Any:
        """Get a value from cache without fetching from gist."""
        data = self._cache.get(filename, {})
        return data.get(key, default)

    def get_all_cached(self, filename: str) -> dict:
        """Get all data from cache without fetching from gist."""
        return self._cache.get(filename, {}).copy()

    def set_cached(self, filename: str, key: str, value: Any):
        """Set a value in cache only (doesn't save to gist)."""
        if filename not in self._cache:
            self._cache[filename] = {}
        self._cache[filename][key] = value
        self._cache_timestamps[filename] = time.time()

    def set_all_cached(self, filename: str, data: dict):
        """Set all data in cache only (doesn't save to gist)."""
        self._cache[filename] = data.copy()
        self._cache_timestamps[filename] = time.time()


# Global database instance
_db: Optional[GistDatabase] = None


def get_database() -> GistDatabase:
    """Get the global database instance."""
    global _db
    if _db is None:
        _db = GistDatabase()
    return _db


async def init_database() -> GistDatabase:
    """Initialize and get the global database instance."""
    global _db
    if _db is None:
        _db = GistDatabase()
        await _db.initialize()
    return _db


async def close_database():
    """Close the global database instance."""
    global _db
    if _db is not None:
        await _db.close()
        _db = None