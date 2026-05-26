import datetime
import time
from typing import Any, Optional

import discord
from discord import app_commands
from discord.ext import commands

from database import get_database


# Default configuration values
DEFAULT_THRESHOLD = 5
DEFAULT_TIME_WINDOW = 10  # seconds
TIMEOUT_DURATION = 86400  # 24 hours in seconds


class TrapActions(discord.ui.View):
    """Persistent view with Ban and Forgive buttons for trap log messages."""

    def __init__(self, cog: "Trap", user_id: int, guild_id: int):
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id
        super().__init__(timeout=None)

        # Static custom_ids — the bot uses _stored_actions to look up context on click
        self.ban_btn = discord.ui.Button(
            label="🔴 Ban Permanently",
            style=discord.ButtonStyle.danger,
            custom_id="trap_ban_btn",
        )
        self.ban_btn.callback = self.ban_callback
        self.add_item(self.ban_btn)

        self.forgive_btn = discord.ui.Button(
            label="🟢 Forgive (Un-timeout)",
            style=discord.ButtonStyle.success,
            custom_id="trap_forgive_btn",
        )
        self.forgive_btn.callback = self.forgive_callback
        self.add_item(self.forgive_btn)

    async def _check_admin(self, interaction: discord.Interaction) -> bool:
        """Check if the interaction user is an admin. Sends an error if not."""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "Only administrators can use this action.", ephemeral=True
            )
            return False
        return True

    async def _disable_buttons(self, interaction: discord.Interaction):
        """Disable both buttons and update the message."""
        self.ban_btn.disabled = True
        self.forgive_btn.disabled = True
        await interaction.message.edit(view=self)

    def _get_action_context(self, interaction: discord.Interaction) -> tuple[Optional[discord.Guild], Optional[int], Optional[int]]:
        """Resolve guild and user_id from stored actions."""
        guild = interaction.guild
        if not guild:
            return None, None, None
        action = self.cog._stored_actions.get(interaction.message.id)
        if not action:
            return guild, None, None
        return guild, action["user_id"], action["guild_id"]

    async def ban_callback(self, interaction: discord.Interaction):
        if not await self._check_admin(interaction):
            return

        guild, user_id, _ = self._get_action_context(interaction)
        if not guild or not user_id:
            await interaction.response.send_message("Could not resolve action context.", ephemeral=True)
            return

        try:
            user = await guild.fetch_member(user_id)
            if user:
                await guild.ban(user, reason=f"Trap ban action by {interaction.user}")
        except discord.NotFound:
            pass  # user already left or was banned

        await self._disable_buttons(interaction)

        embed = interaction.message.embeds[0]
        embed.add_field(
            name="Processed By",
            value=f"{interaction.user.mention} — **Banned**",
            inline=False,
        )
        await interaction.message.edit(embed=embed)
        await interaction.response.edit_message(view=self)

    async def forgive_callback(self, interaction: discord.Interaction):
        if not await self._check_admin(interaction):
            return

        guild, user_id, _ = self._get_action_context(interaction)
        if not guild or not user_id:
            await interaction.response.send_message("Could not resolve action context.", ephemeral=True)
            return

        try:
            user = await guild.fetch_member(user_id)
            if user:
                await user.timeout(until=None, reason=f"Trap forgiven by {interaction.user}")
        except discord.NotFound:
            pass  # user already left

        await self._disable_buttons(interaction)

        embed = interaction.message.embeds[0]
        embed.add_field(
            name="Processed By",
            value=f"{interaction.user.mention} — **Forgiven**",
            inline=False,
        )
        await interaction.message.edit(embed=embed)
        await interaction.response.edit_message(view=self)


