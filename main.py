import asyncio
import json
import os
import time

import discord
from discord import app_commands
from discord.ext import commands

from database import init_database, close_database, get_database

# Main bot entrypoint
bot = commands.Bot(
    command_prefix=">",  # Prefix for non-slash (text) commands
    intents=discord.Intents.all(),
)


def get_data_dir() -> str:
    """Get the data directory path."""
    return "/data" if os.path.exists("/data") else "data"


def get_local_json_path(filename: str) -> str:
    """Get the full path to a local JSON file."""
    return os.path.join(get_data_dir(), filename)


# Mapping of local filenames to gist filenames
MIGRATION_MAP = {
    "hourly_cats.json": "cats.json",
    "qotd.json": "qotd.json",
    "sticky.json": "sticky.json",
    "trap.json": "trap.json",
}


async def migrate_local_to_gist():
    """
    Automatically migrate local JSON files to GitHub Gist on startup.
    Only runs if local files exist and gist is not yet initialized.
    """
    data_dir = get_data_dir()
    
    # Check if any local JSON files exist
    files_to_migrate = []
    for local_file, gist_file in MIGRATION_MAP.items():
        local_path = get_local_json_path(local_file)
        if os.path.exists(local_path):
            try:
                with open(local_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data:  # Only migrate if there's actual data
                    files_to_migrate.append((local_file, gist_file, data))
            except (json.JSONDecodeError, Exception):
                continue

    if not files_to_migrate:
        return  # No local data to migrate

    print(f"[Migration] Found {len(files_to_migrate)} local data file(s) to migrate")

    try:
        db = get_database()
        # Ensure database is initialized (creates gist if needed)
        await db.initialize()

        for local_file, gist_file, data in files_to_migrate:
            try:
                await db.set_all(gist_file, data)
                entry_count = len(data) if isinstance(data, dict) else len(data)
                print(f"[Migration] Migrated {local_file} → {gist_file} ({entry_count} entries)")
            except Exception as e:
                print(f"[Migration] Failed to migrate {local_file}: {e}")

        # Rename local files to .migrated to prevent re-migration
        for local_file, _, _ in files_to_migrate:
            local_path = get_local_json_path(local_file)
            migrated_path = local_path + ".migrated"
            try:
                os.rename(local_path, migrated_path)
            except Exception:
                try:
                    os.remove(local_path)
                except Exception:
                    pass

        print("[Migration] Migration completed successfully!")

    except Exception as e:
        print(f"[Migration] Error during migration: {e}")
        print("[Migration] Continuing with empty database...")


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
    # Check for local data and migrate before loading cogs
    await migrate_local_to_gist()
    
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