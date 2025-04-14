import discord
from discord import File 
from discord.ext import commands
import os
from dotenv import load_dotenv
from azure.ai.contentsafety import ContentSafetyClient
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError
from azure.ai.contentsafety.models import AnalyzeTextOptions

load_dotenv()
token = os.getenv("Discord_ModeratorBot_Token")


intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='>', intents=discord.Intents.all())

content_safety_client = ContentSafetyClient(
    endpoint=os.getenv("Azure_Content_Safety_Endpoint"),
    credential=AzureKeyCredential(os.getenv("Azure_Content_Safety_Key"))
)

@bot.event
async def on_ready():
    print("bot is online")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    try:
        request = AnalyzeTextOptions(text=message.content)
        response = content_safety_client.analyze_text(request)
        if any([
            response.hate.severity > 0 or 
            response.self_harm.severity > 0 or
            response.sexual.severity > 0 or
            response.violence.severity > 0
        ]):
         await message.delete()

        warning_message = (
            f"{message.author.mention}, je bericht is verwijderd omdat het "
                f"ongepaste inhoud bevat. "
                f"Severity niveaus - "
                f"Haat: {response.hate_result.severity}, "
                f"Zelfbeschadiging: {response.self_harm_result.severity}, "
                f"Seksueel: {response.sexual_result.severity}, "
                f"Geweld: {response.violence_result.severity}"
        )
        await message.channel.send(warning_message, delete_after=10)
    except HttpResponseError as e:
        print(f"Error analyzing message: {e}")
    
    
    #await bot.process_commands(message)                    

   

bot.run(token)




    