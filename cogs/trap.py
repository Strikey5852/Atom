import datetime
import logging
import time
from typing import Any, Optional
import discord
from discord import app_commands
from discord.ext import commands

from database import get_database

logger = logging.getLogger(__name__)

DEFAULT_THRESHOLD = 5
DEFAULT_TIME_WINDOW = 10
TIMEOUT_DURATION = 86400
MAX_LOG_ENTRIES_PER_USER = 100


class Trap(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        logger.debug("[Trap] Cog initialized")

        self.db = get_database()
        self.filename = "trap.json"

        self.trap_config: dict[str, dict[str, Any]] = {}
        self._message_log: dict[int, dict[int, list[tuple[float, str, int, int]]]] = {}
        self._pending_actions: set[int] = set()

    async def load_config(self) -> dict:
        """Load trap config from the database."""
        try:
            data = await self.db.get_all(self.filename)
            if data:
                data.pop("_actions", None)
                self.trap_config = data
            else:
                self.trap_config = {}
            logger.info("[Trap] Loaded config for %d guild(s)", len(self.trap_config))
        except Exception as e:
            logger.exception("[Trap] Error loading config: %s", e)
            self.trap_config = {}
        return self.trap_config

    async def save_config(self):
        """Save trap config to the database."""
        try:
            await self.db.set_all(self.filename, self.trap_config)
        except Exception as e:
            logger.exception("[Trap] Error saving config: %s", e)


    def _get_guild_config(self, guild_id: str) -> dict[str, Any]:
        return self.trap_config.get(guild_id, {
            "enabled": False,
            "threshold": DEFAULT_THRESHOLD,
            "time_window": DEFAULT_TIME_WINDOW,
            "log_channel_id": None,
        })

    def _set_guild_config(self, guild_id: str, **kwargs):
        if guild_id not in self.trap_config:
            self.trap_config[guild_id] = {
                "enabled": False,
                "threshold": DEFAULT_THRESHOLD,
                "time_window": DEFAULT_TIME_WINDOW,
                "log_channel_id": None,
            }
        self.trap_config[guild_id].update(kwargs)

    @staticmethod
    def _get_message_signature(message: discord.Message) -> str:
        parts = []
        if message.content:
            parts.append(f"text:{message.content}")
        for att in message.attachments:
            parts.append(f"att:{att.filename}:{att.size}")
        for sticker in message.stickers:
            parts.append(f"sticker:{sticker.id}")
        if not parts:
            return ""
        return " | ".join(parts)

    def _add_message_to_log(
        self, guild_id: int, user_id: int, entry: tuple[float, str, int, int]
    ):
        """Add a message entry to the log for a user, trimming to the cap."""
        log = self._message_log.setdefault(guild_id, {}).setdefault(user_id, [])
        log.append(entry)
        if len(log) > MAX_LOG_ENTRIES_PER_USER:
            del log[: len(log) - MAX_LOG_ENTRIES_PER_USER]

    def _prune_message_log(self, guild_id: int, user_id: int, time_window: float):
        """Remove log entries older than the configured time window."""
        now = time.time()
        log = self._message_log.get(guild_id, {}).get(user_id, [])
        self._message_log[guild_id][user_id] = [
            entry for entry in log if now - entry[0] <= time_window
        ]

    async def _purge_user_messages(
        self,
        guild: discord.Guild,
        user_id: int,
        tracked: list[tuple[float, str, int, int]],
        time_window: float,
    ) -> int:
        """Two-phase purge. Returns total number of messages deleted."""
        total_deleted = 0
        channel_groups: dict[int, list[int]] = {}
        for _, _, channel_id, msg_id in tracked:
            channel_groups.setdefault(channel_id, []).append(msg_id)

        for channel_id, msg_ids in channel_groups.items():
            channel = guild.get_channel(channel_id)
            if not channel:
                continue
            try:
                for i in range(0, len(msg_ids), 100):
                    batch = [discord.Object(id=mid) for mid in msg_ids[i:i + 100]]
                    await channel.delete_messages(batch)
                    total_deleted += len(batch)
            except discord.Forbidden:
                logger.warning("[Trap] Missing manage_messages permission in %s", channel.name)
            except discord.NotFound:
                pass
            except Exception as e:
                logger.exception("[Trap] Error purging tracked messages in %s: %s", channel.name, e)

        after = discord.utils.utcnow() - datetime.timedelta(seconds=time_window)
        for channel_id in channel_groups:
            channel = guild.get_channel(channel_id)
            if not channel:
                continue
            try:
                deleted = await channel.purge(
                    limit=100,
                    after=after,
                    check=lambda m: m.author.id == user_id,
                    bulk=True,
                )
                total_deleted += len(deleted)
            except discord.Forbidden:
                logger.warning("[Trap] Missing manage_messages permission in %s", channel.name)
            except discord.NotFound:
                pass
            except Exception as e:
                logger.exception("[Trap] Error sweeping messages in %s: %s", channel.name, e)

        return total_deleted

    async def _send_trap_log(
        self,
        guild: discord.Guild,
        log_channel_id: Optional[int],
        user: discord.User,
        message: discord.Message,
        matching: list[tuple[float, str, int, int]],
        channels_used: list[str],
        deleted_count: int = 0,
    ):
        if not log_channel_id:
            return None
        channel = guild.get_channel(log_channel_id)
        if not channel:
            return None

        member = None
        try:
            member = await guild.fetch_member(user.id)
        except discord.NotFound:
            pass

        velocity_str = f"{len(matching)} identical messages"
        if len(matching) >= 2:
            elapsed = matching[-1][0] - matching[0][0]
            velocity_str += f" in {elapsed:.2f}s"
        else:
            velocity_str += " (instant)"

        embed = discord.Embed(
            title="Trap Triggered",
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="User", value=f"{user.mention} (`{user.id}`)", inline=False)
        embed.add_field(
            name="Account Age",
            value=discord.utils.format_dt(user.created_at, "R"),
            inline=True,
        )
        embed.add_field(
            name="Joined Server",
            value=discord.utils.format_dt(member.joined_at, "R") if member else "Unknown",
            inline=True,
        )
        embed.add_field(name="Velocity", value=velocity_str, inline=False)
        embed.add_field(
            name="Channels Targeted",
            value=", ".join(f"#{ch}" for ch in channels_used),
            inline=False,
        )

        if message.content:
            embed.add_field(
                name="Text Payload",
                value=f"```{message.content[:1000]}```",
                inline=False,
            )
        elif message.attachments:
            att = message.attachments[0]
            is_image = att.content_type and att.content_type.startswith("image/")
            payload_text = f"Name: {att.filename}\nSize: {att.size:,} bytes"
            if not is_image:
                payload_text += f"\nType: {att.content_type or 'Unknown'}"
            embed.add_field(
                name="Attachment Payload",
                value=payload_text,
                inline=False,
            )
        elif message.stickers:
            sticker = message.stickers[0]
            embed.add_field(
                name="Sticker Payload",
                value=f"Name: {sticker.name} (ID: {sticker.id})",
                inline=False,
            )

        embed.add_field(name="Messages Purged", value=str(deleted_count), inline=False)

        try:
            await channel.send(embed=embed)
        except Exception as e:
            logger.exception("[Trap] Failed to send log: %s", e)


    @commands.Cog.listener()
    async def on_ready(self):
        await self.load_config()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild or message.is_system():
            return

        guild_id = str(message.guild.id)
        config = self._get_guild_config(guild_id)
        if not config["enabled"]:
            return

        if message.author.guild_permissions.administrator:
            return

        user = message.author
        threshold = config["threshold"]
        time_window = config["time_window"]

        signature = self._get_message_signature(message)
        if not signature:
            return

        guild_id_int = message.guild.id
        user_id = user.id

        self._message_log.setdefault(guild_id_int, {})
        self._message_log[guild_id_int].setdefault(user_id, [])

        self._add_message_to_log(
            guild_id_int, user_id, (time.time(), signature, message.channel.id, message.id)
        )

        self._prune_message_log(guild_id_int, user_id, time_window)

        tracked = self._message_log[guild_id_int][user_id]
        matching = [entry for entry in tracked if entry[1] == signature]

        if len(matching) >= threshold:
            if user_id in self._pending_actions:
                return
            self._pending_actions.add(user_id)

            try:
                # 1. Timeout the user FIRST — stops them from sending more
                timeout_until = discord.utils.utcnow() + datetime.timedelta(seconds=TIMEOUT_DURATION)
                await user.timeout(
                    timeout_until,
                    reason=f"Spam repetition trap: {len(matching)} identical messages in {time_window}s",
                )

                # 2. Then purge all their messages
                deleted_count = await self._purge_user_messages(message.guild, user_id, matching, time_window)

                # 3. Send log with the purge count
                channel_names = list({
                    ch.name for _, _, ch_id, _ in matching
                    if (ch := message.guild.get_channel(ch_id))
                })

                await self._send_trap_log(
                    message.guild,
                    config["log_channel_id"],
                    user,
                    message,
                    matching,
                    channel_names,
                    deleted_count,
                )

                logger.warning(
                    "[Trap] Timed out %s (%s) from %s — %d repeats in %ss, purged %d messages",
                    user, user.id, message.guild.name, len(matching), time_window, deleted_count,
                )
            except Exception as e:
                logger.exception("[Trap] Timeout failed for %s (%s): %s: %s", user, user.id, type(e).__name__, e)
            finally:
                self._message_log.get(guild_id_int, {}).pop(user_id, None)
                self._pending_actions.discard(user_id)


    @commands.hybrid_group(
        name="trap",
        description="Enable or disable the spam repetition trap for this server.",
        fallback="toggle",
    )
    @commands.has_permissions(administrator=True)
    @app_commands.allowed_installs(guilds=True, users=False)
    @commands.guild_only()
    async def trap(self, ctx: commands.Context):
        guild_id = str(ctx.guild.id)
        config = self._get_guild_config(guild_id)
        new_state = not config["enabled"]
        self._set_guild_config(guild_id, enabled=new_state)
        await self.save_config()
        status = "enabled" if new_state else "disabled"
        logger.info("[Trap] %s toggled trap to %s (guild=%s)", ctx.author, status, ctx.guild.name)
        await ctx.send(f"Spam repetition trap is now **{status}**.")

    @trap.command(
        name="set",
        description="Configure the spam repetition detection threshold and time window.",
    )
    @commands.has_permissions(administrator=True)
    @app_commands.allowed_installs(guilds=True, users=False)
    @commands.guild_only()
    @app_commands.describe(
        threshold="Number of identical messages before triggering a timeout (default: 5)",
        time_window="Time window in seconds to count repeats (default: 10)",
    )
    async def trapset(
        self,
        ctx: commands.Context,
        threshold: int = DEFAULT_THRESHOLD,
        time_window: int = DEFAULT_TIME_WINDOW,
    ):
        if threshold < 2:
            await ctx.send("Threshold must be at least 2.")
            return
        if time_window < 1:
            await ctx.send("Time window must be at least 1 second.")
            return

        guild_id = str(ctx.guild.id)
        self._set_guild_config(guild_id, threshold=threshold, time_window=time_window)
        await self.save_config()
        logger.info("[Trap] %s configured trap: threshold=%d window=%ds (guild=%s)", ctx.author, threshold, time_window, ctx.guild.name)
        await ctx.send(
            f"Trap configured: **{threshold}** identical messages in **{time_window}** seconds."
        )

    @trap.command(
        name="log",
        description="Set the channel where trap timeout notifications are posted.",
    )
    @commands.has_permissions(administrator=True)
    @app_commands.allowed_installs(guilds=True, users=False)
    @commands.guild_only()
    @app_commands.describe(channel="The channel to send timeout logs to")
    async def traplog(self, ctx: commands.Context, channel: discord.TextChannel):
        guild_id = str(ctx.guild.id)
        self._set_guild_config(guild_id, log_channel_id=channel.id)
        await self.save_config()
        logger.info("[Trap] %s set trap log channel to %s (guild=%s)", ctx.author, channel.name, ctx.guild.name)
        await ctx.send(f"Trap timeout logs will be sent to {channel.mention}.")

    @trapset.autocomplete("threshold")
    async def threshold_autocomplete(
        self, _: discord.Interaction, current: str
    ) -> list[app_commands.Choice[int]]:
        return [
            app_commands.Choice(name=str(v), value=v)
            for v in [2, 3, 5, 10, 20]
            if str(v).startswith(current)
        ]

    @trapset.autocomplete("time_window")
    async def time_window_autocomplete(
        self, _: discord.Interaction, current: str
    ) -> list[app_commands.Choice[int]]:
        return [
            app_commands.Choice(name=str(v), value=v)
            for v in [5, 10, 15, 30, 60]
            if str(v).startswith(current)
        ]


async def setup(bot):
    await bot.add_cog(Trap(bot))