class Trap(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.db = get_database()
        self.filename = "trap.json"

        # Persistent settings per guild: {guild_id: {enabled, threshold, time_window, log_channel_id}}
        self.trap_config: dict[str, dict[str, Any]] = {}

        # Stored action metadata for persistent views: {message_id: {channel_id, user_id, guild_id}}
        self._stored_actions: dict[int, dict[str, int]] = {}

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
            if data:
                # Pop actions safely out first so it doesn't pollute guild settings
                self._stored_actions = data.pop("_actions", {})
                # Whatever remains is the guild config data
                self.trap_config = data
            else:
                self.trap_config = {}
                self._stored_actions = {}
        except Exception as e:
            print(f"[Trap] Error loading config: {e}")
            self.trap_config = {}
            self._stored_actions = {}
        return self.trap_config

    async def save_config(self):
        """Save trap config and stored actions to the database."""
        try:
            # Merge stored actions into the data before saving
            data = dict(self.trap_config)
            data["_actions"] = self._stored_actions
            await self.db.set_all(self.filename, data)
        except Exception as e:
            print(f"[Trap] Error saving config: {e}")

    def _store_action(self, message_id: int, channel_id: int, user_id: int, guild_id: int):
        """Record action metadata so the view can be re-registered after restart."""
        self._stored_actions[message_id] = {
            "channel_id": channel_id,
            "user_id": user_id,
            "guild_id": guild_id,
        }

    def _remove_action(self, message_id: int):
        """Remove a stored action."""
        self._stored_actions.pop(message_id, None)

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

    async def _send_trap_log(
        self,
        guild: discord.Guild,
        log_channel_id: Optional[int],
        user: discord.User,
        message: discord.Message,
        matching: list[tuple[float, str, int, int]],
        channels_used: list[str],
    ):
        """Send a Trap Triggered embed with Ban and Forgive buttons."""
        if not log_channel_id:
            return
        channel = guild.get_channel(log_channel_id)
        if not channel:
            return

        # Attempt to fetch member for join date info
        member = None
        try:
            member = await guild.fetch_member(user.id)
        except discord.NotFound:
            pass

        # Velocity: time span between first and last matching message
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

        # Dynamic payload field: text vs attachment
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
            if is_image:
                embed.set_image(url=att.url)
        elif message.stickers:
            sticker = message.stickers[0]
            embed.add_field(
                name="Sticker Payload",
                value=f"Name: {sticker.name} (ID: {sticker.id})",
                inline=False,
            )

        view = TrapActions(self, user.id, guild.id)
        try:
            msg = await channel.send(embed=embed, view=view)
            # Persist the action so the view survives restarts
            self._store_action(msg.id, channel.id, user.id, guild.id)
            await self.save_config()
        except Exception as e:
            print(f"[Trap] Failed to send log: {e}")

    # ──────────────────────────────────────────────
    # Listeners
    # ──────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_ready(self):
        await self.load_config()

        # Re-register persistent views for stored actions
        for msg_id, action in list(self._stored_actions.items()):
            view = TrapActions(self, action["user_id"], action["guild_id"])
            self.bot.add_view(view, message_id=msg_id)

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
            # Check if action is already in progress for this user
            if user_id in self._pending_bans:
                return
            self._pending_bans.add(user_id)

            try:
                # 1. Purge only the tracked spam messages
                await self._purge_tracked_messages(message.guild, user_id, matching)

                # 2. Timeout the user for 24h — use member.timeout(), not guild.timeout()
                await message.author.timeout(
                    until=discord.utils.utcnow() + datetime.timedelta(seconds=TIMEOUT_DURATION),
                    reason=f"Spam repetition trap: {len(matching)} identical messages in {time_window}s",
                )

                # 3. Log to configured channel with action buttons
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
                )

                print(
                    f"[TRAP] Timed out {user} ({user.id}) from {message.guild.name} — "
                    f"{len(matching)} repeats in {time_window}s"
                )
            except Exception as e:
                print(f"[TRAP] Timeout failed for {user} ({user.id}): {e}")
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
        await ctx.send(
            f"Trap configured: **{threshold}** identical messages in **{time_window}** seconds."
        )

    @commands.hybrid_command(
        name="traplog",
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
        await ctx.send(f"Trap timeout logs will be sent to {channel.mention}.")

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