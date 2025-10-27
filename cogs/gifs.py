import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import random

# Actions that require a target
TARGET_ACTIONS = {
    "shoot": "{actor} shoots at {target}",
    "shrug": "{actor} shrugs at {target}",
    "stare": "{actor} stares at {target}",
    "wave": "{actor} waves at {target}",
    "poke": "{actor} pokes {target}",
    "smile": "{actor} smiles at {target}",
    "peck": "{actor} pecks {target}",
    "wink": "{actor} winks at {target}",
    "blush": "{actor} blushes at {target}",
    "smug": "{actor} looks smug at {target}",
    "tickle": "{actor} tickles {target}",
    "yeet": "{actor} yeets {target}",
    "highfive": "{actor} highfives {target}",
    "feed": "{actor} feeds {target}",
    "bite": "{actor} bites {target}",
    "nom": "{actor} noms on {target}",
    "facepalm": "{actor} facepalms at {target}",
    "cuddle": "{actor} cuddles {target}",
    "kick": "{actor} kicks {target}",
    "hug": "{actor} hugs {target}",
    "pat": "{actor} pats {target}",
    "angry": "{actor} is angry at {target}",
    "nod": "{actor} nods at {target}",
    "nope": "{actor} says nope to {target}",
    "kiss": "{actor} kisses {target}",
    "dance": "{actor} dances with {target}",
    "punch": "{actor} punches {target}",
    "handshake": "{actor} shakes hands with {target}",
    "slap": "{actor} slaps {target}",
    "pout": "{actor} pouts at {target}",
    "handhold": "{actor} holds hands with {target}",
    "thumbsup": "{actor} gives a thumbs up to {target}",
    "laugh": "{actor} laughs at {target}"
}

# Actions that do NOT require a target
NO_TARGET_ACTIONS = {
    "lurk": "{actor} lurks",
    "sleep": "{actor} sleeps",
    "think": "{actor} thinks",
    "bored": "{actor} is bored",
    "yawn": "{actor} yawns",
    "happy": "{actor} is happy",
    "run": "{actor} runs",
    "cry": "{actor} cries"
}

ACTIONS = {**TARGET_ACTIONS, **NO_TARGET_ACTIONS}

NEKOS_BASE = "https://nekos.best/api/v2/"

