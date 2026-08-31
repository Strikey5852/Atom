import asyncio
import logging

import discord
from discord import app_commands
from discord.ext import commands

from database import get_database

logger = logging.getLogger(__name__)


class StickyMessage(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._cooldown_channels = set()
        logger.debug("[Sticky] Cog initialized")

        self.db = get_database()
        self.filename = "sticky.json"

        # Initialize Cache
        self.cached_stickies = {}

    async def load_all_stickies(self) -> dict:
        """Loads data from the database into memory cache."""
        try:
            self.cached_stickies = await self.db.get_all(self.filename)
            logger.info("[Sticky] Loaded %d guild(s) from database", len(self.cached_stickies))
        except Exception as e:
            logger.exception("[Sticky] Error loading stickies: %s", e)
            self.cached_stickies = {}
        return self.cached_stickies

    async def save_to_disk(self):
        """Saves current memory cache to the database."""
        try:
            await self.db.set_all(self.filename, self.cached_stickies)
        except Exception as e:
            logger.exception("[Sticky] Critical Error saving stickies: %s", e)

    async def repost_sticky(self, channel: discord.TextChannel):
        """Handles the deletion of the old sticky and sending of the new one."""
        guild_id = str(channel.guild.id)
        channel_id = str(channel.id)

        # Safety check: ensure the channel is still in our cache
        if channel_id not in self.cached_stickies.get(guild_id, {}):
            self._cooldown_channels.discard(channel_id)
            return

        sticky_info = self.cached_stickies[guild_id][channel_id]
        content = sticky_info.get("content")
        last_msg_id = sticky_info.get("last_message_id")

        try:
            if last_msg_id:
                try:
                    old_msg = channel.get_partial_message(last_msg_id)
                    await old_msg.delete()
                except discord.NotFound:
                    pass  # Already deleted
                except discord.HTTPException:
                    pass

            new_msg = await channel.send(content)

            self.cached_stickies[guild_id][channel_id]["last_message_id"] = new_msg.id
            await self.save_to_disk()
            logger.info("[Sticky] Reposted sticky in channel=%s (new msg=%s)", channel.name, new_msg.id)

        except Exception as e:
            logger.exception("[Sticky] Error in repost_sticky: %s", e)
        finally:
            await asyncio.sleep(1)
            self._cooldown_channels.discard(channel_id)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or (
            message.author.bot and message.author != self.bot.user
        ):
            return

        guild_id = str(message.guild.id)
        channel_id = str(message.channel.id)

        # Check Cache (Instant) instead of Disk
        if (
            guild_id not in self.cached_stickies
            or channel_id not in self.cached_stickies[guild_id]
        ):
            return

        sticky_info = self.cached_stickies[guild_id][channel_id]

        # Ignore if this IS the sticky message
        if message.id == sticky_info.get("last_message_id"):
            return

        # Race Condition Prevention: Check and Set cooldown immediately
        if channel_id in self._cooldown_channels:
            return

        self._cooldown_channels.add(channel_id)

        # Repost the sticky
        logger.debug("[Sticky] Reposting sticky for channel=%s", message.channel.name)
        await self.repost_sticky(message.channel)

    @commands.Cog.listener()
    async def on_ready(self):
        # Load stickies from database
        await self.load_all_stickies()

    @commands.hybrid_group(
        name="sticky",
        description="Manage sticky messages in this server.",
    )
    @commands.guild_only()
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, private_channels=True, dms=False)
    async def sticky(self, ctx: commands.Context):
        """Manage sticky messages."""
        await ctx.send("Sticky commands: `set`, `remove`, `list`. See `/sticky` for usage.")

    @sticky.command(
        name="set", description="Set a sticky message in a specific channel."
    )
    @app_commands.describe(
        channel="The channel to set the sticky message in.",
        content="The message content to stick.",
    )
    @commands.has_permissions(manage_messages=True)
    @app_commands.allowed_installs(guilds=True, users=False)
    @commands.guild_only()
    async def set_sticky(
        self, ctx: commands.Context, channel: discord.TextChannel, content: str
    ):
        await ctx.defer()

        guild_id = str(ctx.guild.id)
        channel_id = str(channel.id)

        # Clean up existing sticky in cache if it exists
        if (
            guild_id in self.cached_stickies
            and channel_id in self.cached_stickies[guild_id]
        ):
            old_id = self.cached_stickies[guild_id][channel_id].get("last_message_id")
            if old_id:
                try:
                    await channel.get_partial_message(old_id).delete()
                except discord.NotFound:
                    pass
                except discord.HTTPException:
                    pass

        # Send fresh sticky
        msg = await channel.send(content)

        # Update Memory Cache
        if guild_id not in self.cached_stickies:
            self.cached_stickies[guild_id] = {}

        self.cached_stickies[guild_id][channel_id] = {
            "content": content,
            "last_message_id": msg.id,
        }

        # Save to Database
        await self.save_to_disk()
        logger.info(
            "[Sticky] Set sticky in channel=%s by %s (guild=%s)",
            channel.name, ctx.author, ctx.guild.name,
        )
        await ctx.send(f"Sticky message set in {channel.mention}")

    @sticky.command(
        name="remove",
        description="Remove the sticky message from a specific channel.",
    )
    @app_commands.describe(channel="The channel to remove the sticky message from.")
    @commands.has_permissions(manage_messages=True)
    @app_commands.allowed_installs(guilds=True, users=False)
    @commands.guild_only()
    async def remove_sticky(self, ctx: commands.Context, channel: discord.TextChannel):
        guild_id = str(ctx.guild.id)
        channel_id = str(channel.id)

        if (
            guild_id not in self.cached_stickies
            or channel_id not in self.cached_stickies[guild_id]
        ):
            return await ctx.send(f"No sticky message found in {channel.mention}.")

        last_id = self.cached_stickies[guild_id][channel_id].get("last_message_id")
        if last_id:
            try:
                await channel.get_partial_message(last_id).delete()
            except discord.NotFound:
                pass
            except discord.HTTPException:
                pass

        del self.cached_stickies[guild_id][channel_id]
        if not self.cached_stickies[guild_id]:
            del self.cached_stickies[guild_id]

        await self.save_to_disk()
        logger.info(
            "[Sticky] Removed sticky from channel=%s by %s (guild=%s)",
            channel.name, ctx.author, ctx.guild.name,
        )
        await ctx.send(f"Removed sticky message from {channel.mention}")

    @sticky.command(
        name="list", description="Show all sticky messages in this server."
    )
    @commands.has_permissions(manage_messages=True)
    @app_commands.allowed_installs(guilds=True, users=False)
    @commands.guild_only()
    async def list_stickies(self, ctx: commands.Context):
        guild_id = str(ctx.guild.id)

        if guild_id not in self.cached_stickies or not self.cached_stickies[guild_id]:
            return await ctx.send("No sticky messages set in this server.")

        lines = []
        for i, (ch_id, info) in enumerate(
            self.cached_stickies[guild_id].items(), start=1
        ):
            ch = ctx.guild.get_channel(int(ch_id))
            channel_name = ch.mention if ch else f"Unknown Channel ({ch_id})"
            content_preview = (
                (info["content"][:50] + "...")
                if len(info["content"]) > 50
                else info["content"]
            )
            lines.append(f"**{i}.** {channel_name}: {content_preview}")

        embed = discord.Embed(
            title="Server Sticky Messages",
            description="\n".join(lines),
            color=discord.Color.from_str("#00FFFF"),
        )
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(StickyMessage(bot))