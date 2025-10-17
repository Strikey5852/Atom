import discord
from discord.ext import commands
from discord import app_commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import aiohttp

class Cats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler()
        self.channel_id = 1428631492011233370

    @commands.Cog.listener()
    async def on_ready(self):
        # avoid adding/starting multiple times
        if not self.scheduler.get_job("post_cat_pic"):
            self.scheduler.add_job(self.post_cat_pic, "interval", hours=1, id="cat_pic")
        if not self.scheduler.running:
            self.scheduler.start()
            print("Cats scheduler started.")

    async def post_cat_pic(self):
        await self.bot.wait_until_ready()
        channel = self.bot.get_channel(self.channel_id)
        if not channel:
            return

        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.thecatapi.com/v1/images/search") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    image_url = data[0]["url"]

                    embed = discord.Embed(
                        title="Hourly Cat Pic :3",
                        color=discord.Color.from_str("#00FFFF")
                    )
                    embed.set_image(url=image_url)
                    await channel.send(embed=embed)
                    
    @app_commands.command(name="cat", description="Sends a random cat picture on demand")
    async def cat(self, interaction: discord.Interaction):
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

                    await interaction.response.send_message(embed=embed)
                else:
                    await interaction.response.send_message("Couldn’t fetch a cat pic right now ;-;", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Cats(bot))
