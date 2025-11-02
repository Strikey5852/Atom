from discord import app_commands
from discord.ext import commands
import random
import re

MAX_TOTAL_DICE = 1000
DISCORD_LIMIT = 2000  # Discord’s max message length

class DiceRoller(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="roll",description="Roll dice in NdM format, e.g. 2d6, 1d20+3, or 2d6+1d8-2")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(dice="The dice to roll in NdM format (e.g. 2d6, 1d20+3, or 2d6+1d8-2)")
    async def roll_dice(self, ctx: commands.Context, dice: str):
        # Parse dice and modifiers
        pattern = r'([+-]?\d*d\d+|[+-]?\d+)'
        parts = re.findall(pattern, dice.replace(" ", "").lower())

        if not parts or not any('d' in p for p in parts):
            await ctx.send("Invalid format! Examples: `2d6`, `1d20+3`, or `2d6+1d8-2`.")
            return

        total_dice = 0
        total = 0
        dice_groups = []

        # Roll each group
        for part in parts:
            if 'd' not in part:  # modifier only
                try:
                    mod = int(part)
                    total += mod
                    dice_groups.append({"type": "mod", "value": mod})
                except ValueError:
                    await ctx.send("Invalid number in expression.")
                    return
                continue

            match = re.fullmatch(r'([+-]?)(\d*)d(\d+)', part)
            if not match:
                await ctx.send(f"Invalid part in expression: `{part}`")
                return

            sign, num_str, sides_str = match.groups()
            num = int(num_str) if num_str else 1
            sides = int(sides_str)
            sign_mult = -1 if sign == '-' else 1

            total_dice += num
            if total_dice > MAX_TOTAL_DICE:
                await ctx.send(f"Total number of dice exceeds the limit of {MAX_TOTAL_DICE}.")
                return
            if num < 1 or sides < 1 or sides > 1000:
                await ctx.send("Dice must have 1–1000 sides, and at least 1 die per group.")
                return

            rolls = [random.randint(1, sides) for _ in range(num)]
            subtotal = sum(rolls) * sign_mult
            total += subtotal

            dice_groups.append({
                "type": "dice",
                "num": num,
                "sides": sides,
                "sign_mult": sign_mult,
                "rolls": rolls
            })

        # Build display strings
        def build_group_string(group, limit_rolls=None):
            """Generate a readable group string, truncating if limit_rolls is given."""
            if group["type"] == "mod":
                return str(group["value"])
            
            rolls = group["rolls"]
            sides = group["sides"]
            
            rolls_str_list = [f"**{r}**" if r == 1 or r == sides else str(r) for r in rolls]

            if limit_rolls and len(rolls_str_list) > limit_rolls:
                rolls_str_list = rolls_str_list[:limit_rolls] + ["..."]

            rolls_str = ', '.join(rolls_str_list)
            prefix = "-" if group["sign_mult"] == -1 else ""
            return f"{prefix}{group['num']}d{group['sides']} ({rolls_str})"

        def join_groups(strings):
            msg = strings[0]
            for r in strings[1:]:
                if r.startswith('-'):
                    msg += f"\n - {r[1:]}"
                else:
                    msg += f"\n + {r}"
            return msg

        # Start with all rolls shown
        group_strings = [build_group_string(g) for g in dice_groups]
        full_message = join_groups(group_strings)

        # Aggressive truncation loop if too long
        if len(full_message) > DISCORD_LIMIT:
            # Determine total roll count (only dice groups)
            total_rolls = sum(len(g["rolls"]) for g in dice_groups if g["type"] == "dice")

            # Start truncation progressively
            limit_ratio = 1.0
            while len(full_message) > DISCORD_LIMIT and limit_ratio > 0.01:
                truncated_group_strings = []
                for g in dice_groups:
                    if g["type"] == "mod":
                        truncated_group_strings.append(str(g["value"]))
                        continue
                    roll_count = len(g["rolls"])
                    limit_rolls = max(1, int(roll_count * limit_ratio))
                    truncated_group_strings.append(build_group_string(g, limit_rolls))
                full_message = join_groups(truncated_group_strings)
                limit_ratio *= 0.8  # trim more aggressively next iteration

            # Final fail-safe
            if len(full_message) > DISCORD_LIMIT:
                await ctx.send("Result too large to display even after truncation.")
                return

        await ctx.send(f"**Result**: {full_message}\n**Total**: {total}")


async def setup(bot):
    await bot.add_cog(DiceRoller(bot))
