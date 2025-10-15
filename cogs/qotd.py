import os
import random
import discord
from discord.ext import commands
from discord import app_commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

class QOTD(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler()
        self.file_path = "data/qotd.txt"
        self.channel_id = 1073447676307320963
        self.warning_channel_id = 1019974638652112967

    # --------------------------------
    # Utility functions
    # --------------------------------
    def read_questions(self):
        """Read all questions from file."""
        if not os.path.exists(self.file_path):
            open(self.file_path, "w").close()
        with open(self.file_path, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]

    def write_questions(self, questions):
        """Overwrite the file with given questions."""
        with open(self.file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(questions) + ("\n" if questions else ""))

    async def send_warning(self, message: str):
        """Send a warning message to the configured warning channel."""
        warning_channel = self.bot.get_channel(self.warning_channel_id)
        if warning_channel:
            await warning_channel.send(f"{message}")
        else:
            print("Warning channel not found!")

    # --------------------------------
    # Main QOTD logic
    # --------------------------------
    async def send_question(self):
        """Send a random question to the QOTD channel."""
        channel = self.bot.get_channel(self.channel_id)
        if not channel:
            print("QOTD channel not found!")
            return

        questions = self.read_questions()

        question = random.choice(questions)
        await channel.send(f"<@&1073455091241193524> {question}")

        # Remove asked question from the 
        questions.remove(question)
        self.write_questions(questions)

        questions = self.read_questions()
        count = len(questions)

        if count == 0:
            await self.send_warning("No more questions left in the list! Add some with `/addqotd`.")
            return

        if count == 1:
            await self.send_warning("Only **1 question** remaining in the QOTD list!")

    # --------------------------------
    # Startup and scheduler
    # --------------------------------
    @commands.Cog.listener()
    async def on_ready(self):
        if not self.scheduler.running:
            # Schedule every day at 08:00 PM IST
            self.scheduler.add_job(
                self.send_question,
                CronTrigger(hour=20, minute=00, timezone="Asia/Kolkata"),
            )
            self.scheduler.start()
            print("QOTD scheduler started")

    # --------------------------------
    # Slash commands
    # --------------------------------
    @app_commands.command(name="addqotd", description="Add a new question to the QOTD list")
    async def add_qotd(self, interaction: discord.Interaction, question: str):
        questions = self.read_questions()
        questions.append(question.strip())
        self.write_questions(questions)
        await interaction.response.send_message(f"Added question: `{question}`", ephemeral=False)

    @app_commands.command(name="removeqotd", description="Remove a question by its number (see /listqotd)")
    async def remove_qotd(self, interaction: discord.Interaction, number: int):
        questions = self.read_questions()
        if number < 1 or number > len(questions):
            await interaction.response.send_message("Invalid question number.", ephemeral=False)
            return
        removed_question = questions.pop(number - 1)
        self.write_questions(questions)
        await interaction.response.send_message(f"Removed question #{number}: `{removed_question}`", ephemeral=False)

    @app_commands.command(name="listqotd", description="Show all current questions")
    async def list_qotd(self, interaction: discord.Interaction):
        questions = self.read_questions()
        if not questions:
            await interaction.response.send_message("No questions in the list.", ephemeral=False)
            return

        display = "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))
        await interaction.response.send_message(f"**Current Questions:**\n{display}", ephemeral=False)

    @app_commands.command(name="qotdnow", description="Manually post a random question now")
    async def qotd_now(self, interaction: discord.Interaction):
        await self.send_question()
        await interaction.response.send_message("Sent a question manually!", ephemeral=True)

async def setup(bot):
    await bot.add_cog(QOTD(bot))
