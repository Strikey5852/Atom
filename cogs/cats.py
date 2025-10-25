import discord
from discord.ext import commands
from discord import app_commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import aiohttp
import os
import json

class Cats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler()
        # Decide where to store JSON files. Use Railway persistent volume if available.
        if os.path.exists("/data"):
            print('yay')
            DATA_DIR = "/data"
        else:
            DATA_DIR = "data"
            print('nay')

        self.cats_json_path = f"{DATA_DIR}/cats.json"  # Stores per-guild channel settings

    def _ensure_cats_json(self):
        """Initialize the JSON storage file if it doesn't exist."""
        os.makedirs(os.path.dirname(self.cats_json_path), exist_ok=True)
        if not os.path.exists(self.cats_json_path):
            with open(self.cats_json_path, "w", encoding="utf-8") as jf:
                json.dump({}, jf)

    def load_settings(self) -> dict:
        """Load and return the guild settings from storage."""
        self._ensure_cats_json()
        try:
            with open(self.cats_json_path, "r", encoding="utf-8") as jf:
                return json.load(jf) or {}
        except Exception:
            return {}

    def save_settings(self, data: dict):
        """Save the guild settings to storage."""
        os.makedirs(os.path.dirname(self.cats_json_path), exist_ok=True)
        with open(self.cats_json_path, "w", encoding="utf-8") as jf:
            json.dump(data, jf, indent=2)

    def get_cat_channel(self, guild_id: int) -> int:
        """Get the configured cat channel for a guild."""
        settings = self.load_settings()
        return settings.get(str(guild_id), {}).get("channel_id")

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.scheduler.running:
            # Schedule to run at the start of every hour IST
            self.scheduler.add_job(
                self.post_cat_pic,
                CronTrigger(minute=0, timezone="Asia/Kolkata"),
                id="post_cat_pic"
            )
            self.scheduler.start()
            print("Cats scheduler started.")

    async def post_cat_pic(self):
        """Post a cat picture to all configured guild channels."""
        await self.bot.wait_until_ready()
        settings = self.load_settings()
        
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.thecatapi.com/v1/images/search") as resp:
                if resp.status != 200:
                    return
                    
                data = await resp.json()
                image_url = data[0]["url"]
                embed = discord.Embed(
                    title="Hourly Cat Pic :3",
                    color=discord.Color.from_str("#00FFFF")
                )
                embed.set_image(url=image_url)

                # Send to each configured guild channel
                for guild_id, guild_data in settings.items():
                    channel_id = guild_data.get("channel_id")
                    if channel_id:
                        channel = self.bot.get_channel(channel_id)
                        if channel:
                            try:
                                await channel.send(embed=embed)
                            except Exception:
                                pass  # Skip if can't send to this channel

    @commands.hybrid_command(name="cat", description="Sends a random cat picture on demand")
    async def cat(self, ctx):
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.thecatapi.com/v1/images/search") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    image_url = data[0]["url"]

                    embed = discord.Embed(
                        title="Random Cat Pic :3",
                        color=discord.Color.from_str("#00FFFF")
                    )
                    embed.set_image(url=image_url)
                    
                    # If it's an interaction, respond to it
                    interaction = getattr(ctx, "interaction", None)
                    if interaction is not None:
                        await interaction.response.send_message(embed=embed)
                    else:
                        await ctx.send(embed=embed)
                else:
                    # Handle error response
                    error_msg = "Couldn't fetch a cat pic right now ;-;"
                    if getattr(ctx, "interaction", None):
                        await ctx.interaction.response.send_message(error_msg, ephemeral=True)
                    else:
                        await ctx.send(error_msg)

    @commands.hybrid_command(name="setcatchannel", description="Set the channel where hourly cat pictures will be posted")
    @commands.has_permissions(administrator=True)
    async def set_cat_channel(self, ctx, channel: discord.TextChannel):
        """Set the channel for hourly cat pictures in this server."""
        if ctx.guild is None:
            await ctx.send("This command must be used in a server.")
            return

        # Save the channel setting for this guild
        settings = self.load_settings()
        settings[str(ctx.guild.id)] = {"channel_id": channel.id}
        self.save_settings(settings)

        await ctx.send(f"Cat pictures will now be posted in {channel.mention}")

    @commands.hybrid_command(name="catinfo", description="Show the cat channel settings for this server")
    @commands.has_permissions(administrator=True)
    async def cat_info(self, ctx):
        """Show the current cat channel configuration for this server."""
        if ctx.guild is None:
            await ctx.send("This command must be used in a server.")
            return

        settings = self.load_settings()
        guild_settings = settings.get(str(ctx.guild.id), {})
        channel_id = guild_settings.get("channel_id")

        if channel_id:
            channel = self.bot.get_channel(channel_id)
            if channel:
                await ctx.send(f"Cat pictures are being posted in {channel.mention}")
            else:
                await ctx.send("Cat channel is set but no longer accessible.")
        else:
            await ctx.send("No cat channel has been set for this server.")

async def setup(bot):
    await bot.add_cog(Cats(bot))
