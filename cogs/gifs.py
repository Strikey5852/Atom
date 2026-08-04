import asyncio
import logging
from typing import Optional

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from shared_http import get_shared_session

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Action definitions — three categories:
#   MUTUAL_ACTIONS: optional target (falls back to "you")
#   SOLO_ACTIONS:   never take a target
#   BOTH_ACTIONS:   optional target (mutual_template, solo_template)
# ──────────────────────────────────────────────

MUTUAL_ACTIONS = {
    "shoot": "{actor} shoots at {target}",
    "poke": "{actor} pokes {target}",
    "tickle": "{actor} tickles {target}",
    "yeet": "{actor} yeets {target}",
    "highfive": "{actor} highfives {target}",
    "feed": "{actor} feeds {target}",
    "bite": "{actor} bites {target}",
    "nom": "{actor} noms on {target}",
    "cuddle": "{actor} cuddles {target}",
    "kick": "{actor} kicks {target}",
    "hug": "{actor} hugs {target}",
    "kiss": "{actor} kisses {target}",
    "punch": "{actor} punches {target}",
    "handshake": "{actor} shakes hands with {target}",
    "slap": "{actor} slaps {target}",
    "handhold": "{actor} holds hands with {target}",
    "peck": "{actor} pecks {target}",
    "carry": "{actor} carries {target}",
    "kabedon": "{actor} kabedons {target}",
    "baka": "{actor} calls {target} a baka",
    "bonk": "{actor} bonks {target}",
    "lappillow": "{actor} uses {target} as a lap pillow",
    "blowkiss": "{actor} blows a kiss to {target}",
    "pat": "{actor} pats {target}",
}

SOLO_ACTIONS = {
    "lurk": "{actor} lurks",
    "sleep": "{actor} sleeps",
    "clap": "{actor} claps",
    "shrug": "{actor} shrugs",
    "confused": "{actor} is confused",
    "sip": "{actor} sips",
    "blush": "{actor} blushes",
    "smug": "{actor} looks smug",
    "think": "{actor} thinks",
    "wag": "{actor} wags their tail",
    "teehee": "{actor} giggles teehee",
    "shocked": "{actor} is shocked",
    "bleh": "{actor} blehs",
    "bored": "{actor} is bored",
    "nya": "{actor} says nya~",
    "yawn": "{actor} yawns",
    "facepalm": "{actor} facepalms",
    "happy": "{actor} is happy",
    "angry": "{actor} is angry",
    "spin": "{actor} spins",
    "shake": "{actor} shakes",
    "run": "{actor} runs",
    "cry": "{actor} cries",
    "salute": "{actor} salutes",
    "tableflip": "{actor} flips the table",
}

# Each entry is a tuple: (mutual_template, solo_template)
BOTH_ACTIONS = {
    "stare": ("{actor} stares at {target}", "{actor} stares"),
    "wave": ("{actor} waves at {target}", "{actor} waves"),
    "smile": ("{actor} smiles at {target}", "{actor} smiles"),
    "wink": ("{actor} winks at {target}", "{actor} winks"),
    "nod": ("{actor} nods at {target}", "{actor} nods"),
    "nope": ("{actor} says nope to {target}", "{actor} says nope"),
    "dance": ("{actor} dances with {target}", "{actor} dances"),
    "laugh": ("{actor} laughs at {target}", "{actor} laughs"),
    "pout": ("{actor} pouts at {target}", "{actor} pouts"),
    "thumbsup": ("{actor} gives a thumbs up to {target}", "{actor} gives a thumbs up"),
}

NEKOS_BASE = "https://nekos.best/api/v2/"


def _create_action_command(action: str, target_mode: str):
    """Create a hybrid command for a gif action.

    target_mode: "required" | "none" | "optional" — all take an
    optional member parameter; when omitted the action is directed
    at the user themselves.
    """
    if target_mode == "none":
        async def command(self, ctx: commands.Context):
            await self.send_action(ctx, action)
    else:
        async def command(self, ctx: commands.Context, member: Optional[discord.Member] = None):
            await self.send_action(ctx, action, member)

    command = app_commands.allowed_installs(guilds=True, users=True)(command)
    command = app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)(command)
    command.__name__ = f"{action}_command"
    # Important: __qualname__ must NOT end with '<locals>' so that
    # app_commands.is_inside_class() returns True, causing discord.py
    # to skip both 'self' AND 'ctx' when extracting slash command parameters.
    command.__qualname__ = f"Gifs.{action}_command"

    return commands.hybrid_command(name=action)(command)


