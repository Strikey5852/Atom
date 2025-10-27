import discord
from discord.ext import commands
import os
import time
import asyncio


# Main bot entrypoint
bot = commands.Bot(
    command_prefix=">",  # Prefix for non-slash (text) commands
    intents=discord.Intents.all()
)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    
    # Sync commands after bot is ready
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
        # Print out the names of synced commands for verification
        print("Synced command names:", [cmd.name for cmd in synced])
    except Exception as e:
        print(f"Error syncing commands: {e}")

@bot.tree.command(name="ping", description="Check bot latency")
async def ping(interaction: discord.Interaction):
    # Slash command to report latency
    start = time.perf_counter()
    await interaction.response.send_message("Pinging...")
    end = time.perf_counter()
    round_trip = (end - start) * 1000  # ms
    await interaction.edit_original_response(
        content=(
            f"Pong!\n"
            f"WebSocket latency: `{bot.latency * 1000:.2f} ms`\n"
            f"Round-trip time: `{round_trip:.2f} ms`"
        )
    )

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
    await bot.start(TOKEN)

asyncio.run(main())
