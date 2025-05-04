from abc import ABCMeta
import discord
from discord.ext import commands
from discord import Embed
from utils.config_manager import ConfigManager
from datetime import datetime


class Logging(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config_manager = ConfigManager('config.json')
        self.config = self.config_manager.load_config()  # Load the full config
        self.logging_config = self.config.get('logging', {})  # Get only the logging section

    async def send_log(self, channel_id, title, description, color, footer=None):
        """Send log embed to specified channel."""
        print(f"Sending log to channel ID: {channel_id}")
        channel = self.bot.get_channel(int(channel_id))
        if channel is None:
            print(f"Error: Channel ID {channel_id} not found!")
            return
        
        embed = Embed(title=title, description=description, color=color)
        embed.timestamp = datetime.utcnow()  # Add timestamp to embed

        if footer:
            embed.set_footer(text="awaaga")

        # Mention the user and link to channel
        if isinstance(description, str):
            description += f"\n\n**Channel:** <#{channel.id}>"
        else:
            description = f"{description}\n\n**Channel:** <#{channel.id}>"
        
        await channel.send(embed=embed)

    # Message Delete
    async def message_delete(self, message):
        if message.author.bot:
            return
        channel_id = self.logging_config.get('message_delete_channel')
        if channel_id:
            embed = Embed(
                title="Message Deleted",
                description=f"**User:** {message.author.mention} ({message.author})\n**Message:** {message.content}",
                color=discord.Color.blue()
            )
            await self.send_log(channel_id, embed.title, embed.description, discord.Color.blue())

    # Message Edit
    async def message_edit(self, before, after):
        if before.author.bot:
            return
        channel_id = self.logging_config.get('message_edit_channel')
        if channel_id:
            embed = Embed(
                title="Message Edited",
                description=f"**User:** {before.author.mention} ({before.author})\n**Before:** {before.content}\n**After:** {after.content}",
                color=discord.Color.blue()
            )
            await self.send_log(channel_id, embed.title, embed.description, discord.Color.blue())

    # Bulk Message Delete
    async def bulk_message_delete(self, messages):
        channel_id = self.logging_config.get('bulk_delete_channel')
        if channel_id:
            embed = Embed(
                title="Bulk Message Delete",
                description=f"**Deleted Messages:**\n" + "\n".join([f"- {msg.content}" for msg in messages]),
                color=discord.Color.red()
            )
            await self.send_log(channel_id, embed.title, embed.description, discord.Color.red(), footer=f"Deleted at {int(messages[0].created_at.timestamp())}")

    # Image Delete (message with image)
    async def image_message_delete(self, message):
        if message.attachments:
            channel_id = self.logging_config.get('image_delete_channel')
            if channel_id:
                embed = Embed(
                    title="Image Deleted",
                    description=f"**User:** {message.author.mention} ({message.author})\n**Image URL:** {message.attachments[0].url}",
                    color=discord.Color.red()
                )
                await self.send_log(channel_id, embed.title, embed.description, discord.Color.red())

    # Member Join
    async def on_member_join(self, member):
        channel_id = self.logging_config.get('member_join_channel')
        if channel_id:
            embed = Embed(
                title="Member Joined",
                description=f"**User:** {member.mention} ({member})\n**Joined at:** {member.joined_at}",
                color=discord.Color.green()
            )
            await self.send_log(channel_id, embed.title, embed.description, discord.Color.green(), footer=f"Joined at {int(member.joined_at.timestamp())}")

    # Member Leave
    async def on_member_remove(self, member):
        channel_id = self.logging_config.get('member_leave_channel')
        if channel_id:
            roles = ', '.join([role.name for role in member.roles if role.name != "@everyone"])
            embed = Embed(
                title="Member Left",
                description=f"**User:** {member.mention} ({member})\n**Roles:** {roles}\n**Left at:** {member.joined_at}",
                color=discord.Color.red()
            )
            await self.send_log(channel_id, embed.title, embed.description, discord.Color.red(), footer=f"Left at {int(member.joined_at.timestamp())}")

    # Member Role Add
    async def on_member_update(self, before, after):
        if before.roles != after.roles:
            added_roles = [role.name for role in after.roles if role not in before.roles]
            if added_roles:
                channel_id = self.logging_config.get('member_role_add_channel')
                if channel_id:
                    embed = Embed(
                        title="Role Added",
                        description=f"**User:** {after.mention} ({after})\n**Added Roles:** {', '.join(added_roles)}",
                        color=discord.Color.blue()
                    )
                    await self.send_log(channel_id, embed.title, embed.description, discord.Color.blue(), footer=f"Role added at {int(after.joined_at.timestamp())}")

            removed_roles = [role.name for role in before.roles if role not in after.roles]
            if removed_roles:
                channel_id = self.logging_config.get('member_role_remove_channel')
                if channel_id:
                    embed = Embed(
                        title="Role Removed",
                        description=f"**User:** {after.mention} ({after})\n**Removed Roles:** {', '.join(removed_roles)}",
                        color=discord.Color.red()
                    )
                    await self.send_log(channel_id, embed.title, embed.description, discord.Color.red(), footer=f"Role removed at {int(after.joined_at.timestamp())}")

    # Member Ban
    async def on_member_ban(self, guild, user):
        channel_id = self.logging_config.get('member_ban_channel')
        if channel_id:
            embed = Embed(
                title="Member Banned",
                description=f"**User:** {user.mention} ({user})",
                color=discord.Color.red()
            )
            await self.send_log(channel_id, embed.title, embed.description, discord.Color.red(), footer=f"Banned at {int(datetime.utcnow().timestamp())}")

    # Member Unban
    async def on_member_unban(self, guild, user):
        channel_id = self.logging_config.get('member_unban_channel')
        if channel_id:
            embed = Embed(
                title="Member Unbanned",
                description=f"**User:** {user.mention} ({user})",
                color=discord.Color.green()
            )
            await self.send_log(channel_id, embed.title, embed.description, discord.Color.green(), footer=f"Unbanned at {int(datetime.utcnow().timestamp())}")

    # Role Create
    async def on_guild_role_create(self, role):
        channel_id = self.logging_config.get('role_create_channel')
        if channel_id:
            embed = Embed(
                title="Role Created",
                description=f"**Role:** {role.name}\n**Role ID:** {role.id}",
                color=discord.Color.blue()
            )
            await self.send_log(channel_id, embed.title, embed.description, discord.Color.blue(), footer=f"Created at {int(datetime.utcnow().timestamp())}")

    # Role Delete
    async def on_guild_role_delete(self, role):
        channel_id = self.logging_config.get('role_delete_channel')
        if channel_id:
            embed = Embed(
                title="Role Deleted",
                description=f"**Role:** {role.name}\n**Role ID:** {role.id}",
                color=discord.Color.red()
            )
            await self.send_log(channel_id, embed.title, embed.description, discord.Color.red(), footer=f"Deleted at {int(datetime.utcnow().timestamp())}")

    # Role Update
    async def on_guild_role_update(self, before, after):
        channel_id = self.logging_config.get('role_update_channel')
        if channel_id:
            embed = Embed(
                title="Role Updated",
                description=f"**Role:** {before.name} ({before.id})\n**Color Changed To:** {after.color}",
                color=discord.Color.blue()
            )
            await self.send_log(channel_id, embed.title, embed.description, discord.Color.blue(), footer=f"Updated at {int(datetime.utcnow().timestamp())}")

    # Channel Create
    async def on_guild_channel_create(self, channel):
        channel_id = self.logging_config.get('channel_create_channel')
        if channel_id:
            embed = Embed(
                title="Channel Created",
                description=f"**Channel Name:** {channel.name}\n**Channel ID:** {channel.id}",
                color=discord.Color.blue()
            )
            await self.send_log(channel_id, embed.title, embed.description, discord.Color.blue(), footer=f"Created at {int(datetime.utcnow().timestamp())}")

    # Channel Delete
    async def on_guild_channel_delete(self, channel):
        channel_id = self.logging_config.get('channel_delete_channel')
        if channel_id:
            embed = Embed(
                title="Channel Deleted",
                description=f"**Channel Name:** {channel.name}\n**Channel ID:** {channel.id}",
                color=discord.Color.red()
            )
            await self.send_log(channel_id, embed.title, embed.description, discord.Color.red(), footer=f"Deleted at {int(datetime.utcnow().timestamp())}")

    # Emoji Create
    async def on_guild_emoji_create(self, emoji):
        channel_id = self.logging_config.get('emoji_create_channel')
        if channel_id:
            embed = Embed(
                title="Emoji Created",
                description=f"**Emoji Name:** {emoji.name}\n**Emoji ID:** {emoji.id}",
                color=discord.Color.blue()
            )
            await self.send_log(channel_id, embed.title, embed.description, discord.Color.blue(), footer=f"Created at {int(datetime.utcnow().timestamp())}")

    # Emoji Delete
    async def on_guild_emoji_delete(self, emoji):
        channel_id = self.logging_config.get('emoji_delete_channel')
        if channel_id:
            embed = Embed(
                title="Emoji Deleted",
                description=f"**Emoji Name:** {emoji.name}\n**Emoji ID:** {emoji.id}",
                color=discord.Color.red()
            )
            await self.send_log(channel_id, embed.title, embed.description, discord.Color.red(), footer=f"Deleted at {int(datetime.utcnow().timestamp())}")

    # Voice Channel Join/Leave
    async def on_voice_state_update(self, member, before, after):
        if before.channel != after.channel:
            if after.channel:
                channel_id = self.logging_config.get('voice_join_channel')
                if channel_id:
                    embed = Embed(
                        title="Voice Channel Join",
                        description=f"**User:** {member.mention} ({member})\n**Channel:** {after.channel.name}",
                        color=discord.Color.green()
                    )
                    await self.send_log(channel_id, embed.title, embed.description, discord.Color.green(), footer=f"Joined at {int(datetime.utcnow().timestamp())}")
            if before.channel:
                channel_id = self.logging_config.get('voice_leave_channel')
                if channel_id:
                    embed = Embed(
                        title="Voice Channel Leave",
                        description=f"**User:** {member.mention} ({member})\n**Channel:** {before.channel.name}",
                        color=discord.Color.red()
                    )
                    await self.send_log(channel_id, embed.title, embed.description, discord.Color.red(), footer=f"Left at {int(datetime.utcnow().timestamp())}")

    # Emoji Update (Only if the name or other properties change)
    async def on_guild_emoji_update(self, before, after):
        channel_id = self.logging_config.get('emoji_update_channel')
        if channel_id:
            embed = Embed(
                title="Emoji Updated",
                description=f"**Before:** {before.name} (ID: {before.id})\n**After:** {after.name} (ID: {after.id})",
                color=discord.Color.orange()
            )
            await self.send_log(channel_id, embed.title, embed.description, discord.Color.orange(), footer=f"Updated at {int(datetime.utcnow().timestamp())}")

    # Channel Update
    async def on_guild_channel_update(self, before, after):
        channel_id = self.logging_config.get('channel_update_channel')
        if channel_id:
            embed = Embed(
                title="Channel Updated",
                description=f"**Before:** {before.name} (ID: {before.id})\n**After:** {after.name} (ID: {after.id})",
                color=discord.Color.orange()
            )
            await self.send_log(channel_id, embed.title, embed.description, discord.Color.orange(), footer=f"Updated at {int(datetime.utcnow().timestamp())}")

async def setup(bot):
    await bot.add_cog(Logging(bot))

