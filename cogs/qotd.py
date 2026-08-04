import io
import logging
import random
from datetime import datetime

import discord
from discord.ext import commands
from discord import app_commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from database import get_database

logger = logging.getLogger(__name__)

DEFAULT_GUILD_DATA = {
    "questions": [],
    "channel_id": None,
    "warning_channel_id": None,
    "ping_role_id": None,
}


class QOTD(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler()
        logger.debug("[QOTD] Cog initialized")

        self.db = get_database()
        self.filename = "qotd.json"

    async def load_all_guild_questions(self) -> dict:
        """Load all guild questions from the database."""
        try:
            data = await self.db.get_all(self.filename)
        except Exception:
            return {}

        # Ensure all guild data has the expected structure
        normalized = {}
        for gk, val in data.items():
            # Get existing data or create new with default values
            guild_data = val if isinstance(val, dict) else {}
            normalized[gk] = {
                "questions": guild_data.get("questions", []),
                "channel_id": guild_data.get("channel_id"),
                "warning_channel_id": guild_data.get("warning_channel_id"),
                "ping_role_id": guild_data.get("ping_role_id"),
            }

        return normalized

    async def save_all_guild_questions(self, data: dict, immediate: bool = False):
        """Save all guild questions to the database."""
        try:
            await self.db.set_all(self.filename, data, immediate=immediate)
        except Exception as e:
            logger.exception("[QOTD] Error saving: %s", e)

    async def get_questions_for_guild(self, guild_id: int) -> list:
        """Get questions for a guild, fetching fresh data if cache is stale."""
        data = await self.db.get_all(self.filename)
        g = data.get(str(guild_id))
        if not g:
            return []
        return g.get("questions", [])

    async def set_questions_for_guild(self, guild_id: int, questions: list):
        """Set questions for a guild and save to database."""
        data = self.db.get_all_cached(self.filename)
        g = data.get(str(guild_id), dict(DEFAULT_GUILD_DATA))
        g["questions"] = questions
        data[str(guild_id)] = g
        self.db.set_all_cached(self.filename, data)
        await self.save_all_guild_questions(data)

    async def set_channel_for_guild(self, guild_id: int, channel_id: int):
        """Set the QOTD channel for a guild."""
        data = self.db.get_all_cached(self.filename)
        g = data.get(str(guild_id), dict(DEFAULT_GUILD_DATA))
        g["channel_id"] = channel_id
        data[str(guild_id)] = g
        self.db.set_all_cached(self.filename, data)
        await self.save_all_guild_questions(data)

    async def set_warning_channel_for_guild(self, guild_id: int, channel_id: int):
        """Set the warning channel for a guild."""
        data = self.db.get_all_cached(self.filename)
        g = data.get(str(guild_id), dict(DEFAULT_GUILD_DATA))
        g["warning_channel_id"] = channel_id
        data[str(guild_id)] = g
        self.db.set_all_cached(self.filename, data)
        await self.save_all_guild_questions(data)

    def get_guild_settings(self, guild_id: int):
        """Get settings for a guild from cache."""
        data = self.db.get_all_cached(self.filename)
        return data.get(str(guild_id), dict(DEFAULT_GUILD_DATA))

    async def send_warning(self, guild_id: int, message: str):
        """Send a warning message to the warning channel."""
        data = self.db.get_all_cached(self.filename)
        guild_data = data.get(str(guild_id), {})
        warn_id = guild_data.get("warning_channel_id")

        if warn_id:
            warning_channel = self.bot.get_channel(warn_id)
            if warning_channel:
                try:
                    await warning_channel.send(message)
                except Exception:
                    pass

    async def send_question(self, guild_id: int) -> bool:
        """Send a random question to the QOTD channel."""
        data = self.db.get_all_cached(self.filename)
        gk = str(guild_id)
        guild_data = data.get(gk, {})
        questions = guild_data.get("questions", [])
        ch_id = guild_data.get("channel_id")

        if not questions or not ch_id:
            return False

        # Pick and remove a random question
        question = random.choice(questions)
        questions.remove(question)
        guild_data["questions"] = questions
        data[gk] = guild_data

        channel = self.bot.get_channel(ch_id)
        if not channel:
            return False
        try:
            # Get ping role if configured
            ping_text = ""
            ping_role_id = guild_data.get("ping_role_id")
            if ping_role_id:
                guild = channel.guild
                role = guild.get_role(ping_role_id)
                if role:
                    ping_text = f"{role.mention}"

            # Send the question with optional ping
            await channel.send(f"{ping_text} {question}")
        except Exception:
            return False

        # Send warnings to this guild if their question count is low
        warn_id = guild_data.get("warning_channel_id")
        if warn_id:
            warn_channel = self.bot.get_channel(warn_id)
            if warn_channel:
                if len(questions) == 0:
                    await warn_channel.send("No more questions left in this server's list! Add some with `/addqotd`.")
                elif len(questions) == 1:
                    await warn_channel.send("Only **1 question** remaining in this server's list!")

        # Save changes (debounced)
        self.db.set_all_cached(self.filename, data)
        await self.save_all_guild_questions(data)
        return True

    async def _scheduled_send_questions(self):
        """Scheduled task to send questions to all guilds."""
        for guild in self.bot.guilds:
            await self.send_question(guild.id)

    @commands.Cog.listener()
    async def on_ready(self):
        # Load data from database
        await self.load_all_guild_questions()

        if not self.scheduler.running:
            # Schedule every day at 08:00 PM IST
            self.scheduler.add_job(
                self._scheduled_send_questions,
                CronTrigger(hour=20, minute=00, timezone="Asia/Kolkata"),
            )
            self.scheduler.start()
            logger.info("[QOTD] Scheduler started (daily 8:00 PM IST).")

    @commands.hybrid_command(name="addqotd", description="Add question(s) to the QOTD list. (Seperate by newlines; use \\n for slash commands.)")
    @commands.has_permissions(administrator=True)
    @app_commands.allowed_installs(guilds=True, users=False)
    @commands.guild_only()
    @app_commands.describe(question="Question(s) to add (Seperate by newlines; use \\n for slash commands.)")
    async def add_qotd(self, ctx, *, question: str):
        logger.info("[QOTD] addqotd invoked by %s (guild=%s)", ctx.author, ctx.guild.name)
        gid = ctx.guild.id
        questions = await self.get_questions_for_guild(gid)

        normalized = question.replace("\\n", "\n")
        parts = [q.strip() for q in normalized.splitlines() if q.strip()]

        for q in parts:
            questions.append(q)

        await self.set_questions_for_guild(gid, questions)
        logger.info("[QOTD] Added %d question(s) for guild=%s", len(parts), ctx.guild.name)
        display = "\n".join(f"{i+1}. {q}" for i, q in enumerate(parts))
        await ctx.send(f"Added {len(parts)} question(s) to this server:\n{display}")

    @commands.hybrid_command(name="removeqotd", description="Remove a question by its number (see /listqotd)")
    @commands.has_permissions(administrator=True)
    @app_commands.allowed_installs(guilds=True, users=False)
    @commands.guild_only()
    @app_commands.describe(number="The question number to remove (from /listqotd)")
    async def remove_qotd(self, ctx, number: int):
        logger.info("[QOTD] removeqotd invoked by %s (guild=%s) number=%d", ctx.author, ctx.guild.name, number)
        gid = ctx.guild.id
        questions = await self.get_questions_for_guild(gid)
        if number < 1 or number > len(questions):
            await ctx.send("Invalid question number.")
            return
        removed_question = questions.pop(number - 1)
        await self.set_questions_for_guild(gid, questions)
        logger.info("[QOTD] Removed question #%d for guild=%s", number, ctx.guild.name)
        await ctx.send(f"Removed question #{number}: `{removed_question}` from this server")

    @commands.hybrid_command(name="listqotd", description="Show all current questions")
    @commands.has_permissions(administrator=True)
    @app_commands.allowed_installs(guilds=True, users=False)
    @commands.guild_only()
    async def list_qotd(self, ctx):
        logger.info("[QOTD] listqotd invoked by %s (guild=%s)", ctx.author, ctx.guild.name)
        gid = ctx.guild.id
        questions = await self.get_questions_for_guild(gid)
        if not questions:
            await ctx.send("No questions in the list for this server.")
            return

        # Build all lines first
        lines = [f"{i+1}. {q}" for i, q in enumerate(questions)]

        # If everything fits in one message, send it simply
        display = "\n".join(lines)
        if len(display) <= 1800:
            await ctx.send(f"**Current Questions for this server:**\n{display}")
            return

        # Otherwise, chunk into multiple messages under the Discord limit
        total_pages = 1
        current_chunk = []
        current_len = 0
        header = "**Current Questions for this server:**"

        for line in lines:
            line_len = len(line) + 1  # +1 for newline
            if current_len + line_len > 1800 and current_chunk:
                page_text = "\n".join(current_chunk)
                await ctx.send(f"{header}\n{page_text}\n\n*Page {total_pages}*")
                current_chunk = [line]
                current_len = line_len
                total_pages += 1
            else:
                current_chunk.append(line)
                current_len += line_len

        # Send the final chunk
        if current_chunk:
            page_text = "\n".join(current_chunk)
            footer = f"\n\n*Page {total_pages}*"
            await ctx.send(f"{header}\n{page_text}{footer}")

        logger.info("[QOTD] listqotd displayed %d questions in %d pages (guild=%s)", len(questions), total_pages, ctx.guild.name)

    @commands.hybrid_command(name="qotdnow", description="Manually post a random question now")
    @commands.has_permissions(administrator=True)
    @app_commands.allowed_installs(guilds=True, users=False)
    @commands.guild_only()
    async def qotd_now(self, ctx):
        logger.info("[QOTD] qotdnow invoked by %s (guild=%s)", ctx.author, ctx.guild.name)
        success = await self.send_question(ctx.guild.id)
        if success:
            await ctx.send("Sent a question manually!")
        else:
            await ctx.send("No available question or QOTD channel not set")

    @commands.hybrid_command(name="setqotdchannel", description="Set the channel where QOTD will be posted for this server")
    @commands.has_permissions(administrator=True)
    @app_commands.allowed_installs(guilds=True, users=False)
    @commands.guild_only()
    @app_commands.describe(channel="The text channel for QOTD postings")
    async def set_qotd_channel(self, ctx, channel: discord.TextChannel):
        logger.info("[QOTD] setqotdchannel by %s -> %s (guild=%s)", ctx.author, channel.name, ctx.guild.name)
        await self.set_channel_for_guild(ctx.guild.id, channel.id)
        await ctx.send(f"QOTD channel set to {channel.mention}")

    @commands.hybrid_command(name="setqotdwarn", description="Set the channel where QOTD warnings will be posted for this server")
    @commands.has_permissions(administrator=True)
    @app_commands.allowed_installs(guilds=True, users=False)
    @commands.guild_only()
    @app_commands.describe(channel="The text channel for QOTD warnings")
    async def set_qotd_warning_channel(self, ctx, channel: discord.TextChannel):
        logger.info("[QOTD] setqotdwarn by %s -> %s (guild=%s)", ctx.author, channel.name, ctx.guild.name)
        await self.set_warning_channel_for_guild(ctx.guild.id, channel.id)
        await ctx.send(f"QOTD warning channel set to {channel.mention}")

    @commands.hybrid_command(name="setqotdping", description="Set a role to ping when posting QOTD")
    @commands.has_permissions(administrator=True)
    @app_commands.allowed_installs(guilds=True, users=False)
    @commands.guild_only()
    @app_commands.describe(role="The role to ping with each QOTD")
    async def set_qotd_ping(self, ctx, role: discord.Role):
        # Save the ping role setting for this guild
        data = self.db.get_all_cached(self.filename)
        guild_data = data.setdefault(str(ctx.guild.id), dict(DEFAULT_GUILD_DATA))
        guild_data["ping_role_id"] = role.id
        data[str(ctx.guild.id)] = guild_data
        self.db.set_all_cached(self.filename, data)
        await self.save_all_guild_questions(data)
        logger.info("[QOTD] setqotdping by %s -> role %s (guild=%s)", ctx.author, role.name, ctx.guild.name)

        await ctx.send(f"QOTD will now ping {role.mention}")

    @commands.hybrid_command(name="qotdinfo", description="Show the QOTD settings for this server")
    @commands.has_permissions(administrator=True)
    @app_commands.allowed_installs(guilds=True, users=False)
    @commands.guild_only()
    async def qotd_settings(self, ctx):
        guild_id = str(ctx.guild.id)
        data = self.db.get_all_cached(self.filename)
        guild_setting = data.get(guild_id, {})
        ch = guild_setting.get("channel_id")
        warn = guild_setting.get("warning_channel_id")
        ping_role = guild_setting.get("ping_role_id")
        parts = []
        if ch:
            channel = self.bot.get_channel(ch)
            parts.append(f"QOTD channel: {channel.mention if channel else str(ch)}")
        else:
            parts.append("QOTD channel: Not set")
        if warn:
            wchannel = self.bot.get_channel(warn)
            parts.append(f"Warning channel: {wchannel.mention if wchannel else str(warn)}")
        else:
            parts.append("Warning channel: Not set")
        if ping_role:
            role = ctx.guild.get_role(ping_role)
            parts.append(f"Ping role: {role.mention if role else str(ping_role)}")
        else:
            parts.append("Ping role: Not set")
        await ctx.send("\n".join(parts))

    @commands.hybrid_command(name="exportqotd", description="Export all past QOTD questions from the QOTD channel to a text file")
    @commands.has_permissions(administrator=True)
    @app_commands.allowed_installs(guilds=True, users=False)
    @commands.guild_only()
    async def export_qotd(self, ctx):
        logger.info("[QOTD] exportqotd invoked by %s (guild=%s)", ctx.author, ctx.guild.name)
        gid = ctx.guild.id
        guild_data = self.get_guild_settings(gid)
        ch_id = guild_data.get("channel_id")
        ping_role_id = guild_data.get("ping_role_id")

        if not ch_id:
            await ctx.send("QOTD channel is not set for this server. Use `/setqotdchannel` first.")
            return
        if not ping_role_id:
            await ctx.send("QOTD ping role is not set for this server. Use `/setqotdping` first.")
            return

        channel = self.bot.get_channel(ch_id)
        if not channel:
            await ctx.send("Could not find the QOTD channel.")
            return

        role = ctx.guild.get_role(ping_role_id)
        if not role:
            await ctx.send("Could not find the QOTD ping role.")
            return

        questions = []
        async for message in channel.history(limit=None):
            if role in message.role_mentions:
                content = message.content
                for mention in message.role_mentions:
                    content = content.replace(mention.mention, "").strip()
                if content:
                    questions.append(content)

        if not questions:
            await ctx.send("No QOTD messages found in the channel.")
            return

        # Build the text file
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines = [
            f"QOTD History for {ctx.guild.name}",
            f"Exported on {now}",
            "----------------------------------------",
        ]
        for i, q in enumerate(questions, 1):
            lines.append(f"{i}. {q}")

        file_content = "\n".join(lines)
        buffer = io.BytesIO(file_content.encode("utf-8"))
        file = discord.File(buffer, filename="qotd_history.txt")
        await ctx.send(f"Found **{len(questions)}** QOTD question(s).", file=file)
        logger.info("[QOTD] exportqotd exported %d questions (guild=%s)", len(questions), ctx.guild.name)


async def setup(bot):
    await bot.add_cog(QOTD(bot))