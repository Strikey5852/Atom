import os
import json
import discord
from discord.ext import commands
from discord import app_commands

class StickyMessage(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._cooldown_channels = set()

        if os.path.exists("/data"):
            DATA_DIR = "/data"
        else:
            DATA_DIR = "data"

        self.sticky_json_path = f"{DATA_DIR}/sticky.json"

    def _ensure_sticky_json(self):
        os.makedirs(os.path.dirname(self.sticky_json_path), exist_ok=True)
        if not os.path.exists(self.sticky_json_path):
            with open(self.sticky_json_path, "w", encoding="utf-8") as jf:
                json.dump({}, jf)

    def load_all_stickies(self) -> dict:
        self._ensure_sticky_json()
        try:
            with open(self.sticky_json_path, "r", encoding="utf-8") as jf:
                data = json.load(jf) or {}
        except Exception:
            return {}

        normalized = {}
        for guild_id, channels in data.items():
            if isinstance(channels, dict):
                normalized[guild_id] = {
                    cid: {
                        "content": info.get("content", ""),
                        "last_message_id": info.get("last_message_id")
                    }
                    for cid, info in channels.items()
                }
        return normalized

    def save_all_stickies(self, data: dict):
        os.makedirs(os.path.dirname(self.sticky_json_path), exist_ok=True)
        with open(self.sticky_json_path, "w", encoding="utf-8") as jf:
            json.dump(data, jf, indent=2)

    async def repost_sticky(self, message: discord.Message):
        data = self.load_all_stickies()
        guild_id = str(message.guild.id)
        channel_id = str(message.channel.id)

        sticky_info = data[guild_id][channel_id]
        content = sticky_info.get("content")
        last_msg_id = sticky_info.get("last_message_id")

        self._cooldown_channels.add(channel_id)
        try:
            # delete old sticky
            if last_msg_id:
                try:
                    last_msg = await message.channel.fetch_message(last_msg_id)
                    await last_msg.delete()
                except Exception:
                    pass

            # send new sticky and update JSON
            new_msg = await message.channel.send(content)
            sticky_info["last_message_id"] = new_msg.id
            data[guild_id][channel_id] = sticky_info
            self.save_all_stickies(data)
        finally:
            self._cooldown_channels.discard(channel_id)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild:
            return
        # Ignore other bots
        if message.author.bot and message.author.id != self.bot.user.id:
            return

        data = self.load_all_stickies()
        guild_id = str(message.guild.id)
        channel_id = str(message.channel.id)

        if guild_id not in data or channel_id not in data[guild_id]:
            return
        sticky_info = data[guild_id][channel_id]

        # Ignore if message is the last sticky or channel is in cooldown
        if message.id == sticky_info.get("last_message_id"):
            return
        if channel_id in self._cooldown_channels:
            return
        
        await self.repost_sticky(message)

    @commands.hybrid_command(name="setsticky", description="Set a sticky message in a specific channel.")
    @app_commands.describe(channel="The channel to set the sticky message in.", content="The message content to stick.")
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def set_sticky(self, ctx: commands.Context, channel: discord.TextChannel, content: str):
        data = self.load_all_stickies()
        guild_id = str(ctx.guild.id)
        channel_id = str(channel.id)

        self._cooldown_channels.add(channel_id)

        try:
            # delete existing sticky if present
            if guild_id in data and channel_id in data[guild_id]:
                last_msg_id = data[guild_id][channel_id].get("last_message_id")
                if last_msg_id:
                    try:
                        last_msg = await channel.fetch_message(last_msg_id)
                        await last_msg.delete()
                    except Exception:
                        pass

            # send new sticky message
            msg = await channel.send(content)
            if guild_id not in data:
                data[guild_id] = {}
            data[guild_id][channel_id] = {"content": content, "last_message_id": msg.id}
            self.save_all_stickies(data)
        finally:
            await ctx.send(f"Sticky message set in {channel.mention}")
            self._cooldown_channels.discard(channel_id)

    @commands.hybrid_command(name="removesticky", description="Remove the sticky message from a specific channel.")
    @app_commands.describe(channel="The channel to remove the sticky message from.")
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def remove_sticky(self, ctx: commands.Context, channel: discord.TextChannel):
        data = self.load_all_stickies()
        guild_id = str(ctx.guild.id)
        channel_id = str(channel.id)

        if guild_id not in data or channel_id not in data[guild_id]:
            return await ctx.send(f"No sticky message found in {channel.mention}.")

        sticky_info = data[guild_id][channel_id]
        last_id = sticky_info.get("last_message_id")

        if last_id:
            try:
                last_msg = await channel.fetch_message(last_id)
                await last_msg.delete()
            except Exception:
                pass

        del data[guild_id][channel_id]
        if not data[guild_id]:
            del data[guild_id]

        self.save_all_stickies(data)
        await ctx.send(f"Removed sticky message from {channel.mention}")

    @commands.hybrid_command(name="liststickies", description="Show all sticky messages in this server.")
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def list_stickies(self, ctx: commands.Context):
        data = self.load_all_stickies()
        guild_id = str(ctx.guild.id)

        if guild_id not in data or not data[guild_id]:
            return await ctx.send("No sticky messages set in this server.")

        lines = []
        for i, (ch_id, info) in enumerate(data[guild_id].items(), start=1):
            ch = ctx.guild.get_channel(int(ch_id))
            channel_name = ch.mention if ch else f"Deleted Channel ({ch_id})"
            content_preview = info['content'][:80].replace("\n", " ")
            if len(info['content']) > 80:
                content_preview += "..."
            lines.append(f"{i}. {channel_name} — {content_preview}")

        message_text = "Sticky Messages:\n" + "\n".join(lines)
        await ctx.send(message_text)

async def setup(bot):
    await bot.add_cog(StickyMessage(bot))
