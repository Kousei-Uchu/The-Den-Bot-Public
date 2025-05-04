import discord
from discord.ext import commands
import json
import os
from dotenv import load_dotenv
from utils.config_manager import ConfigManager

load_dotenv()

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='/', intents=intents, help_command=None)

config_manager = ConfigManager('config.json')
config = config_manager.load_config()

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    await load_cogs()
    await bot.tree.sync()

async def load_cogs():
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            try:
                await bot.load_extension(f'cogs.{filename[:-3]}')
                print(f'Loaded cog: {filename}')
            except Exception as e:
                print(f'Failed to load cog {filename}: {e}')

@bot.command()
@commands.has_permissions(administrator=True)
async def reload(ctx, cog_name: str):
    try:
        await bot.reload_extension(f'cogs.{cog_name}')
        await ctx.send(f'Reloaded {cog_name} successfully!')
    except Exception as e:
        await ctx.send(f'Failed to reload {cog_name}: {e}')

bot.run(os.getenv('DISCORD_TOKEN'))
