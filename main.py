import discord
from discord.ext import commands
import os
import time
import asyncio

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    
    # Sync commands after bot is ready
    synced = await bot.tree.sync()
    print(f"Synced {len(synced)} commands")

@bot.tree.command(name="ping", description="Check bot latency")
async def ping(interaction: discord.Interaction):
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
    await bot.start(TOKEN)

asyncio.run(main())
