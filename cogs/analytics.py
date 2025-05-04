import asyncio
import discord
from discord.ext import commands
from discord import app_commands
import json
import datetime
from utils.data_handler import DataHandler
from utils.config_manager import ConfigManager

class Analytics(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data_handler = DataHandler('data/analytics.json')
        self.config_manager = ConfigManager('config.json')
        self.config = self.config_manager.load_config().get('analytics', {})

        # Initialize command configurations
        self.command_configs = {
            'activity': {
                'enabled': True,
                'required_roles': ['@everyone'],
                'permissions': []
            },
            'xpstats': {
                'enabled': True,
                'required_roles': ['@everyone'],
                'permissions': []
            }
        }
        self.update_configs()

    def update_configs(self):
        if 'commands' in self.config:
            for cmd, cfg in self.config['commands'].items():
                if cmd in self.command_configs:
                    self.command_configs[cmd].update(cfg)

    async def check_command_permissions(self, interaction: discord.Interaction, command_name):
        if command_name not in self.command_configs:
            return False

        cmd_cfg = self.command_configs[command_name]

        if not cmd_cfg.get('enabled', True):
            return False

        if 'permissions' in cmd_cfg:
            for perm in cmd_cfg['permissions']:
                if not getattr(interaction.user.guild_permissions, perm, False):
                    return False

        required_roles = cmd_cfg.get('required_roles', [])
        if required_roles and '@everyone' not in required_roles:
            user_roles = [str(role.id) for role in interaction.user.roles]
            if not any(role_id in user_roles for role_id in required_roles):
                return False

        return True

    async def process_message_for_analytics(self, message):
        print(f"Received message from {message.author}: {message.content}")
        try:
            if message.author.bot or not self.config.get('enabled', True):
                return

            guild_id = str(message.guild.id)
            user_id = str(message.author.id)

            data = self.data_handler.load_data()

            # Initialize guild data if not exists
            if guild_id not in data:
                data[guild_id] = {
                    'server_hours': {},
                    'users': {}
                }

            # Initialize 'users' data if it doesn't exist
            if 'users' not in data[guild_id]:
                data[guild_id]['users'] = {}

            # Initialize user data if not exists
            if user_id not in data[guild_id]['users']:
                data[guild_id]['users'][user_id] = {
                    'message_count': 0,
                    'last_active': None,
                    'status_changes': [],
                    'xp_changes': [],
                    'online_time': 0,
                    'activity': {
                        'channels': {},
                        'active_hours': {}
                    },
                    'games': {}
                }

            user_data = data[guild_id]['users'][user_id]
            user_data['message_count'] += 1
            user_data['last_active'] = datetime.datetime.now().isoformat()

            # Track channel activity
            channel_id = str(message.channel.id)
            user_data['activity']['channels'][channel_id] = user_data['activity']['channels'].get(channel_id, 0) + 1

            # Track server-wide hour activity
            current_hour = str(datetime.datetime.now().hour)
            data[guild_id]['server_hours'][current_hour] = data[guild_id]['server_hours'].get(current_hour, 0) + 1
        
            # Track user hour activity
            user_data['activity']['active_hours'][current_hour] = user_data['activity']['active_hours'].get(current_hour, 0) + 1

            self.data_handler.save_data(data)
            print(f"Data for {message.author} saved.")
        except Exception as e:
            print(f"Error in on_message: {e}")

    async def process_status_change(self, before, after):
        if not self.config.get('enabled', True) or before.guild is None:
            return

        guild_id = str(before.guild.id)
        user_id = str(before.id)

        data = self.data_handler.load_data()

        # Check if user data exists
        if guild_id not in data or user_id not in data[guild_id].get('users', {}):
            return

        user_data = data[guild_id]['users'][user_id]

        # Track status changes
        if before.status != after.status:
            user_data['status_changes'].append({
                'timestamp': datetime.datetime.now().isoformat(),
                'from': str(before.status),
                'to': str(after.status)
            })

        # Track online time
        if after.status == discord.Status.online:
            if 'last_online' not in user_data:
                user_data['last_online'] = datetime.datetime.now().isoformat()
        elif 'last_online' in user_data:
            last_online = datetime.datetime.fromisoformat(user_data['last_online'])
            time_online = (datetime.datetime.now() - last_online).total_seconds()
            user_data['online_time'] = user_data.get('online_time', 0) + time_online
            del user_data['last_online']

        # Track games played
        if after.activity and hasattr(after.activity, 'name'):
            game = after.activity.name
            user_data['games'][game] = user_data['games'].get(game, 0) + 1

        self.data_handler.save_data(data)

    @app_commands.command(name="activity", description="Show user activity analytics")
    async def activity(self, interaction: discord.Interaction, member: discord.Member = None):
        """Show detailed activity statistics for a user"""
        if not await self.check_command_permissions(interaction, 'activity'):
            return await interaction.response.send_message(
                "You don't have permission to use this command!",
                ephemeral=True
            )

        member = member or interaction.user
        data = self.data_handler.load_data()
        guild_id = str(interaction.guild.id)
        user_id = str(member.id)

        # Check if data exists for this user
        if guild_id not in data or user_id not in data[guild_id].get('users', {}):
            return await interaction.response.send_message(
                f"No activity data available for {member.display_name}!",
                ephemeral=True
            )

        user_data = data[guild_id]['users'][user_id]
    
        embed = discord.Embed(
            title=f"{member.display_name}'s Activity Overview",
            color=discord.Color.blurple(),
            timestamp=datetime.datetime.now()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
    
        # Basic activity stats
        embed.add_field(name="Messages Sent", value=user_data.get("message_count", 0), inline=True)
        
        if "last_active" in user_data:
            last_active = datetime.datetime.fromisoformat(user_data["last_active"])
            embed.add_field(name="Last Active", value=f"<t:{int(last_active.timestamp())}:R>", inline=True)
        
        # Online Time
        hours = user_data.get("online_time", 0) / 3600
        embed.add_field(name="Online Time", value=f"{hours:.1f} hours", inline=True)
        
        # Most Active Hour
        if "active_hours" in user_data.get("activity", {}):
            active_hours = user_data["activity"]["active_hours"]
            if active_hours:
                top_hour = max(active_hours.items(), key=lambda x: x[1])[0]
                embed.add_field(name="Most Active Hour", value=f"{int(top_hour)}:00", inline=True)
        
        # Top Channels
        if "channels" in user_data.get("activity", {}):
            channels = user_data["activity"]["channels"]
            if channels:
                top_channels = sorted(channels.items(), key=lambda x: x[1], reverse=True)[:3]
                channel_summary = "\n".join(f"<#{cid}>: {count} msgs" for cid, count in top_channels)
                embed.add_field(name="Top Channels", value=channel_summary, inline=False)
        
        # Most Played Games
        if "games" in user_data and user_data["games"]:
            top_games = sorted(user_data["games"].items(), key=lambda x: x[1], reverse=True)[:3]
            games_summary = "\n".join(f":video_game: {name}: {count} times" for name, count in top_games)
            embed.add_field(name="Top Games", value=games_summary, inline=False)
        
        # Server-wide stats
        if "server_hours" in data[guild_id] and data[guild_id]["server_hours"]:
            busiest_hour = max(data[guild_id]["server_hours"].items(), key=lambda x: x[1])[0]
            embed.add_field(name="Busiest Server Hour", value=f"{int(busiest_hour)}:00", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Analytics(bot))