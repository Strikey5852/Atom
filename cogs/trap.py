import asyncio
import json
import os

import discord
from discord import app_commands
from discord.ext import commands

from database import get_database


class Trap(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        self.db = get_database()
        self.filename = "trap.json"
        
        self.trap_channels = {}

    async def load_traps(self) -> dict:
        """Load trap channels from the database."""
        try:
            self.trap_channels = await self.db.get_all(self.filename)
        except Exception as e:
            print(f"[Trap] Error loading traps: {e}")
            self.trap_channels = {}
        return self.trap_channels

    async def save_traps(self):
        """Save trap channels to the database."""
        try:
            await self.db.set_all(self.filename, self.trap_channels)
        except Exception as e:
            print(f"[Trap] Error saving traps: {e}")

    @commands.Cog.listener()
    async def on_ready(self):
        # Load traps from database
        await self.load_traps()

    @commands.hybrid_command(
        name="settrap",
        description="Set a channel as the trap channel.",
    )
    @commands.has_permissions(administrator=True)
    @app_commands.allowed_installs(guilds=True, users=False)
    @commands.guild_only()
    @app_commands.describe(channel="The channel to set as a trap")
    async def set_trap(self, ctx, channel: discord.TextChannel):
        guild_id = str(ctx.guild.id)
        self.trap_channels[guild_id] = channel.id
        await self.save_traps()
        await ctx.send(
            f"{channel.mention} is now the trap channel. Any message sent here will result in a ban."
        )

    @commands.hybrid_command(
        name="removetrap", description="Remove the trap channel for this server."
    )
    @commands.has_permissions(administrator=True)
    @app_commands.allowed_installs(guilds=True, users=False)
    @commands.guild_only()
    async def remove_trap(self, ctx):
        guild_id = str(ctx.guild.id)
        if guild_id in self.trap_channels:
            del self.trap_channels[guild_id]
            await self.save_traps()
            await ctx.send("Trap channel has been disabled.")
        else:
            await ctx.send("No trap channel is currently set.")

    @commands.Cog.listener()
    async def on_message(self, message):
        # Ignore bots and DMs
        if message.author.bot or not message.guild:
            return

        guild_id = str(message.guild.id)
        trap_channel_id = self.trap_channels.get(guild_id)

        if trap_channel_id is None:
            return

        if message.channel.id != trap_channel_id:
            return

        if message.author.guild_permissions.administrator:
            return

        # Retry ban every 5 seconds, up to 6 attempts (30 seconds total)
        max_attempts = 6
        for attempt in range(max_attempts):
            try:
                await message.guild.ban(
                    message.author,
                    reason=f"Triggered trap channel: #{message.channel.name}",
                    delete_message_seconds=86400,
                )
                print(
                    f"[TRAP] Banned {message.author} from {message.guild.name} "
                )
                return  # Success
            except Exception as e:
                if attempt < max_attempts - 1:
                    print(
                        f"[TRAP] Ban attempt {attempt + 1} failed for {message.author} "
                        f"in {message.guild.name}: {e}. Retrying in 5s..."
                    )
                    await asyncio.sleep(5)
                else:
                    print(
                        f"[TRAP] All {max_attempts} ban attempts failed for {message.author} "
                        f"in {message.guild.name}. Last error: {e}"
                    )

async def setup(bot):
    await bot.add_cog(Trap(bot))