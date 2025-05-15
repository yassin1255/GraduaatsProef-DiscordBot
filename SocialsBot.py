import discord
from discord.ext import commands

bot = commands.Bot(command_prefix='!')

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

@bot.command()
async def post(ctx, *, message):
 
    await ctx.send(f'Bericht ontvangen: "{message}". Dit wordt nu gepost op sociale media.')

bot.run('')