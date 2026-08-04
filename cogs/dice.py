import logging
import random
import re

from discord import app_commands
from discord.ext import commands

logger = logging.getLogger(__name__)

MAX_TOTAL_DICE = 1000
DISCORD_LIMIT = 2000  # Discord's max message length

# Regex: matches dice groups (NdM) and standalone modifiers (+N / -N), with optional signs
PART_PATTERN = re.compile(r'([+-]?\d*d\d+|[+-]?\d+)')
DICE_GROUP_PATTERN = re.compile(r'([+-]?)(\d*)d(\d+)')


class DiceRoller(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        logger.debug("[Dice] Cog initialized")

    @commands.hybrid_command(name="roll", description="Roll dice in NdM format, e.g. 2d6, 1d20+3, or 2d6+1d8-2")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(dice="The dice to roll in NdM format (e.g. 2d6, 1d20+3, or 2d6+1d8-2)")
    async def roll_dice(self, ctx: commands.Context, dice: str):
        logger.info(
            "[Dice] roll invoked: dice='%s' author=%s guild=%s channel=%s",
            dice, ctx.author, getattr(ctx.guild, "name", None),
            getattr(ctx.channel, "name", getattr(ctx.channel, "id", None)),
        )

        # Parse dice and modifiers
        parts = PART_PATTERN.findall(dice.replace(" ", "").lower())

        if not parts or not any('d' in p for p in parts):
            logger.warning("[Dice] Invalid format: dice='%s'", dice)
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
                    logger.warning("[Dice] Invalid number in expression: dice='%s' part='%s'", dice, part)
                    await ctx.send("Invalid number in expression.")
                    return
                continue

            match = DICE_GROUP_PATTERN.fullmatch(part)
            if not match:
                logger.warning("[Dice] Invalid part in expression: dice='%s' part='%s'", dice, part)
                await ctx.send(f"Invalid part in expression: `{part}`")
                return

            sign, num_str, sides_str = match.groups()
            num = int(num_str) if num_str else 1
            sides = int(sides_str)
            sign_mult = -1 if sign == '-' else 1

            total_dice += num
            if total_dice > MAX_TOTAL_DICE:
                logger.warning("[Dice] Too many dice: %d exceeds limit %d", total_dice, MAX_TOTAL_DICE)
                await ctx.send(f"Total number of dice exceeds the limit of {MAX_TOTAL_DICE}.")
                return
            if num < 1 or sides < 1 or sides > 1000:
                logger.warning("[Dice] Invalid dice spec: num=%d sides=%d", num, sides)
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

        # Build the full display string
        full_message = self._join_groups(
            [self._build_group_string(g) for g in dice_groups]
        )

        # Truncate only if needed
        if len(full_message) > DISCORD_LIMIT:
            full_message = self._truncate_to_limit(dice_groups)
            if full_message is None:
                logger.error("[Dice] Result too large to display even after truncation: dice='%s'", dice)
                await ctx.send("Result too large to display even after truncation.")
                return

        logger.debug("[Dice] Roll completed: dice='%s' total=%d groups=%d", dice, total, len(dice_groups))
        await ctx.send(f"**Result**: {full_message}\n**Total**: {total}")

    @staticmethod
    def _build_group_string(group: dict, limit_rolls: int | None = None) -> str:
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

    @staticmethod
    def _join_groups(strings: list[str]) -> str:
        msg = strings[0]
        for r in strings[1:]:
            if r.startswith('-'):
                msg += f"\n - {r[1:]}"
            else:
                msg += f"\n + {r}"
        return msg

    def _truncate_to_limit(self, dice_groups: list[dict]) -> str | None:
        """Analytically determine per-group roll limits and rebuild the message once.

        Returns None if even the most aggressive truncation can't fit.
        Uses binary search on the per-group roll limit ratio.
        """
        # Extremely conservative baseline: 1 roll per group
        baseline_strings = [
            self._build_group_string(g, limit_rolls=1) for g in dice_groups
        ]
        baseline = self._join_groups(baseline_strings)
        if len(baseline) > DISCORD_LIMIT:
            return None

        # Binary search for the largest ratio that fits
        lo, hi = 1.0, max((len(g["rolls"]) for g in dice_groups if g["type"] == "dice"), default=1.0)
        best: str | None = None

        # First check if even the full message fits with ratio hi (it doesn't, we know)
        # So binary search between lo and hi
        while hi - lo > 0.01:
            mid = (lo + hi) / 2
            strings = [
                self._build_group_string(g, limit_rolls=max(1, int(len(g["rolls"]) * mid)))
                if g["type"] == "dice"
                else str(g["value"])
                for g in dice_groups
            ]
            msg = self._join_groups(strings)
            if len(msg) <= DISCORD_LIMIT:
                best = msg
                lo = mid  # Try a larger ratio (more rolls shown)
            else:
                hi = mid  # Too long, try smaller ratio

        # Check final point (hi may produce a slightly different message)
        if best is not None:
            return best

        # Even the minimum couldn't fit
        if len(baseline) <= DISCORD_LIMIT:
            return baseline
        return None


async def setup(bot):
    await bot.add_cog(DiceRoller(bot))