class Gifs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        """Called when the cog is loaded. Register dynamic commands here
        because add_command() is not available in __init__."""
        self._register_dynamic_commands()
        total = len(MUTUAL_ACTIONS) + len(SOLO_ACTIONS) + len(BOTH_ACTIONS)
        logger.info("[Gifs] Registered %d dynamic action commands", total)

    @property
    def session(self):
        """Get the shared aiohttp session."""
        return get_shared_session()

    def _register_dynamic_commands(self):
        """Register all action commands dynamically from the action dicts.

        In discord.py 2.6+, add_command() is a Bot method, not a Cog method.
        The Cog._inject() method calls cog_load() first, then iterates
        __cog_commands__ to register commands with the bot. So we add the
        dynamically created commands to the cog's __cog_commands__ tuple here.

        Note: We do NOT add to __cog_app_commands__ because bot.add_command()
        for hybrid commands already registers the app_command to the tree.
        Adding to both would cause CommandAlreadyRegistered errors.
        """
        new_commands = []

        for action in MUTUAL_ACTIONS:
            new_commands.append(_create_action_command(action, target_mode="required"))
        for action in SOLO_ACTIONS:
            new_commands.append(_create_action_command(action, target_mode="none"))
        for action in BOTH_ACTIONS:
            new_commands.append(_create_action_command(action, target_mode="optional"))

        # Add to the cog's command list (__cog_commands__ is a tuple)
        self.__cog_commands__ = self.__cog_commands__ + tuple(new_commands)

    async def fetch_gif(self, action: str) -> str:
        """Fetch a random GIF URL for the given action from nekos.best"""
        url = f"{NEKOS_BASE}{action}"
        logger.info("[Gifs] fetch_gif called for action='%s' URL='%s'", action, url)

        for attempt in (1, 2):
            try:
                session = self.session
                logger.debug("[Gifs] Attempt %d: GET %s", attempt, url)
                async with session.get(
                    url, timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status != 200:
                        logger.warning(
                            "[Gifs] Attempt %d: Non-200 status for %s: %d %s",
                            attempt, url, resp.status, resp.reason,
                        )
                        return None
                    data = await resp.json()
                    results = data.get("results", [])
                    if not results:
                        logger.warning(
                            "[Gifs] Attempt %d: 200 OK but 'results' is empty/missing. Raw keys: %s",
                            attempt, list(data.keys()),
                        )
                        return None
                    gif_url = results[0].get("url")
                    if not gif_url:
                        logger.warning(
                            "[Gifs] Attempt %d: 'results[0]' has no 'url'. Result keys: %s",
                            attempt, list(results[0].keys()),
                        )
                        return None
                    logger.info("[Gifs] Attempt %d: Got GIF URL: %s", attempt, gif_url)
                    return gif_url
            except (aiohttp.ClientError, asyncio.TimeoutError, IndexError, KeyError) as exc:
                logger.warning(
                    "[Gifs] Attempt %d: Exception while fetching %s: %s: %s",
                    attempt, url, type(exc).__name__, exc,
                )
                if attempt == 1:
                    logger.info("[Gifs] Retrying...")
                else:
                    logger.error("[Gifs] Retry also failed for %s. Giving up.", url)
        return None

    async def send_action(self, ctx, action: str, member: Optional[discord.Member] = None):
        logger.info(
            "[Gifs] send_action invoked: action='%s' author=%s guild=%s channel=%s",
            action, ctx.author, getattr(ctx.guild, "name", None),
            getattr(ctx.channel, "name", getattr(ctx.channel, "id", None)),
        )
        gif_url = await self.fetch_gif(action)
        if not gif_url:
            logger.warning("[Gifs] No GIF URL found for action='%s'. Sending fallback message.", action)
            return await ctx.send(f"Sorry, no GIF found for `{action}`")

        logger.debug("[Gifs] Sending embed with GIF for action='%s' URL='%s'", action, gif_url)

        actor = ctx.author.display_name
        target = None

        # Resolve the target from the member argument (works for both prefix & slash)
        if member:
            if isinstance(member, discord.Member):
                target = member.mention
            else:
                try:
                    converted = await commands.MemberConverter().convert(ctx, member)
                    target = converted.mention
                except commands.BadArgument:
                    pass  # fall back to no target

        # Determine which template to use based on action category
        if action in MUTUAL_ACTIONS:
            # Mututal action — target defaults to "you" when not provided
            if target:
                content = MUTUAL_ACTIONS[action].format(actor=actor, target=target)
            else:
                content = MUTUAL_ACTIONS[action].format(actor=actor, target="you")
        elif action in SOLO_ACTIONS:
            content = SOLO_ACTIONS[action].format(actor=actor)
        else:  # BOTH_ACTIONS
            mutual_tpl, solo_tpl = BOTH_ACTIONS[action]
            if target:
                content = mutual_tpl.format(actor=actor, target=target)
            else:
                content = solo_tpl.format(actor=actor)

        embed = discord.Embed(
            color=discord.Color.from_str("#00FFFF")
        )
        embed.set_image(url=gif_url)
        await ctx.send(content=f"***{content}***", embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Gifs(bot))