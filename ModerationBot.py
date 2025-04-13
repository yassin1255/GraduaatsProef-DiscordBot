import discord
from discord import File 
from discord.ext import commands
import os
from dotenv import load_dotenv

load_dotenv()
token = os.getenv("Discord_ModeratorBot_Token")

client = discord.Client(intents=discord.Intents.all())
client = commands.Bot(command_prefix='>', intents=discord.Intents.all())
block_words = ["badword1", "badword2", "badword3"] 

@client.event
async def on_ready():
    print("Moderatorbot is online")

@client.event
async def on_message(message):
    if message.author == client.user:
        return
    
    # Check for moderator role
    is_moderator = any(role.name == "Moderator" for role in message.author.roles)
    
    if not is_moderator:
        message_content = message.content.lower()
        
        # Check for blocked words
        if any(word in message_content for word in block_words):
            await message.delete()
            await message.channel.send(f"Bericht van {message.author.mention} is verwijderd omdat het ongepast was.")
            return
        
        # Check for URLs (simple version)
        if "http://" in message_content or "https://" in message_content:
            await message.delete()
            await message.channel.send(f"Bericht van {message.author.mention} is verwijderd omdat het links bevatte.")
            return
    
    print("Bericht niet verwijderd")
    
"""
client.command(name='ban')
@commands.has_role("Moderator")
async def ban_user(ctx, member: discord.member, *, reason="Geen reden opgegeven"):
"""
client.run(token)




    