import os
import json
import aiohttp
import discord
from discord.ext import commands
from discord import app_commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from database import get_database

class Cats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler()
        
        self.db = get_database()
        self.filename = "cats.json"
        
        self.settings = {}  # In-memory cache
        
        self.session = aiohttp.ClientSession()

    async def load_settings(self) -> dict:
        """Load settings from the database."""
        try:
            self.settings = await self.db.get_all(self.filename)
        except Exception as e:
            print(f"[Cats] Error loading settings: {e}")
            self.settings = {}
        return self.settings

    async def save_settings(self):
        """Save settings to the database."""
        try:
            await self.db.set_all(self.filename, self.settings)
        except Exception as e:
            print(f"[Cats] Error saving settings: {e}")

    @commands.Cog.listener()
    async def on_ready(self):
        # Load settings when bot is ready
        await self.load_settings()
        
        if not self.scheduler.running:
            self.scheduler.add_job(
                self.post_cat_pic,
                CronTrigger(minute=0, timezone="Asia/Kolkata"),
                id="post_cat_pic",
                replace_existing=True
            )
            self.scheduler.start()
            print("Cat Scheduler started.")

    async def post_cat_pic(self):
        """Post a cat picture to all configured channels."""
        await self.bot.wait_until_ready()
        
        # Fetch image once, reuse for all guilds
        async with self.session.get("https://api.thecatapi.com/v1/images/search") as resp:
            if resp.status != 200:
                return
            data = await resp.json()
            image_url = data[0]["url"]

        embed = discord.Embed(
            title="Hourly Cat Pic :3",
            color=discord.Color.from_str("#00FFFF")
        )
        embed.set_image(url=image_url)

        # Iterate through cached settings
        for guild_id, guild_data in self.settings.items():
            guild = self.bot.get_guild(int(guild_id))
            if not guild:
                continue
            channel_id = guild_data.get("channel_id")
            if not channel_id:
                continue

            channel = self.bot.get_channel(channel_id)
            if channel:
                try:
                    await channel.send(embed=embed)
                except discord.Forbidden:
                    print(f"Missing permissions to post cats in {channel_id}")
                except Exception:
                    pass

    @commands.hybrid_command(name="cat", description="Sends a random cat picture on demand")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def cat(self, ctx):
        async with self.session.get("https://api.thecatapi.com/v1/images/search", timeout=10) as resp:
            if resp.status == 200:
                data = await resp.json()
                image_url = data[0]["url"]
                embed = discord.Embed(title="Random Cat Pic :3", color=discord.Color.from_str("#00FFFF"))
                embed.set_image(url=image_url)
                await ctx.send(embed=embed)
            else:
                await ctx.send("Couldn't fetch a cat pic right now ;-;", ephemeral=True)

    @commands.hybrid_command(name="setcatchannel", description="Set the channel where hourly cat pictures will be posted")
    @commands.has_permissions(manage_guild=True)
    @app_commands.allowed_installs(guilds=True, users=False)
    @commands.guild_only()
    @app_commands.describe(channel="The text channel to post hourly cat pictures in")    
    async def set_cat_channel(self, ctx, channel: discord.TextChannel):
        self.settings[str(ctx.guild.id)] = {"channel_id": channel.id}
        await self.save_settings()
        await ctx.send(f"Cat pictures will now be posted in {channel.mention}")

    @commands.hybrid_command(name="catinfo", description="Show the cat channel settings for this server")
    @commands.has_permissions(manage_guild=True)
    @app_commands.allowed_installs(guilds=True, users=False)
    @commands.guild_only()
    async def cat_info(self, ctx):
        guild_settings = self.settings.get(str(ctx.guild.id), {})
        channel_id = guild_settings.get("channel_id")

        if channel_id:
            channel = self.bot.get_channel(channel_id)
            mention = channel.mention if channel else f"Deleted Channel ({channel_id})"
            await ctx.send(f"Cat pictures are being posted in {mention}")
        else:
            await ctx.send("No cat channel has been set for this server.")

    async def cog_unload(self):
        """Clean up when cog is unloaded."""
        if self.session and not self.session.closed:
            await self.session.close()

async def setup(bot):
    await bot.add_cog(Cats(bot))