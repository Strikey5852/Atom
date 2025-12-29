import os
import json
import aiohttp
import discord
from discord.ext import commands
from discord import app_commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

class Cats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler()
        
        # Path Setup
        self.data_dir = "/data" if os.path.exists("/data") else "data"
        self.cats_json_path = os.path.join(self.data_dir, "cats.json")
        
        self.settings = self.load_settings()
        
        self.session = aiohttp.ClientSession()

    def load_settings(self) -> dict:
        if not os.path.exists(self.cats_json_path):
            return {}
        try:
            with open(self.cats_json_path, "r", encoding="utf-8") as jf:
                return json.load(jf) or {}
        except Exception:
            return {}

    def save_settings(self):
        os.makedirs(os.path.dirname(self.cats_json_path), exist_ok=True)
        with open(self.cats_json_path, "w", encoding="utf-8") as jf:
            json.dump(self.settings, jf, indent=2)

    @commands.Cog.listener()
    async def on_ready(self):
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
        self.save_settings()
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

async def setup(bot):
    await bot.add_cog(Cats(bot))