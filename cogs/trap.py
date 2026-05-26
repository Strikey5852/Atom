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

    def __init__(self, cog: "Trap"):
        self.cog = cog
        super().__init__(timeout=None)

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
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "Only administrators can use this action.", ephemeral=True
            )
            return False
        return True

    async def _resolve_target(self, interaction: discord.Interaction):
        """Look up the stored user/guild from cog's stored actions using message id."""
        action = self.cog._stored_actions.get(interaction.message.id)
        if not action:
            await interaction.response.send_message(
                "This action is no longer valid.", ephemeral=True
            )
            return None, None
        return action["user_id"], action["guild_id"]

    async def _disable_buttons(self, interaction: discord.Interaction):
        self.ban_btn.disabled = True
        self.forgive_btn.disabled = True
        await interaction.message.edit(view=self)

    async def ban_callback(self, interaction: discord.Interaction):
        if not await self._check_admin(interaction):
            return

        user_id, guild_id = await self._resolve_target(interaction)
        if user_id is None:
            return

        guild = interaction.guild
        if not guild:
            await interaction.response.send_message("Could not resolve guild.", ephemeral=True)
            return

        try:
            user = await guild.fetch_member(user_id)
            if user:
                await guild.ban(user, reason=f"Trap ban action by {interaction.user}")
        except discord.NotFound:
            pass

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

        user_id, guild_id = await self._resolve_target(interaction)
        if user_id is None:
            return

        guild = interaction.guild
        if not guild:
            await interaction.response.send_message("Could not resolve guild.", ephemeral=True)
            return

        try:
            user = await guild.fetch_member(user_id)
            if user:
                await user.timeout(until=None, reason=f"Trap forgiven by {interaction.user}")
        except discord.NotFound:
            pass

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

        # Set of user_ids currently being processed (prevents duplicate concurrent work)
        self._pending_actions: set[int] = set()

    # ──────────────────────────────────────────────
    # Persistence
    # ──────────────────────────────────────────────

    async def load_config(self) -> dict:
        """Load trap config from the database, separating settings from action metadata."""
        try:
            data = await self.db.get_all(self.filename)
            if data:
                # Pop actions first so it doesn't pollute guild settings
                self._stored_actions = data.pop("_actions", {})
                # Everything left is guild config
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
            data = dict(self.trap_config)
            data["_actions"] = self._stored_actions
            await self.db.set_all(self.filename, data)
        except Exception as e:
            print(f"[Trap] Error saving config: {e}")

    def _store_action(self, message_id: int, channel_id: int, user_id: int, guild_id: int):
        self._stored_actions[message_id] = {
            "channel_id": channel_id,
            "user_id": user_id,
            "guild_id": guild_id,
        }

    # ──────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────

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

    def _prune_message_log(self, guild_id: int, user_id: int, time_window: float):
        now = time.time()
        log = self._message_log.get(guild_id, {}).get(user_id, [])
        self._message_log[guild_id][user_id] = [
            entry for entry in log if now - entry[0] <= time_window
        ]

    async def _purge_tracked_messages(
        self,
        guild: discord.Guild,
        tracked: list[tuple[float, str, int, int]],
    ):
        channel_groups: dict[int, list[int]] = {}
        for _, _, channel_id, msg_id in tracked:
            channel_groups.setdefault(channel_id, []).append(msg_id)

        for channel_id, msg_ids in channel_groups.items():
            channel = guild.get_channel(channel_id)
            if not channel:
                continue
            try:
                for i in range(0, len(msg_ids), 100):
                    batch = msg_ids[i:i + 100]
                    await channel.delete_messages(batch)
            except discord.Forbidden:
                print(f"[Trap] Missing manage_messages permission in {channel.name}")
            except discord.NotFound:
                pass
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
        if not log_channel_id:
            return
        channel = guild.get_channel(log_channel_id)
        if not channel:
            return

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
            if is_image:
                embed.set_image(url=att.url)
        elif message.stickers:
            sticker = message.stickers[0]
            embed.add_field(
                name="Sticker Payload",
                value=f"Name: {sticker.name} (ID: {sticker.id})",
                inline=False,
            )

        view = TrapActions(self)
        try:
            msg = await channel.send(embed=embed, view=view)
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

        # Register ONE persistent view that handles ALL trap action messages
        # The callbacks resolve user/guild from _stored_actions using the message id
        view = TrapActions(self)
        self.bot.add_view(view)

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

        self._message_log[guild_id_int][user_id].append(
            (time.time(), signature, message.channel.id, message.id)
        )

        self._prune_message_log(guild_id_int, user_id, time_window)

        tracked = self._message_log[guild_id_int][user_id]
        matching = [entry for entry in tracked if entry[1] == signature]

        if len(matching) >= threshold:
            if user_id in self._pending_actions:
                return
            self._pending_actions.add(user_id)

            try:
                # 1. Purge only the tracked spam messages
                await self._purge_tracked_messages(message.guild, matching)

                # 2. Timeout the user for 24h (on the Member object, not Guild)
                await user.timeout(
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
                self._message_log.get(guild_id_int, {}).pop(user_id, None)
                self._pending_actions.discard(user_id)

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