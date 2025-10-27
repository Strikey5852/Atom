import aiohttp
import discord
from discord.ext import commands
from typing import Optional


class Gifs(commands.Cog):
    """Send action GIFs using the nekos.best v2 API.

    Each action is its own command, for example:
      >hug @user  or  /hug @user
      >kiss @user  or  /kiss @user

    You can also reply to a message with the command to target that user.
    """
    # List of supported actions (from nekos.best API)
    ACTIONS = [
        "lurk","shoot","sleep","shrug","stare","wave","poke","smile","peck",
        "wink","blush","smug","tickle","yeet","think","highfive","feed",
        "bite","bored","nom","yawn","facepalm","cuddle","kick","happy",
        "hug","pat","angry","run","nod","nope","kiss","dance",
        "punch","handshake","slap","cry","pout","handhold","thumbsup","laugh"
    ]

    # Targeted phrasing templates (actor-focused). Use {actor} and {target} placeholders.
    TARGETED_PHRASES = {
        "shoot": "{actor} shoots at {target}",
        "shrug": "{actor} shrugs at {target}",
        "stare": "{actor} stares at {target}",
        "wave": "{actor} waves at {target}",
        "poke": "{actor} pokes {target}",
        "smile": "{actor} smiles at {target}",
        "peck": "{actor} pecks {target}",
        "wink": "{actor} winks at {target}",
        "blush": "{actor} blushes at {target}",
        "smug": "{actor} gives {target} a smug look",
        "tickle": "{actor} tickles {target}",
        "yeet": "{actor} yeets {target}",
        "highfive": "{actor} gives {target} a high five",
        "feed": "{actor} feeds {target}",
        "bite": "{actor} bites {target}",
        "nom": "{actor} noms {target}",
        "cuddle": "{actor} cuddles {target}",
        "kick": "{actor} kicks {target}",
        "hug": "{actor} hugs {target}",
        "pat": "{actor} pats {target}",
        "angry": "{actor} gets angry at {target}",
        "kiss": "{actor} kisses {target}",
        "dance": "{actor} dances with {target}",
        "punch": "{actor} punches {target}",
        "handshake": "{actor} shakes hands with {target}",
        "slap": "{actor} slaps {target}",
        "cry": "{actor} cries for {target}",
        "pout": "{actor} pouts at {target}",
        "handhold": "{actor} holds {target}'s hand",
        "thumbsup": "{actor} gives {target} a thumbs up",
        "laugh": "{actor} laughs at {target}",
    }

    # Non-targeted (self) phrasing templates
    NON_TARGETED_PHRASES = {
        "lurk": "lurks",
        "sleep": "sleeps",
        "think": "thinks",
        "bored": "feels bored",
        "yawn": "yawns",
        "facepalm": "facepalms",
        "run": "runs",
        "nod": "nods",
        "nope": "says nope",
        "happy": "feels happy",
    }

    # Actions that do not accept a target — the command is self-directed
    NON_TARGETED = set(NON_TARGETED_PHRASES.keys())

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _resolve_target_from_context(self, ctx: commands.Context, member: Optional[discord.Member]) -> Optional[discord.Member]:
        """Determine the target member: explicit member argument, or the author of the replied-to message if present."""
        if member:
            return member

        # If this was used as a prefix command, ctx.message may be present
        msg = getattr(ctx, "message", None)
        if msg and msg.reference:
            try:
                ref = msg.reference
                # Fetch the referenced message
                referenced = None
                if hasattr(ref, "message_id") and ref.message_id:
                    channel = msg.channel
                    referenced = await channel.fetch_message(ref.message_id)
                if referenced and referenced.author:
                    # Try to resolve to a Member in this guild
                    if isinstance(referenced.author, discord.Member):
                        return referenced.author
                    # If it's a User, try to get Member from guild
                    if ctx.guild:
                        return ctx.guild.get_member(referenced.author.id)
            except Exception:
                pass

        return None

    # initial shared handler removed — consolidated handler below is used


    async def _fetch_gif(self, action: str) -> Optional[str]:
        """Internal helper to fetch a single gif URL from nekos.best.
        Returns the image URL on success or None on failure."""
        url = f"https://nekos.best/api/v2/{action}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json()
                    return data.get("results", [])[0].get("url")
        except Exception:
            return None

    async def _handle_action(self, ctx: commands.Context, action: str, member: Optional[discord.Member] = None, allow_target: bool = True):
        """Internal helper to handle fetching and sending action gifs."""
        # Resolve a target only if this action supports targeting
        target = None
        if allow_target:
            if member is None and getattr(ctx, "message", None) and ctx.message.reference:
                try:
                    replied_msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                    # Only treat the reply as a target if the command message explicitly mentions the replied user
                    mentions = getattr(ctx.message, "mentions", []) or []
                    if replied_msg.author in mentions:
                        member = replied_msg.author
                except Exception:
                    pass
            # Try to resolve member to a guild Member object if possible
            if member and ctx.guild and not isinstance(member, discord.Member):
                try:
                    member = ctx.guild.get_member(member.id)
                except Exception:
                    pass
            target = member

        # Indicate we're working
        try:
            await ctx.trigger_typing()
        except Exception:
            pass

        img_url = await self._fetch_gif(action)

        if not img_url:
            error_msg = "Couldn't fetch a gif right now. Try again later."
            interaction = getattr(ctx, "interaction", None)
            if interaction is not None:
                try:
                    await interaction.response.send_message(error_msg, ephemeral=True)
                    return
                except Exception:
                    pass
            await ctx.send(error_msg)
            return

        # Build the plain-text message according to whether the action targets someone
        actor_name = ctx.author.display_name
        if not allow_target:
            # Non-targeted: present tense phrases like "Ari thinks"
            present = self.NON_TARGETED_PHRASES.get(action, action if action.endswith("s") else f"{action}s")
            message_text = f"**{actor_name} {present}**"
        else:
            if target:
                # Targeted: use a template if we have one, otherwise default to "Actor verbs Target"
                tpl = self.TARGETED_PHRASES.get(action)
                if tpl:
                    # Use mention for pinging the target
                    message_text = tpl.format(actor=f"**{actor_name}**", target=target.mention)
                else:
                    verb = action if action.endswith("s") else f"{action}s"
                    message_text = f"**{actor_name} {verb} {target.mention}**"
            else:
                # No explicit target resolved — fall back to self-targeting phrasing
                present = self.NON_TARGETED_PHRASES.get(action, action if action.endswith("s") else f"{action}s")
                message_text = f"**{present} you**"

        # Create embed with only the image
        embed = discord.Embed(color=discord.Color.from_str("#00FFFF"))
        embed.set_image(url=img_url)

        interaction = getattr(ctx, "interaction", None)
        if interaction is not None:
            try:
                await interaction.response.send_message(content=message_text, embed=embed)
                return
            except Exception:
                pass

        await ctx.send(content=message_text, embed=embed)

    # Commands are registered dynamically below to avoid repeating boilerplate

# Dynamically attach hybrid commands for each supported action
def _make_action_command(action_name: str):
    # If action is non-targeted, create a no-target command signature
    if action_name in Gifs.NON_TARGETED:
        @commands.hybrid_command(
            name=action_name,
            description=f"{action_name.capitalize()}"
        )
        async def _cmd(self, ctx):
            await self._handle_action(ctx, action_name, None, allow_target=False)
    else:
        @commands.hybrid_command(
            name=action_name,
            description=f"{action_name.capitalize()} someone"
        )
        async def _cmd(self, ctx, member: Optional[discord.Member] = None):
            await self._handle_action(ctx, action_name, member, allow_target=True)

    return _cmd


# Register commands during cog setup
async def setup(bot: commands.Bot):
    cog = Gifs(bot)
    registered = 0

    for _action in Gifs.ACTIONS:
        try:
            cmd = _make_action_command(_action)

            # Bind the command to the cog and mark it as belonging to this cog
            cmd.cog = cog
            cmd._callback = cmd.callback.__get__(cog, Gifs)

            # Add to cog manually
            cog.__cog_commands__ = (*cog.__cog_commands__, cmd)

            registered += 1
        except Exception as e:
            print(f"Error registering command {_action}: {e}")

    await bot.add_cog(cog)