import discord
from discord import File 
from discord.ext import commands
import os
from dotenv import load_dotenv

load_dotenv()
token = os.getenv("Discord_ModeratorBot_Token")

client = discord.Client(intents=discord.Intents.all())
block_words = ["badword1", "badword2", "badword3","http://, https://"] 

@client.event
async def on_ready():
    print("Moderatorbot is online")

@client.event
async def on_message(message):

  if message.author != client.user:
    for word in block_words:
      if "Moderator" not in str(message.author.roles) and word in str(message.content.tolower()):
       await message.delete()
       await message.channel.send(f"Bericht van {message.author.mention} is verwijderd omdat het ongepast was.")
       return
    print("Bericht niet verwijderd")        
client.run(token)




    