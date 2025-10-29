import discord
from discord.ext import commands
from discord import app_commands
import aiohttp

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

    async def send_action(self, ctx, action: str, member: str=None):
        gif_url = await self.fetch_gif(action)
        if not gif_url:
            return await ctx.send(f"Sorry, no GIF found for `{action}`")
        
        actor = ctx.author.display_name
        if member:
            try:
                member = await commands.MemberConverter().convert(ctx, member)
            except commands.BadArgument:
                member = None
        
        if ctx.message.mentions: 
            target = ctx.message.mentions[0].display_name
        elif member:
            target = member.mention
        else:
            target = "you"

        if action in NO_TARGET_ACTIONS:
            content = ACTIONS[action].format(actor=actor)
        else:
            if target == "you":
                content = (ACTIONS[action].format(actor="", target=target)).strip().capitalize()
            else:
                content = ACTIONS[action].format(actor=actor, target=target)

        embed = discord.Embed(
            color=discord.Color.from_str("#00FFFF")
        )
        embed.set_image(url=gif_url)
        await ctx.send(content=f"_{content}_", embed=embed)

    # --- Hybrid commands for each action ---
    @commands.hybrid_command(name="shoot", description="Shoot someone")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(member="The member you want to shoot at")
    async def shoot(self, ctx: commands.Context, member: str=None):
        await self.send_action(ctx, "shoot", member)

    @commands.hybrid_command(name="shrug", description="Shrug at someone")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(member="The member you want to shrug at")
    async def shrug(self, ctx: commands.Context, member: str=None):
        await self.send_action(ctx, "shrug", member)

    @commands.hybrid_command(name="stare", description="Stare at someone")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(member="The member you want to stare at")
    async def stare(self, ctx: commands.Context, member: str=None):
        await self.send_action(ctx, "stare", member)

    @commands.hybrid_command(name="wave", description="Wave at someone")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(member="The member you want to wave at")
    async def wave(self, ctx: commands.Context, member: str=None):
        await self.send_action(ctx, "wave", member)

    @commands.hybrid_command(name="poke", description="Poke someone")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(member="The member you want to poke")
    async def poke(self, ctx: commands.Context, member: str=None):
        await self.send_action(ctx, "poke", member)

    @commands.hybrid_command(name="smile", description="Smile at someone")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(member="The member you want to smile at")
    async def smile(self, ctx: commands.Context, member: str=None):
        await self.send_action(ctx, "smile", member)

    @commands.hybrid_command(name="peck", description="Peck someone")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(member="The member you want to peck")
    async def peck(self, ctx: commands.Context, member: str=None):
        await self.send_action(ctx, "peck", member)

    @commands.hybrid_command(name="wink", description="Wink at someone")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(member="The member you want to wink at")
    async def wink(self, ctx: commands.Context, member: str=None):
        await self.send_action(ctx, "wink", member)

    @commands.hybrid_command(name="blush", description="Blush at someone")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(member="The member you want to blush at")
    async def blush(self, ctx: commands.Context, member: str=None):
        await self.send_action(ctx, "blush", member)

    @commands.hybrid_command(name="smug", description="Look smug at someone")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(member="The member you want to look smug at")
    async def smug(self, ctx: commands.Context, member: str=None):
        await self.send_action(ctx, "smug", member)

    @commands.hybrid_command(name="tickle", description="Tickle someone")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(member="The member you want to tickle")
    async def tickle(self, ctx: commands.Context, member: str=None):
        await self.send_action(ctx, "tickle", member)

    @commands.hybrid_command(name="yeet", description="Yeet someone")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(member="The member you want to yeet")
    async def yeet(self, ctx: commands.Context, member: str=None):
        await self.send_action(ctx, "yeet", member)

    @commands.hybrid_command(name="highfive", description="Highfive someone")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(member="The member you want to highfive")
    async def highfive(self, ctx: commands.Context, member: str=None):
        await self.send_action(ctx, "highfive", member)

    @commands.hybrid_command(name="feed", description="Feed someone")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(member="The member you want to feed")
    async def feed(self, ctx: commands.Context, member: str=None):
        await self.send_action(ctx, "feed", member)

    @commands.hybrid_command(name="bite", description="Bite someone")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(member="The member you want to bite")
    async def bite(self, ctx: commands.Context, member: str=None):
        await self.send_action(ctx, "bite", member)

    @commands.hybrid_command(name="nom", description="Nom on someone")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(member="The member you want to nom on")
    async def nom(self, ctx: commands.Context, member: str=None):
        await self.send_action(ctx, "nom", member)

    @commands.hybrid_command(name="facepalm", description="Facepalm at someone")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(member="The member you want to facepalm at")
    async def facepalm(self, ctx: commands.Context, member: str=None):
        await self.send_action(ctx, "facepalm", member)

    @commands.hybrid_command(name="cuddle", description="Cuddle someone")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(member="The member you want to cuddle")
    async def cuddle(self, ctx: commands.Context, member: str=None):
        await self.send_action(ctx, "cuddle", member)

    @commands.hybrid_command(name="kick", description="Kick someone")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(member="The member you want to kick")
    async def kick(self, ctx: commands.Context, member: str=None):
        await self.send_action(ctx, "kick", member)

    @commands.hybrid_command(name="hug", description="Hug someone")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(member="The member you want to hug")
    async def hug(self, ctx: commands.Context, member: str=None):
        await self.send_action(ctx, "hug", member)

    @commands.hybrid_command(name="pat", description="Pat someone")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(member="The member you want to pat")
    async def pat(self, ctx: commands.Context, member: str=None):
        await self.send_action(ctx, "pat", member)

    @commands.hybrid_command(name="angry", description="Be angry at someone")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(member="The member you want to be angry at")
    async def angry(self, ctx: commands.Context, member: str=None):
        await self.send_action(ctx, "angry", member)

    @commands.hybrid_command(name="nod", description="Nod at someone")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(member="The member you want to nod at")
    async def nod(self, ctx: commands.Context, member: str=None):
        await self.send_action(ctx, "nod", member)

    @commands.hybrid_command(name="nope", description="Say nope to someone")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(member="The member you want to say nope to")
    async def nope(self, ctx: commands.Context, member: str=None):
        await self.send_action(ctx, "nope", member)

    @commands.hybrid_command(name="kiss", description="Kiss someone")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(member="The member you want to kiss")
    async def kiss(self, ctx: commands.Context, member: str=None):
        await self.send_action(ctx, "kiss", member)

    @commands.hybrid_command(name="dance", description="Dance with someone")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(member="The member you want to dance with")
    async def dance(self, ctx: commands.Context, member: str=None):
        await self.send_action(ctx, "dance", member)

    @commands.hybrid_command(name="punch", description="Punch someone")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(member="The member you want to punch")
    async def punch(self, ctx: commands.Context, member: str=None):
        await self.send_action(ctx, "punch", member)

    @commands.hybrid_command(name="handshake", description="Shake hands with someone")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(member="The member you want to shake hands with")
    async def handshake(self, ctx: commands.Context, member: str=None):
        await self.send_action(ctx, "handshake", member)

    @commands.hybrid_command(name="slap", description="Slap someone")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(member="The member you want to slap")
    async def slap(self, ctx: commands.Context, member: str=None):
        await self.send_action(ctx, "slap", member)

    @commands.hybrid_command(name="pout", description="Pout at someone")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(member="The member you want to pout at")
    async def pout(self, ctx: commands.Context, member: str=None):
        await self.send_action(ctx, "pout", member)

    @commands.hybrid_command(name="handhold", description="Hold hands with someone")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(member="The member you want to hold hands with")
    async def handhold(self, ctx: commands.Context, member: str=None):
        await self.send_action(ctx, "handhold", member)

    @commands.hybrid_command(name="thumbsup", description="Give a thumbs up to someone")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(member="The member you want to give a thumbs up to")
    async def thumbsup(self, ctx: commands.Context, member: str=None):
        await self.send_action(ctx, "thumbsup", member)

    @commands.hybrid_command(name="laugh", description="Laugh at someone")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(member="The member you want to laugh at")
    async def laugh(self, ctx: commands.Context, member: str=None):
        await self.send_action(ctx, "laugh", member)

    @commands.hybrid_command(name="lurk", description="Lurk around")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def lurk(self, ctx: commands.Context):
        await self.send_action(ctx, "lurk")

    @commands.hybrid_command(name="sleep", description="Sleep")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def sleep(self, ctx: commands.Context):
        await self.send_action(ctx, "sleep")

    @commands.hybrid_command(name="think", description="Think")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def think(self, ctx: commands.Context):
        await self.send_action(ctx, "think")

    @commands.hybrid_command(name="bored", description="Be bored")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def bored(self, ctx: commands.Context):
        await self.send_action(ctx, "bored")

    @commands.hybrid_command(name="yawn", description="Yawn")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def yawn(self, ctx: commands.Context):    
        await self.send_action(ctx, "yawn")

    @commands.hybrid_command(name="happy", description="Be happy")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def happy(self, ctx: commands.Context):
        await self.send_action(ctx, "happy")

    @commands.hybrid_command(name="run", description="Run")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def run(self, ctx: commands.Context):
        await self.send_action(ctx, "run")

    @commands.hybrid_command(name="cry", description="Cry")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def cry(self, ctx: commands.Context):
        await self.send_action(ctx, "cry")

async def setup(bot: commands.Bot):
    await bot.add_cog(Gifs(bot))
