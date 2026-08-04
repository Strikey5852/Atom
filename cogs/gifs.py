import asyncio
import logging
from typing import Optional

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from shared_http import get_shared_session

logger = logging.getLogger(__name__)

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


def _make_description(template: str) -> str:
    """Build a command description from the action template."""
    desc = template.format(actor="", target="someone").strip()
    return desc[0].upper() + desc[1:] if desc else "Send a GIF"


def _create_action_command(action: str, template: str, needs_target: bool):
    """Create a hybrid command for a gif action."""
    description = _make_description(template)

    if needs_target:
        async def command(self, ctx, member: Optional[str] = None):
            await self.send_action(ctx, action, member)

        command = app_commands.describe(
            member="The user to direct this action at (optional)"
        )(command)
    else:
        async def command(self, ctx):
            await self.send_action(ctx, action)

    command = app_commands.allowed_installs(guilds=True, users=True)(command)
    command = app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)(command)
    command.__name__ = f"{action}_command"

    return commands.hybrid_command(name=action, description=description)(command)


class Gifs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        """Called when the cog is loaded. Register dynamic commands here
        because add_command() is not available in __init__."""
        self._register_dynamic_commands()
        logger.info("[Gifs] Registered %d dynamic action commands", len(ACTIONS))

    @property
    def session(self):
        """Get the shared aiohttp session."""
        return get_shared_session()

    def _register_dynamic_commands(self):
        """Register all action commands dynamically from the ACTIONS dict.

        In discord.py 2.6+, add_command() is a Bot method, not a Cog method.
        The Cog._inject() method calls cog_load() first, then iterates
        __cog_commands__ to register commands with the bot. So we add the
        dynamically created commands to the cog's __cog_commands__ tuple here.

        Note: We do NOT add to __cog_app_commands__ because bot.add_command()
        for hybrid commands already registers the app_command to the tree.
        Adding to both would cause CommandAlreadyRegistered errors.
        """
        new_commands = []

        for action, template in TARGET_ACTIONS.items():
            new_commands.append(_create_action_command(action, template, needs_target=True))
        for action, template in NO_TARGET_ACTIONS.items():
            new_commands.append(_create_action_command(action, template, needs_target=False))

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

    async def send_action(self, ctx, action: str, member: Optional[str] = None):
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
        target = "you"

        # Resolve the target from the member argument (works for both prefix & slash)
        if member:
            if isinstance(member, discord.Member):
                target = member.mention
            else:
                try:
                    converted = await commands.MemberConverter().convert(ctx, member)
                    target = converted.mention
                except commands.BadArgument:
                    pass  # fall back to "you"

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
        await ctx.send(content=f"***{content}***", embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Gifs(bot))