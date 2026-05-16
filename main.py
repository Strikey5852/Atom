import asyncio
import os
import random
import time

import aiohttp
import server

import discord
from discord import app_commands
from discord.ext import commands

from database import init_database, close_database

# Maximum number of consecutive connection attempts before giving up
MAX_RETRIES = 10
# Base delay in seconds for exponential backoff
BASE_DELAY = 5


async def start_bot_with_retry(token: str) -> None:
    """Attempt to connect to Discord with exponential backoff + jitter.

    Handles temporary IP bans / rate limits from Render's shared egress IPs
    by waiting progressively longer between attempts.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            await bot.start(token)
            return  # Connected successfully
        except (discord.errors.ConnectionClosed,
                discord.errors.GatewayNotFound,
                discord.errors.HTTPException,
                OSError,
                aiohttp.ClientError) as exc:
            if attempt == MAX_RETRIES:
                print(f"[Main] All {MAX_RETRIES} connection attempts exhausted. Giving up.")
                raise

            delay = BASE_DELAY * (2 ** (attempt - 1)) + random.uniform(0, 2)
            print(
                f"[Main] Connection attempt {attempt}/{MAX_RETRIES} failed: {exc}\n"
                f"       Retrying in {delay:.1f} seconds..."
            )
            await asyncio.sleep(delay)
        except Exception:
            # For unexpected errors, re-raise immediately
            raise

# Main bot entrypoint
bot = commands.Bot(
    command_prefix=">",  # Prefix for non-slash (text) commands
    intents=discord.Intents.all(),
)


@bot.event
async def on_ready():
    # Initialize database
    try:
        await init_database()
        print("[Main] Database initialized successfully")
    except Exception as e:
        print(f"[Main] Failed to initialize database: {e}")
        return

    print(f"Logged in as {bot.user}")

    # Sync commands after bot is ready
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
        # Print out the names of synced commands for verification
        print("Synced command names:", [cmd.name for cmd in synced])
    except Exception as e:
        print(f"Error syncing commands: {e}")


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
    for root, _, files in os.walk("cogs"):
        for file in files:
            if file.endswith(".py"):
                module = (root + "\\" + file)[:-3].replace("\\", ".")
                await bot.load_extension(module)
                print(f"Loaded cog: {module}")


async def main():
    # Start the Flask health-check server in a background thread
    server.start()

    await load_cogs(bot)
    TOKEN = os.getenv("TOKEN")
    if not TOKEN:
        raise RuntimeError("TOKEN environment variable is not set")
    
    try:
        await start_bot_with_retry(TOKEN)
    finally:
        # Clean up database connection
        await close_database()


asyncio.run(main())