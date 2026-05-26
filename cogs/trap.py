import time
from typing import Any, Optional

import discord
from discord import app_commands
from discord.ext import commands

from database import get_database


# Default configuration values
DEFAULT_THRESHOLD = 5
DEFAULT_TIME_WINDOW = 10  # seconds


class Trap(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.db = get_database()
        self.filename = "trap.json"

        # Persistent settings per guild: {guild_id: {enabled, threshold, time_window, log_channel_id}}
        self.trap_config: dict[str, dict[str, Any]] = {}

        # In-memory message log for repetition detection.
        # {guild_id: {user_id: [(timestamp, content, channel_id, message_id), ...]}}
        self._message_log: dict[int, dict[int, list[tuple[float, str, int, int]]]] = {}

        # Set of user_ids currently being banned (prevents duplicate concurrent bans)
        self._pending_bans: set[int] = set()

    # ──────────────────────────────────────────────
    # Persistence
    # ──────────────────────────────────────────────

    async def load_config(self) -> dict:
        """Load trap config from the database."""
        try:
            data = await self.db.get_all(self.filename)
            if data and isinstance(next(iter(data.values()), None), dict):
                # New format
                self.trap_config = data
            else:
                # Old format or empty — start fresh
                self.trap_config = {}
        except Exception as e:
            print(f"[Trap] Error loading config: {e}")
            self.trap_config = {}
        return self.trap_config

    async def save_config(self):
        """Save trap config to the database."""
        try:
            await self.db.set_all(self.filename, self.trap_config)
        except Exception as e:
            print(f"[Trap] Error saving config: {e}")

    # ──────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────

    def _get_guild_config(self, guild_id: str) -> dict[str, Any]:
        """Get config dict for a guild, or a default if not set."""
        return self.trap_config.get(guild_id, {
            "enabled": False,
            "threshold": DEFAULT_THRESHOLD,
            "time_window": DEFAULT_TIME_WINDOW,
            "log_channel_id": None,
        })

    def _set_guild_config(self, guild_id: str, **kwargs):
        """Update specific keys in a guild's config."""
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
        """Build a unique fingerprint for a message based on all its content types."""
        parts = []

        # Text content
        if message.content:
            parts.append(f"text:{message.content}")

        # Attachments (filename + size)
        for att in message.attachments:
            parts.append(f"att:{att.filename}:{att.size}")

        # Stickers
        for sticker in message.stickers:
            parts.append(f"sticker:{sticker.id}")

        if not parts:
            return ""

        return " | ".join(parts)

    def _prune_message_log(self, guild_id: int, user_id: int, time_window: float):
        """Remove entries older than time_window for a given user in a guild."""
        now = time.time()
        log = self._message_log.get(guild_id, {}).get(user_id, [])
        self._message_log[guild_id][user_id] = [
            entry for entry in log if now - entry[0] <= time_window
        ]

    async def _purge_tracked_messages(
        self,
        guild: discord.Guild,
        user_id: int,
        tracked: list[tuple[float, str, int, int]],
    ):
        """Delete all tracked messages from their respective channels."""
        # Group message IDs by channel
        channel_groups: dict[int, list[int]] = {}
        for _, _, channel_id, msg_id in tracked:
            channel_groups.setdefault(channel_id, []).append(msg_id)

        for channel_id, msg_ids in channel_groups.items():
            channel = guild.get_channel(channel_id)
            if not channel:
                continue
            # Discord allows bulk-deleting up to 100 messages at once
            try:
                for i in range(0, len(msg_ids), 100):
                    batch = msg_ids[i:i + 100]
                    await channel.delete_messages(batch)
            except discord.Forbidden:
                print(f"[Trap] Missing manage_messages permission in {channel.name}")
            except discord.NotFound:
                pass  # Some messages already deleted — fine
            except Exception as e:
                print(f"[Trap] Error purging messages in {channel.name}: {e}")

    async def _send_ban_log(
        self,
        guild: discord.Guild,
        log_channel_id: Optional[int],
        user: discord.User,
        repeated_content: str,
        repeat_count: int,
        time_window: int,
        channels_used: list[str],
    ):
        """Send a ban notification embed to the configured log channel."""
        if not log_channel_id:
            return
        channel = guild.get_channel(log_channel_id)
        if not channel:
            return

        embed = discord.Embed(
            title="Trap Ban Triggered",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="User", value=f"{user.mention} (`{user.id}`)", inline=False)
        embed.add_field(
            name="Repeated Content",
            value=f"```{repeated_content[:1000]}```",
            inline=False,
        )
        embed.add_field(name="Repeats", value=f"{repeat_count} in {time_window}s", inline=True)
        embed.add_field(
            name="Channels", value=", ".join(f"#{ch}" for ch in channels_used), inline=True
        )

        try:
            await channel.send(embed=embed)
        except Exception as e:
            print(f"[Trap] Failed to send log: {e}")

    # ──────────────────────────────────────────────
    # Listeners
    # ──────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_ready(self):
        await self.load_config()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore bots, DMs, and system messages
        if message.author.bot or not message.guild or message.is_system():
            return

        guild_id = str(message.guild.id)
        config = self._get_guild_config(guild_id)
        if not config["enabled"]:
            return

        # Ignore administrators
        if message.author.guild_permissions.administrator:
            return

        user = message.author
        threshold = config["threshold"]
        time_window = config["time_window"]

        # Build a signature that captures text, attachments, and stickers
        signature = self._get_message_signature(message)
        if not signature:
            return

        guild_id_int = message.guild.id
        user_id = user.id

        # Ensure nested dicts exist
        self._message_log.setdefault(guild_id_int, {})
        self._message_log[guild_id_int].setdefault(user_id, [])

        # Append current message
        self._message_log[guild_id_int][user_id].append(
            (time.time(), signature, message.channel.id, message.id)
        )

        # Prune old entries
        self._prune_message_log(guild_id_int, user_id, time_window)

        # Count how many of the remaining entries have identical signature
        tracked = self._message_log[guild_id_int][user_id]
        matching = [entry for entry in tracked if entry[1] == signature]

        if len(matching) >= threshold:
            # Check if ban is already in progress for this user
            if user_id in self._pending_bans:
                return
            self._pending_bans.add(user_id)

            try:
                # 1. Purge only the tracked spam messages
                await self._purge_tracked_messages(message.guild, user_id, matching)

                # 2. Ban the user
                await message.guild.ban(
                    user,
                    reason=f"Spam repetition trap: {len(matching)} identical messages in {time_window}s",
                )

                # 3. Log to configured channel
                channel_names = list({
                    ch.name for _, _, ch_id, _ in matching
                    if (ch := message.guild.get_channel(ch_id))
                })

                # For the log, show the original text if present, otherwise describe the content
                log_content = message.content if message.content else "[non-text content]"
                await self._send_ban_log(
                    message.guild,
                    config["log_channel_id"],
                    user,
                    log_content,
                    len(matching),
                    time_window,
                    channel_names,
                )

                print(
                    f"[TRAP] Banned {user} ({user.id}) from {message.guild.name} — "
                    f"{len(matching)} repeats in {time_window}s"
                )
            except Exception as e:
                print(f"[TRAP] Ban failed for {user} ({user.id}): {e}")
            finally:
                # Clear the user's tracked messages and remove from pending set
                self._message_log.get(guild_id_int, {}).pop(user_id, None)
                self._pending_bans.discard(user_id)

    # ──────────────────────────────────────────────
    # Commands
    # ──────────────────────────────────────────────

    @commands.hybrid_command(
        name="trap",
        description="Enable or disable the spam repetition trap for this server.",
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
        await ctx.send(f"Spam repetition trap is now **{status}**.")

    @commands.hybrid_command(
        name="trapset",
        description="Configure the spam repetition detection threshold and time window.",
    )
    @commands.has_permissions(administrator=True)
    @app_commands.allowed_installs(guilds=True, users=False)
    @commands.guild_only()
    @app_commands.describe(
        threshold="Number of identical messages before triggering a ban (default: 5)",
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
        await ctx.send(
            f"Trap configured: **{threshold}** identical messages in **{time_window}** seconds."
        )

    @commands.hybrid_command(
        name="traplog",
        description="Set the channel where trap ban notifications are posted.",
    )
    @commands.has_permissions(administrator=True)
    @app_commands.allowed_installs(guilds=True, users=False)
    @commands.guild_only()
    @app_commands.describe(channel="The channel to send ban logs to")
    async def traplog(self, ctx: commands.Context, channel: discord.TextChannel):
        guild_id = str(ctx.guild.id)
        self._set_guild_config(guild_id, log_channel_id=channel.id)
        await self.save_config()
        await ctx.send(f"Trap ban logs will be sent to {channel.mention}.")

    @commands.hybrid_command(
        name="removetrap",
        description="Disable the trap and clear its configuration for this server.",
    )
    @commands.has_permissions(administrator=True)
    @app_commands.allowed_installs(guilds=True, users=False)
    @commands.guild_only()
    async def remove_trap(self, ctx: commands.Context):
        guild_id = str(ctx.guild.id)
        if guild_id in self.trap_config:
            del self.trap_config[guild_id]
            await self.save_config()
            await ctx.send("Trap has been disabled and configuration cleared.")
        else:
            await ctx.send("No trap is configured for this server.")

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