import asyncio
import logging
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from dotenv import load_dotenv

import discord
from discord import app_commands
from discord.ext import commands

from database import init_database, close_database
from shared_http import close_shared_session

# Load environment variables from .env file
load_dotenv()

# ──────────────────────────────────────────────
# Logging Configuration
# ──────────────────────────────────────────────
# Global defaults, overridable via environment variables:
#   COG_LOG_LEVEL=<level>              — default level for ALL cog loggers (DEBUG/INFO/WARNING/ERROR)
#   COG_LOG_LEVEL_<COG>=<level>        — per-cog override (e.g. COG_LOG_LEVEL_GIFS=DEBUG)
#
# Examples:
#   COG_LOG_LEVEL=WARNING              # Quiet globally
#   COG_LOG_LEVEL_GIFS=DEBUG           # Verbose only for the gifs cog
#   COG_LOG_LEVEL_TRAP=ERROR           # Only errors from the trap cog

DEFAULT_COG_LOG_LEVEL = os.getenv("COG_LOG_LEVEL", "INFO").upper()
ALL_COG_NAMES = ["cats", "dice", "gifs", "qotd", "sticky", "trap"]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger("main")

# Apply per-cog log levels
for cog_name in ALL_COG_NAMES:
    env_key = f"COG_LOG_LEVEL_{cog_name.upper()}"
    level_name = os.getenv(env_key, DEFAULT_COG_LOG_LEVEL).upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.getLogger(f"cogs.{cog_name}").setLevel(level)
    logger.info("Log level for cogs.%s: %s", cog_name, logging.getLevelName(level))

HEALTH_CHECK_PORT = int(os.getenv("PORT", 8000))
_HEALTH_SERVER = None
_HEALTH_LOCK = threading.Lock()


class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in {"/", "/health", "/healthz"}:
            payload = b'{"status":"ok"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        self.send_response(404)
        self.end_headers()

    do_HEAD = do_GET  # Respond to HEAD requests the same way as GET

    def log_message(self, format, *args):
        logger.debug("Health check request: %s", format % args)


def start_health_check_server() -> None:
    global _HEALTH_SERVER

    with _HEALTH_LOCK:
        if _HEALTH_SERVER is not None:
            return

        server = ThreadingHTTPServer(("0.0.0.0", HEALTH_CHECK_PORT), HealthCheckHandler)
        _HEALTH_SERVER = server

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("Health check server started on port %d", HEALTH_CHECK_PORT)


def stop_health_check_server() -> None:
    global _HEALTH_SERVER

    with _HEALTH_LOCK:
        if _HEALTH_SERVER is None:
            return

        server = _HEALTH_SERVER
        _HEALTH_SERVER = None

    server.shutdown()
    server.server_close()
    logger.info("Health check server stopped on port %d", HEALTH_CHECK_PORT)


# Main bot entrypoint
bot = commands.Bot(
    command_prefix=">",  # Prefix for non-slash (text) commands
    intents=discord.Intents.default() | discord.Intents(message_content=True),
)


@bot.event
async def on_ready():
    # Initialize database
    try:
        await init_database()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error("Failed to initialize database: %s", e)
        return

    logger.info("Logged in as %s", bot.user)

    # Sync commands after bot is ready
    try:
        synced = await bot.tree.sync()
        logger.info("Synced %d commands", len(synced))
        # Print out the names of synced commands for verification
        logger.info("Synced command names: %s", [cmd.name for cmd in synced])
    except Exception as e:
        logger.error("Error syncing commands: %s", e)


@commands.hybrid_command(name="ping", description="Check bot latency")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def ping(ctx: commands.Context):
    # Slash command to report latency
    start = time.perf_counter()
    msg = await ctx.send("Pinging...")
    end = time.perf_counter()
    round_trip = (end - start) * 1000  # ms
    await msg.edit(
        content=(
            f"Pong!\n"
            f"WebSocket latency: `{bot.latency * 1000:.2f} ms`\n"
            f"Round-trip time: `{round_trip:.2f} ms`"
        )
    )


bot.add_command(ping)


async def load_cogs(bot):
    cogs_dir = Path("cogs")
    for path in sorted(cogs_dir.glob("*.py")):
        if path.name == "__init__.py":
            continue
        module = f"cogs.{path.stem}"
        await bot.load_extension(module)
        logger.info("Loaded cog: %s", module)


async def main():
    start_health_check_server()
    await load_cogs(bot)
    TOKEN = os.getenv("TOKEN")
    if not TOKEN:
        raise RuntimeError("TOKEN environment variable is not set")

    try:
        await bot.start(TOKEN)
    finally:
        stop_health_check_server()
        await close_database()
        await close_shared_session()


asyncio.run(main())