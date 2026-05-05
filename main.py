import asyncio
import os
import time

import discord
from discord import app_commands
from discord.ext import commands

from database import init_database, close_database

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
    await load_cogs(bot)
    TOKEN = os.getenv("TOKEN")
    if not TOKEN:
        raise RuntimeError("TOKEN environment variable is not set")
    
    try:
        await bot.start(TOKEN)
    finally:
        # Clean up database connection
        await close_database()


asyncio.run(main())