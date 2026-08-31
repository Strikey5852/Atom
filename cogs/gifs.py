import asyncio
import logging
from typing import Optional

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from shared_http import get_shared_session

logger = logging.getLogger(__name__)

# The action sets below map names to message templates.

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
    "lick": "{actor} licks {target}",
    "nuzzle": "{actor} nuzzles {target}",
    "brofist": "{actor} brofists {target}",
    "pinch": "{actor} pinches {target}",
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
    "celebrate": "{actor} celebrates",
    "cool": "{actor} is cool",
    "drool": "{actor} drools",
    "evillaugh": "{actor} evil laughs",
    "headbang": "{actor} headbangs",
    "nervous": "{actor} is nervous",
    "nosebleed": "{actor} has a nosebleed",
    "peek": "{actor} peeks",
    "sad": "{actor} is sad",
    "scared": "{actor} is scared",
    "shout": "{actor} shouts",
    "shy": "{actor} is shy",
    "sigh": "{actor} sighs",
    "sing": "{actor} sings",
    "slowclap": "{actor} slow claps",
    "sneeze": "{actor} sneezes",
    "stop": "{actor} signals stop",
    "sweat": "{actor} sweats",
    "tired": "{actor} is tired",
    "woah": "{actor} says woah",
    "yay": "{actor} yays",
}

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
    "angrystare": ("{actor} angrily stares at {target}", "{actor} angrily stares"),
    "love": ("{actor} gives love to {target}", "{actor} gives love"),
    "sorry": ("{actor} apologizes to {target}", "{actor} apologizes"),
    "cheers": ("{actor} cheers with {target}", "{actor} cheers"),
}

NEKOS_BASE = "https://nekos.best/api/v2/"
OTAKUGIFS_BASE = "https://api.otakugifs.xyz/gif?reaction={action}&format=gif"

ALT_ACTIONS = {
    "lick", "nuzzle", "brofist", "pinch",
    "angrystare", "love", "sorry", "cheers",
    "celebrate", "cool", "drool", "evillaugh",
    "headbang", "nervous", "nosebleed", "peek",
    "sad", "scared", "shout", "shy", "sigh",
    "sing", "slowclap", "sneeze", "stop", "sweat",
    "tired", "woah", "yay",
}

