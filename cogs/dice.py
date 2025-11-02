import discord
from discord import app_commands
from discord.ext import commands
import random
import re

class DiceRoller(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="roll", description="Roll dice in NdM format, e.g. 2d6 or 1d20+3")
    @app_commands.describe(dice="The dice to roll in NdM format (e.g. 2d6, 1d20+3, or 3d8-2)")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def roll_dice(self, ctx: commands.Context, dice: str):
        # Match patterns like 2d6, 1d20+3, or 3d8-2
        match = re.fullmatch(r'(\d+)d(\d+)([+-]\d+)?', dice.lower())
        if not match:
            await ctx.send("Invalid format! Use `NdM` or `NdM±X` (e.g. 2d6, 1d20+3, or 3d8-2).")
            return

        num, sides, modifier = match.groups()
        num, sides = int(num), int(sides)
        modifier = int(modifier) if modifier else 0

        # Limit dice and sides to prevent abuse
        if num > 100 or sides > 1000:
            await ctx.send("Too many dice or sides! Max 100 dice with up to 1000 sides each.")
            return
        if num < 1 or sides < 1:
            await ctx.send("You must roll at least 1 die with 1 or more sides.")
            return

        # Roll the dice
        rolls = [random.randint(1, sides) for _ in range(num)]

        # Highlight critical rolls (max rolls)
        rolls_str = ', '.join(f"**{r}**" if r == sides else str(r) for r in rolls)

        total = sum(rolls) + modifier
        mod_text = f" {modifier:+}" if modifier else ""

        # Send the formatted result
        await ctx.send(f"**Result**: {num}d{sides}{mod_text} ({rolls_str})\n**Total**: {total}")

async def setup(bot):
    await bot.add_cog(DiceRoller(bot))
