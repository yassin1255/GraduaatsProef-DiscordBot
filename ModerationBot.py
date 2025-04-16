import discord
from discord import File 
from discord.ext import commands
import os
from dotenv import load_dotenv
from azure.ai.contentsafety import ContentSafetyClient
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError
from azure.ai.contentsafety.models import AnalyzeTextOptions, TextCategory

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
    print("moderatorbot is online")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    try:
        request = AnalyzeTextOptions(text=message.content)
        response = content_safety_client.analyze_text(request)
        
        # Get results for each category
        hate_result = next((item for item in response.categories_analysis 
                          if item.category == TextCategory.HATE), None)
        self_harm_result = next((item for item in response.categories_analysis 
                               if item.category == TextCategory.SELF_HARM), None)
        sexual_result = next((item for item in response.categories_analysis 
                            if item.category == TextCategory.SEXUAL), None)
        violence_result = next((item for item in response.categories_analysis 
                              if item.category == TextCategory.VIOLENCE), None)

        # Check if any category has severity > 0
        if any(result.severity > 0 for result in [hate_result, self_harm_result, 
                                                sexual_result, violence_result] if result):
            
            await message.delete()
            
            warning_msg = (
                f"{message.author.mention}, je bericht is verwijderd wegens ongepaste inhoud.\n"
                f"Severiteit niveaus:\n"
                f"Haat: {hate_result.severity if hate_result else 0}\n"
                f"Zelfbeschadiging: {self_harm_result.severity if self_harm_result else 0}\n"
                f"Seksuele content: {sexual_result.severity if sexual_result else 0}\n"
                f"Geweld: {violence_result.severity if violence_result else 0}"
            )
            await message.channel.send(warning_msg, delete_after=10)
            
    except HttpResponseError as e:
        print(f"Error analyzing message: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
    
    
    #await bot.process_commands(message)                    

   

bot.run(token)




    