DESCRIPTIONS = {
    "shoot": "( ・_・)ノ⌒●~*",
    "poke": "( ・_・)σ",
    "tickle": "(く・ω・)く",
    "yeet": "(ノ°ο°)ノ",
    "highfive": "( °∀°)人(°∀° )",
    "feed": "(っ˘ڡ˘ς)",
    "bite": "(・∀・) ｶﾞﾌﾞｯ",
    "nom": "( ˘༥˘ )",
    "cuddle": "(づ｡◕‿‿◕｡)づ",
    "kick": "(ノ>_<)ノ ┌┛",
    "hug": "(つ≧▽≦)つ",
    "kiss": "(*￣3￣)╭",
    "punch": "(ง •̀_•́)ง",
    "handshake": "(・_・)人(・_・)",
    "slap": "( '= ')ノ)- -)",
    "handhold": "(⁄ ⁄•⁄ω⁄•⁄ ⁄)vv(⁄ ⁄•⁄ω⁄•⁄ ⁄)",
    "peck": "( ˘ ³˘)♡",
    "carry": "(⊃｡•́‿•̀｡)⊃",
    "kabedon": "|(•̀ᴗ•́)✧",
    "baka": "(ノ°益°)ノ",
    "bonk": "( ・_・)ノ☆(>_<)",
    "lappillow": "(◦′ ω ‵◦)",
    "blowkiss": "( ˘ ³˘)ﾉ",
    "pat": "(ｏ・_・)ノ(ᴗ_ᴗ。)",
    "lurk": "(┬┴┬┴┤•_•)",
    "sleep": "( -_•) zZZ",
    "clap": "( • ω • )888",
    "shrug": "¯\\_(ツ)_/¯",
    "confused": "(・_・?)",
    "sip": "( ￣ω￣)旦",
    "blush": "(⁄ ⁄•⁄ω⁄•⁄ ⁄)",
    "smug": "(¬‿¬)",
    "think": "(￣ヘ￣)",
    "wag": "(＾• ω •＾)",
    "teehee": "( > ▽ < )",
    "shocked": "(⊙_⊙)",
    "bleh": "( ＞ｐ＜ )",
    "bored": "(￣～￣;)",
    "nya": "(=^･ω･^=)",
    "yawn": "(´O｀)",
    "facepalm": "(ノ_＜)",
    "happy": "(＾▽＾)",
    "angry": "(╬ Ò﹏Ó)",
    "spin": "(o゜▽゜)o",
    "shake": "ヽ(°〇°)ﾉ",
    "run": "ε=ε=┌( >_<)┘",
    "cry": "(╥﹏╥)",
    "salute": "(￣^￣)ゞ",
    "tableflip": "(╯°□°）╯︵ ┻━┻",
    "stare": "(¬_¬)",
    "wave": "(￣▽￣)ノ",
    "smile": "( ^_^ )",
    "wink": "(＾‿＾)",
    "nod": "( ・_・)(_ _)",
    "nope": "(乂 ─_─ )",
    "dance": "♪(┌・。・)┌",
    "laugh": "(≧▽≦)",
    "pout": "( ￣ 3￣)",
    "thumbsup": "(b ᵔ▽ᵔ)b",
    "lick": "(^q^)",
    "nuzzle": "(´ ∀ ` *)",
    "brofist": "( ・ω・)=っo",
    "pinch": "( ˘ ⌣ ˘)σ",
    "angrystare": "(▼皿▼#)",
    "love": "(♡´∀`♡)",
    "sorry": "(シ_ _)シ",
    "cheers": "( ^^)／▽ ▽＼(^^ )",
    "celebrate": "( ﾉ^ω^)ﾉﾟ",
    "cool": "(•̀ᴗ•́)و",
    "drool": "(￣﹃￣)",
    "evillaugh": "(｀∀´)Ψ",
    "headbang": "(ﾉ≧∀≦)ﾉ",
    "nervous": "(´•ω•̥`)",
    "nosebleed": "(＞人＜；)",
    "peek": "|ω•́`)",
    "sad": "(´；ω；`)",
    "scared": "(>_<,,)",
    "shout": "(ﾟДﾟ)ﾉ",
    "shy": "(/ω＼)",
    "sigh": "(´-ω-`)",
    "sing": "(♪´∀`)ﾉ",
    "slowclap": "( ￣ω￣) 8 8 8",
    "sneeze": "(>з<)",
    "stop": "(乂｀д´)",
    "sweat": "(;´Д`)",
    "tired": "(￣ω￣;)",
    "woah": "(°ω°)",
    "yay": "＼(^ω^＼)"
}

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

        command = app_commands.describe(
            member="The member to direct this action at"
        )(command)

    command = app_commands.allowed_installs(guilds=True, users=True)(command)
    command = app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)(command)
    command.__name__ = f"{action}_command"
    # Keep the qualname on the class so discord.py treats this as a method, not a nested function.
    command.__qualname__ = f"Gifs.{action}_command"

    return commands.hybrid_command(
        name=action,
        description=DESCRIPTIONS.get(action, action.capitalize()),
    )(command)


class Gifs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        """Register the generated action commands when the cog loads."""
        self._register_dynamic_commands()
        total = len(MUTUAL_ACTIONS) + len(SOLO_ACTIONS) + len(BOTH_ACTIONS)
        logger.info("[Gifs] Registered %d dynamic action commands", total)

    @property
    def session(self):
        """Get the shared aiohttp session."""
        return get_shared_session()

    def _register_dynamic_commands(self):
        """Register the generated action commands on the cog itself."""
        new_commands = []

        for action in MUTUAL_ACTIONS:
            new_commands.append(_create_action_command(action, target_mode="required"))
        for action in SOLO_ACTIONS:
            new_commands.append(_create_action_command(action, target_mode="none"))
        for action in BOTH_ACTIONS:
            new_commands.append(_create_action_command(action, target_mode="optional"))

        self.__cog_commands__ = self.__cog_commands__ + tuple(new_commands)

    async def fetch_gif(self, action: str) -> str:
        if action in ALT_ACTIONS:
            url = OTAKUGIFS_BASE.format(action=action)
        else:
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
                    if action in ALT_ACTIONS:
                        # otakugifs returns {"url": "..."}
                        gif_url = data.get("url")
                        if not gif_url:
                            logger.warning(
                                "[Gifs] Attempt %d: 200 OK but no 'url'. Raw keys: %s",
                                attempt, list(data.keys()),
                            )
                            return None
                    else:
                        # nekos.best returns {"results": [{"url": "..."}]}
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

        if action in MUTUAL_ACTIONS:
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