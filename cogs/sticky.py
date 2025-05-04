import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord.ui import Button, View
from utils.data_handler import DataHandler
from utils.config_manager import ConfigManager

class Sticky(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data_handler = DataHandler('data/sticky.json')
        self.config_manager = ConfigManager('config.json')
        self.config = self.config_manager.load_config().get('sticky', {})
        self.sticky_messages = {}

        # Initialize command configurations
        self.command_configs = {
            'stick': {
                'enabled': True,
                'required_roles': ['@everyone'],
                'permissions': ['manage_messages']
            },
            'unstick': {
                'enabled': True,
                'required_roles': ['@everyone'],
                'permissions': ['manage_messages']
            }
        }
        self.update_configs()
        self.sticky_ready_task.start()

    def update_configs(self):
        """Update command configurations from the config file"""
        for cmd, cfg in self.config.get('commands', {}).items():
            if cmd in self.command_configs:
                self.command_configs[cmd].update(cfg)

    async def check_command_permissions(self, interaction, command_name):
        """Check if user has permissions to use the command"""
        cmd_cfg = self.command_configs.get(command_name, {})
        if not cmd_cfg.get('enabled', True):
            return False
        # Discord permissions
        for perm in cmd_cfg.get('permissions', []):
            if not getattr(interaction.user.guild_permissions, perm, False):
                return False
        # Role requirements
        req = cmd_cfg.get('required_roles', [])
        if req and '@everyone' not in req:
            user_roles = [str(r.id) for r in interaction.user.roles]
            if not any(rid in user_roles for rid in req):
                return False
        return True

    @tasks.loop(count=1)
    async def sticky_ready_task(self):
        await self.bot.wait_until_ready()
        print("[Sticky] Bot is ready, restoring stickies...")
        await self.sticky_on_ready()

    async def sticky_on_ready(self):
        """Restore sticky messages from file when the bot restarts."""
        data = self.data_handler.load_data()
        print('working')

        for channel_id, sticky_data in data.items():
            channel = self.bot.get_channel(int(channel_id))
            if not channel:
                continue
            try:
                # Try fetching the sticky message by ID
                msg = await channel.fetch_message(sticky_data['message_id'])
                self.sticky_messages[channel_id] = msg
            except discord.NotFound:
                # If message doesn't exist, try sending a new one
                new_msg = await channel.send(sticky_data['content'])
                sticky_data['message_id'] = new_msg.id
                self.sticky_messages[channel_id] = new_msg
                self.data_handler.save_data(data)  # Save the new message ID

            # If the bot couldn't find the message, try getting the last 20 messages
            if channel_id not in self.sticky_messages:
                async for message in channel.history(limit=20):
                    if message.content == sticky_data['content']:
                        self.sticky_messages[channel_id] = message
                        break

            # If sticky message still not found, send a new one
            if channel_id not in self.sticky_messages:
                new_msg = await channel.send(sticky_data['content'])
                sticky_data['message_id'] = new_msg.id
                self.sticky_messages[channel_id] = new_msg
                self.data_handler.save_data(data)  # Save the new message ID

    @app_commands.command(name="stick", description="Stick a message to the channel")
    async def stick(self, interaction: discord.Interaction, message: str):
        """Stick a message to the channel using slash command"""
        if not await self.check_command_permissions(interaction, 'stick'):
            return await interaction.response.send_message("❌ You don't have permission to use this command!", ephemeral=True)

        data = self.data_handler.load_data()
        channel_id = str(interaction.channel.id)

        # Send and record the sticky message
        sticky_msg = await interaction.channel.send(message)
        data[channel_id] = {
            'message_id': sticky_msg.id,
            'content': message
        }
        self.data_handler.save_data(data)
        self.sticky_messages[channel_id] = sticky_msg

        await interaction.response.send_message("📌 Message stuck to channel!", ephemeral=True)
        await interaction.delete_original_response()

    @app_commands.command(name="unstick", description="Remove the sticky message from this channel")
    async def unstick(self, interaction: discord.Interaction):
        """Remove the sticky message using slash command"""
        if not await self.check_command_permissions(interaction, 'unstick'):
            return await interaction.response.send_message("❌ You don't have permission to use this command!", ephemeral=True)

        data = self.data_handler.load_data()
        channel_id = str(interaction.channel.id)

        if channel_id not in data:
            return await interaction.response.send_message("ℹ️ There is no sticky message in this channel.", ephemeral=True)

        # Delete the message if it still exists
        msg_id = data[channel_id]['message_id']
        try:
            msg = await interaction.channel.fetch_message(msg_id)
            await msg.delete()
        except discord.NotFound:
            pass

        # Remove from storage and cache
        del data[channel_id]
        self.data_handler.save_data(data)
        self.sticky_messages.pop(channel_id, None)

        await interaction.response.send_message("🗑️ Sticky message removed.", ephemeral=True)

    async def update_sticky_message(self, channel):
        """Internal: re-post the sticky message at the bottom"""
        data = self.data_handler.load_data()
        channel_id = str(channel.id)
        if channel_id not in data:
            return

        sticky_data = data[channel_id]

        # Delete old sticky message
        try:
            old = await channel.fetch_message(sticky_data['message_id'])
            await old.delete()
        except discord.NotFound:
            pass

        # Re-post sticky message
        new_msg = await channel.send(sticky_data['content'])
        data[channel_id]['message_id'] = new_msg.id
        self.data_handler.save_data(data)
        self.sticky_messages[channel_id] = new_msg

    async def on_message(self, message):
        """When anyone posts, re-stick the sticky message at the bottom."""
        if message.author.bot or not isinstance(message.channel, discord.TextChannel):
            return

        cid = str(message.channel.id)
        if cid in self.sticky_messages and message.id != self.sticky_messages[cid].id:
            await self.update_sticky_message(message.channel)

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return
        if isinstance(error, commands.MissingPermissions):
            return await ctx.send("❌ You don't have permission to use this command!", ephemeral=True)
        await ctx.send(f"⚠️ Error: {error}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Sticky(bot))