class Gifs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()

    async def fetch_gif(self, action: str) -> str:
        """Fetch a random GIF URL for the given action from nekos.best"""
        async with self.session.get(f"{NEKOS_BASE}{action}") as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            return data.get("results", [])[0].get("url")

    async def send_action(self, ctx, action: str, member: discord.Member = None):
        gif_url = await self.fetch_gif(action)
        if not gif_url:
            return await ctx.send(f"Sorry, no GIF found for `{action}`")
        
        actor = ctx.author.display_name
        
        # Use the ACTIONS dictionary to format the sentence
        if action in NO_TARGET_ACTIONS:
            content = ACTIONS[action].format(actor=actor)
        elif member is None and action in TARGET_ACTIONS:
            content = (ACTIONS[action].format(actor="", target="you")).capitalize()  
        else:
            target = member.mention
            content = ACTIONS[action].format(actor=actor, target=target)

        embed = discord.Embed(
            color=discord.Color.from_str("#00FFFF")
        )
        embed.set_image(url=gif_url)
        await ctx.send(content=f"_{content}_", embed=embed)

    # --- Hybrid commands for each action ---
    @commands.hybrid_command(name="shoot")
    async def shoot(self, ctx: commands.Context, member: discord.Member=None):
        await self.send_action(ctx, "shoot", member)

    @commands.hybrid_command(name="shrug")
    async def shrug(self, ctx: commands.Context, member: discord.Member=None):
        await self.send_action(ctx, "shrug", member)

    @commands.hybrid_command(name="stare")
    async def stare(self, ctx: commands.Context, member: discord.Member=None):
        await self.send_action(ctx, "stare", member)

    @commands.hybrid_command(name="wave")
    async def wave(self, ctx: commands.Context, member: discord.Member=None):
        await self.send_action(ctx, "wave", member)

    @commands.hybrid_command(name="poke")
    async def poke(self, ctx: commands.Context, member: discord.Member=None):
        await self.send_action(ctx, "poke", member)

    @commands.hybrid_command(name="smile")
    async def smile(self, ctx: commands.Context, member: discord.Member=None):
        await self.send_action(ctx, "smile", member)

    @commands.hybrid_command(name="peck")
    async def peck(self, ctx: commands.Context, member: discord.Member=None):
        await self.send_action(ctx, "peck", member)

    @commands.hybrid_command(name="wink")
    async def wink(self, ctx: commands.Context, member: discord.Member=None):
        await self.send_action(ctx, "wink", member)

    @commands.hybrid_command(name="blush")
    async def blush(self, ctx: commands.Context, member: discord.Member=None):
        await self.send_action(ctx, "blush", member)

    @commands.hybrid_command(name="smug")
    async def smug(self, ctx: commands.Context, member: discord.Member=None):
        await self.send_action(ctx, "smug", member)

    @commands.hybrid_command(name="tickle")
    async def tickle(self, ctx: commands.Context, member: discord.Member=None):
        await self.send_action(ctx, "tickle", member)

    @commands.hybrid_command(name="yeet")
    async def yeet(self, ctx: commands.Context, member: discord.Member=None):
        await self.send_action(ctx, "yeet", member)

    @commands.hybrid_command(name="highfive")
    async def highfive(self, ctx: commands.Context, member: discord.Member=None):
        await self.send_action(ctx, "highfive", member)

    @commands.hybrid_command(name="feed")
    async def feed(self, ctx: commands.Context, member: discord.Member=None):
        await self.send_action(ctx, "feed", member)

    @commands.hybrid_command(name="bite")
    async def bite(self, ctx: commands.Context, member: discord.Member=None):
        await self.send_action(ctx, "bite", member)

    @commands.hybrid_command(name="nom")
    async def nom(self, ctx: commands.Context, member: discord.Member=None):
        await self.send_action(ctx, "nom", member)

    @commands.hybrid_command(name="facepalm")
    async def facepalm(self, ctx: commands.Context, member: discord.Member=None):
        await self.send_action(ctx, "facepalm", member)

    @commands.hybrid_command(name="cuddle")
    async def cuddle(self, ctx: commands.Context, member: discord.Member=None):
        await self.send_action(ctx, "cuddle", member)

    @commands.hybrid_command(name="kick")
    async def kick(self, ctx: commands.Context, member: discord.Member=None):
        await self.send_action(ctx, "kick", member)

    @commands.hybrid_command(name="hug")
    async def hug(self, ctx: commands.Context, member: discord.Member=None):
        await self.send_action(ctx, "hug", member)

    @commands.hybrid_command(name="pat")
    async def pat(self, ctx: commands.Context, member: discord.Member=None):
        await self.send_action(ctx, "pat", member)

    @commands.hybrid_command(name="angry")
    async def angry(self, ctx: commands.Context, member: discord.Member=None):
        await self.send_action(ctx, "angry", member)

    @commands.hybrid_command(name="nod")
    async def nod(self, ctx: commands.Context, member: discord.Member=None):
        await self.send_action(ctx, "nod", member)

    @commands.hybrid_command(name="nope")
    async def nope(self, ctx: commands.Context, member: discord.Member=None):
        await self.send_action(ctx, "nope", member)

    @commands.hybrid_command(name="kiss")
    async def kiss(self, ctx: commands.Context, member: discord.Member=None):
        await self.send_action(ctx, "kiss", member)

    @commands.hybrid_command(name="dance")
    async def dance(self, ctx: commands.Context, member: discord.Member=None):
        await self.send_action(ctx, "dance", member)

    @commands.hybrid_command(name="punch")
    async def punch(self, ctx: commands.Context, member: discord.Member=None):
        await self.send_action(ctx, "punch", member)

    @commands.hybrid_command(name="handshake")
    async def handshake(self, ctx: commands.Context, member: discord.Member=None):
        await self.send_action(ctx, "handshake", member)

    @commands.hybrid_command(name="slap")
    async def slap(self, ctx: commands.Context, member: discord.Member=None):
        await self.send_action(ctx, "slap", member)

    @commands.hybrid_command(name="pout")
    async def pout(self, ctx: commands.Context, member: discord.Member=None):
        await self.send_action(ctx, "pout", member)

    @commands.hybrid_command(name="handhold")
    async def handhold(self, ctx: commands.Context, member: discord.Member=None):
        await self.send_action(ctx, "handhold", member)

    @commands.hybrid_command(name="thumbsup")
    async def thumbsup(self, ctx: commands.Context, member: discord.Member=None):
        await self.send_action(ctx, "thumbsup", member)

    @commands.hybrid_command(name="laugh")
    async def laugh(self, ctx: commands.Context, member: discord.Member=None):
        await self.send_action(ctx, "laugh", member)

    @commands.hybrid_command(name="lurk")
    async def lurk(self, ctx: commands.Context):
        await self.send_action(ctx, "lurk")

    @commands.hybrid_command(name="sleep")
    async def sleep(self, ctx: commands.Context):
        await self.send_action(ctx, "sleep")

    @commands.hybrid_command(name="think")
    async def think(self, ctx: commands.Context):
        await self.send_action(ctx, "think")

    @commands.hybrid_command(name="bored")
    async def bored(self, ctx: commands.Context):
        await self.send_action(ctx, "bored")

    @commands.hybrid_command(name="yawn")
    async def yawn(self, ctx: commands.Context):    
        await self.send_action(ctx, "yawn")

    @commands.hybrid_command(name="happy")
    async def happy(self, ctx: commands.Context):
        await self.send_action(ctx, "happy")

    @commands.hybrid_command(name="run")
    async def run(self, ctx: commands.Context):
        await self.send_action(ctx, "run")

    @commands.hybrid_command(name="cry")
    async def cry(self, ctx: commands.Context):
        await self.send_action(ctx, "cry")

async def setup(bot: commands.Bot):
    await bot.add_cog(Gifs(bot))
