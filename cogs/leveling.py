import discord
from discord.ext import commands
from discord import app_commands
import random
from utils.data_handler import DataHandler
from utils.config_manager import ConfigManager

class Leveling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data_handler = DataHandler('data/leveling.json')
        self.config_manager = ConfigManager('config.json')
        self.config = self.config_manager.load_config().get('leveling', {})

    def calculate_xp_needed(self, level):
        return 75 + 100 * (level - 1)

    def has_permission(self, interaction: discord.Interaction, command_name: str):
        command_cfg = self.config.get("commands", {}).get(command_name, {})
        if not command_cfg.get("enabled", True):
            return False
        # Check required roles
        required_roles = command_cfg.get("required_roles", [])
        if not any(role.name in required_roles or str(role.id) in required_roles for role in interaction.user.roles):
            return False
        # Check Discord permissions
        required_perms = command_cfg.get("permissions", [])
        if required_perms:
            author_perms = interaction.channel.permissions_for(interaction.user)
            for perm in required_perms:
                if not getattr(author_perms, perm, False):
                    return False
        return True

    async def update_user_level(self, user_id, guild_id, xp_to_add=0):
        data = self.data_handler.load_data()
        guild_id = str(guild_id)
        user_id = str(user_id)

        if guild_id not in data:
            data[guild_id] = {}
        if user_id not in data[guild_id]:
            data[guild_id][user_id] = {'xp': 0, 'level': 1}

        user_data = data[guild_id][user_id]
        user_data['xp'] += xp_to_add
        xp_needed = self.calculate_xp_needed(user_data['level'])
        level_up = False

        while user_data['xp'] >= xp_needed:
            user_data['level'] += 1
            user_data['xp'] -= xp_needed
            xp_needed = self.calculate_xp_needed(user_data['level'])
            level_up = True

        self.data_handler.save_data(data)
        return level_up, user_data['level']

    async def process_message_for_leveling(self, message):
        if message.author.bot or not self.config.get('enabled', True):
            return

        guild_id = str(message.guild.id)
        xp_gain_cfg = self.config.get("xp_gain", {})
        if not xp_gain_cfg.get("enabled", True):
            return

        min_xp = xp_gain_cfg.get("min_xp", 10)
        max_xp = xp_gain_cfg.get("max_xp", 20)
        xp_to_add = random.randint(min_xp, max_xp)

        level_up, new_level = await self.update_user_level(message.author.id, message.guild.id, xp_to_add)

        if level_up and self.config.get("level_up", {}).get("enabled", True):
            msg_template = self.config["level_up"].get("message", "{user} leveled up to {level}!")
            channel_id = self.config["level_up"].get("channel_id")
            channel = self.bot.get_channel(int(channel_id)) if channel_id else message.channel
            await channel.send(msg_template.format(user=message.author.mention, level=new_level))

            # Check for level-up roles
            level_roles = self.config.get("level_roles", {})
            if str(new_level) in level_roles:
                role_id = int(level_roles[str(new_level)])
                role = message.guild.get_role(role_id)
                if role:
                    await message.author.add_roles(role)

    @app_commands.command(name="level", description="Check the level and XP of a user.")
    async def level(self, interaction: discord.Interaction, member: discord.Member = None):
        if not self.has_permission(interaction, "level"):
            return await interaction.response.send_message("You do not have permission to use this command.")
        
        member = member or interaction.user
        data = self.data_handler.load_data()
        user_data = data.get(str(interaction.guild.id), {}).get(str(member.id))

        if not user_data:
            return await interaction.response.send_message(f"{member.display_name} hasn't earned any XP yet!")

        level = user_data['level']
        xp = user_data['xp']
        xp_needed = self.calculate_xp_needed(level)
        progress = (xp / xp_needed) * 100

        embed = discord.Embed(title=f"{member.display_name}'s Level Stats", color=discord.Color.green())
        embed.add_field(name="Level", value=level)
        embed.add_field(name="XP", value=f"{xp}/{xp_needed}")
        embed.add_field(name="Progress", value=f"{progress:.1f}%")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leaderboard", description="Check the server's leaderboard.")
    async def leaderboard(self, interaction: discord.Interaction):
        if not self.has_permission(interaction, "level"):
            return await interaction.response.send_message("You do not have permission to use this command.")
        
        data = self.data_handler.load_data()
        guild_id = str(interaction.guild.id)
        if guild_id not in data:
            return await interaction.response.send_message("No data found for this server.")

        sorted_members = sorted(
            data[guild_id].items(),
            key=lambda x: (x[1]['level'], x[1]['xp']),
            reverse=True
        )

        embed = discord.Embed(title="🏆 Server Leaderboard", color=discord.Color.gold())
        description = ""
        for i, (user_id, stats) in enumerate(sorted_members[:10], start=1):
            member = interaction.guild.get_member(int(user_id))
            name = member.display_name if member else f"<@{user_id}>"
            description += f"**#{i}** — {name} → Level {stats['level']} ({stats['xp']} XP)\n"
        embed.description = description or "No users yet!"
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="setlevel", description="Set the level of a user.")
    async def setlevel(self, interaction: discord.Interaction, member: discord.Member, level: int):
        if not self.has_permission(interaction, "setlevel"):
            return await interaction.response.send_message("You do not have permission to use this command.")
        if level < 1:
            return await interaction.response.send_message("Level must be at least 1.")
        
        data = self.data_handler.load_data()
        guild_id = str(interaction.guild.id)
        user_id = str(member.id)
        if guild_id not in data:
            data[guild_id] = {}
        data[guild_id][user_id] = {'xp': 0, 'level': level}
        self.data_handler.save_data(data)
        await interaction.response.send_message(f"Set {member.mention}'s level to {level}.")

    @app_commands.command(name="addxp", description="Add XP to a user.")
    async def addxp(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        if not self.has_permission(interaction, "addxp"):
            return await interaction.response.send_message("You do not have permission to use this command.")
        
        level_up, _ = await self.update_user_level(member.id, interaction.guild.id, amount)
        await interaction.response.send_message(f"Gave {amount} XP to {member.mention}.")

    @app_commands.command(name="removexp", description="Remove XP from a user.")
    async def removexp(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        if not self.has_permission(interaction, "removexp"):
            return await interaction.response.send_message("You do not have permission to use this command.")
        
        await self.update_user_level(member.id, interaction.guild.id, -amount)
        await interaction.response.send_message(f"Removed {amount} XP from {member.mention}.")

    @app_commands.command(name="grantlevel", description="Grant levels to a user.")
    async def grantlevel(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        if not self.has_permission(interaction, "grantlevel"):
            return await interaction.response.send_message("You do not have permission to use this command.")
        
        data = self.data_handler.load_data()
        guild_id = str(interaction.guild.id)
        user_id = str(member.id)
        if guild_id not in data:
            data[guild_id] = {}
        if user_id not in data[guild_id]:
            data[guild_id][user_id] = {'xp': 0, 'level': 1}
        data[guild_id][user_id]['level'] += amount
        self.data_handler.save_data(data)
        await interaction.response.send_message(f"Granted {amount} levels to {member.mention}.")

    @app_commands.command(name="revokelevel", description="Revoke levels from a user.")
    async def revokelevel(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        if not self.has_permission(interaction, "revokelevel"):
            return await interaction.response.send_message("You do not have permission to use this command.")
        
        data = self.data_handler.load_data()
        guild_id = str(interaction.guild.id)
        user_id = str(member.id)
        if guild_id not in data or user_id not in data[guild_id]:
            return await interaction.response.send_message("User data not found.")
        
        data[guild_id][user_id]['level'] = max(1, data[guild_id][user_id]['level'] - amount)
        self.data_handler.save_data(data)
        await interaction.response.send_message(f"Revoked {amount} levels from {member.mention}.")

async def setup(bot):
    await bot.add_cog(Leveling(bot))
