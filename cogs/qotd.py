import os
import json
import random
import discord
from discord.ext import commands
from discord import app_commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from database import get_database

class QOTD(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler()
        
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
                "ping_role_id": guild_data.get("ping_role_id")
            }

        return normalized

    async def save_all_guild_questions(self, data: dict):
        """Save all guild questions to the database."""
        try:
            await self.db.set_all(self.filename, data)
        except Exception as e:
            print(f"[QOTD] Error saving: {e}")

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
        g = data.get(str(guild_id), {"questions": [], "channel_id": None, "warning_channel_id": None})
        g["questions"] = questions
        data[str(guild_id)] = g
        self.db.set_all_cached(self.filename, data)
        await self.save_all_guild_questions(data)

    async def set_channel_for_guild(self, guild_id: int, channel_id: int):
        """Set the QOTD channel for a guild."""
        data = self.db.get_all_cached(self.filename)
        g = data.get(str(guild_id), {"questions": [], "channel_id": None, "warning_channel_id": None})
        g["channel_id"] = channel_id
        data[str(guild_id)] = g
        self.db.set_all_cached(self.filename, data)
        await self.save_all_guild_questions(data)

    async def set_warning_channel_for_guild(self, guild_id: int, channel_id: int):
        """Set the warning channel for a guild."""
        data = self.db.get_all_cached(self.filename)
        g = data.get(str(guild_id), {"questions": [], "channel_id": None, "warning_channel_id": None})
        g["warning_channel_id"] = channel_id
        data[str(guild_id)] = g
        self.db.set_all_cached(self.filename, data)
        await self.save_all_guild_questions(data)

    def get_guild_settings(self, guild_id: int):
        """Get settings for a guild from cache."""
        data = self.db.get_all_cached(self.filename)
        return data.get(str(guild_id), {"questions": [], "channel_id": None, "warning_channel_id": None})

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

        # Save changes
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

    @commands.hybrid_command(name="addqotd", description="Add question(s) to the QOTD list. (Seperate by newlines; use \\n for slash commands.)")
    @commands.has_permissions(administrator=True)
    @app_commands.allowed_installs(guilds=True, users=False)
    @commands.guild_only()
    @app_commands.describe(question="Question(s) to add (Seperate by newlines; use \\n for slash commands.)")
    async def add_qotd(self, ctx, *, question: str):
        gid = ctx.guild.id
        questions = await self.get_questions_for_guild(gid)

        normalized = question.replace("\\n", "\n")
        parts = [q.strip() for q in normalized.splitlines() if q.strip()]

        for q in parts:
            questions.append(q)

        await self.set_questions_for_guild(gid, questions)
        display = "\n".join(f"{i+1}. {q}" for i, q in enumerate(parts))
        await ctx.send(f"Added {len(parts)} question(s) to this server:\n{display}")

    @commands.hybrid_command(name="removeqotd", description="Remove a question by its number (see /listqotd)")
    @commands.has_permissions(administrator=True)
    @app_commands.allowed_installs(guilds=True, users=False)
    @commands.guild_only()
    @app_commands.describe(number="The question number to remove (from /listqotd)")
    async def remove_qotd(self, ctx, number: int):
        gid = ctx.guild.id
        questions = await self.get_questions_for_guild(gid)
        if number < 1 or number > len(questions):
            await ctx.send("Invalid question number.")
            return
        removed_question = questions.pop(number - 1)
        await self.set_questions_for_guild(gid, questions)
        await ctx.send(f"Removed question #{number}: `{removed_question}` from this server")

    @commands.hybrid_command(name="listqotd", description="Show all current questions")
    @commands.has_permissions(administrator=True)
    @app_commands.allowed_installs(guilds=True, users=False)
    @commands.guild_only()
    async def list_qotd(self, ctx):
        gid = ctx.guild.id
        questions = await self.get_questions_for_guild(gid)
        if not questions:
            await ctx.send("No questions in the list for this server.")
            return
        display = "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))
        await ctx.send(f"**Current Questions for this server:**\n{display}")

    @commands.hybrid_command(name="qotdnow", description="Manually post a random question now")
    @commands.has_permissions(administrator=True)
    @app_commands.allowed_installs(guilds=True, users=False)
    @commands.guild_only()
    async def qotd_now(self, ctx):
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
        await self.set_channel_for_guild(ctx.guild.id, channel.id)
        await ctx.send(f"QOTD channel set to {channel.mention}")

    @commands.hybrid_command(name="setqotdwarn", description="Set the channel where QOTD warnings will be posted for this server")
    @commands.has_permissions(administrator=True)
    @app_commands.allowed_installs(guilds=True, users=False)
    @commands.guild_only()
    @app_commands.describe(channel="The text channel for QOTD warnings")
    async def set_qotd_warning_channel(self, ctx, channel: discord.TextChannel):
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
        guild_data = data.setdefault(str(ctx.guild.id), {
            "questions": [],
            "channel_id": None,
            "warning_channel_id": None,
            "ping_role_id": None
        })
        guild_data["ping_role_id"] = role.id
        data[str(ctx.guild.id)] = guild_data
        self.db.set_all_cached(self.filename, data)
        await self.save_all_guild_questions(data)
        
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

async def setup(bot):
    await bot.add_cog(QOTD(bot))