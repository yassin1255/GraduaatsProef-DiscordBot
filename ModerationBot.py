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
    
    # Skip commands and DMs
    if message.content.startswith(bot.command_prefix) or not message.guild:
        return await bot.process_commands(message)
    
    try:
        print(f"[DEBUG] Analyzing: {message.content}")  # Debug log
        
        request = AnalyzeTextOptions(text=message.content)
        response = content_safety_client.analyze_text(request)
        
        # Debug log van de analyse
        print(f"[DEBUG] Analysis results: {[f'{cat.category}:{cat.severity}' for cat in response.categories_analysis]}")
        
        max_severity = max(item.severity for item in response.categories_analysis)
        print(f"[DEBUG] Max severity: {max_severity}")  # Debug log

        # Alleen actie ondernemen bij ernstige gevallen
        if max_severity >= 1:  # Verhoogde drempel
            print(f"[ACTION] Taking action for severity {max_severity}")
            
            if max_severity >= 4:  # Zeer ernstig
                try:
                    await message.author.ban(reason=f"Inappropriate content (severity {max_severity})")
                    await message.channel.send(f"{message.author.mention} is verbannen wegens ernstig ongepaste inhoud.")
                except discord.Forbidden:
                    print("[ERROR] Geen ban permissies")
                    await message.channel.send("Ik heb geen permissies om te bannen.")
                
            elif max_severity >= 3:  # Ernstig
                try:
                    await message.author.kick(reason=f"Inappropriate content (severity {max_severity})")
                    await message.channel.send(f"{message.author.mention} is gekicked wegens ongepaste inhoud.")
                except discord.Forbidden:
                    print("[ERROR] Geen kick permissies")
                    await message.channel.send("Ik heb geen permissies om te kicken.")
                
            elif max_severity >= 2:  # Matig ernstig
                muted_role = discord.utils.get(message.guild.roles, name="Muted")
                if not muted_role:
                    try:
                        muted_role = await message.guild.create_role(name="Muted")
                        for channel in message.guild.channels:
                            await channel.set_permissions(muted_role, send_messages=False)
                    except discord.Forbidden:
                        print("[ERROR] Kan Muted rol niet maken")
                        return
                
                try:
                    await message.author.add_roles(muted_role)
                    await message.channel.send(f"{message.author.mention} is gemute voor ongepaste inhoud.")
                except discord.Forbidden:
                    print("[ERROR] Geen mute permissies")
                    await message.channel.send("Ik heb geen permissies om te muten.")
            
            await message.delete()
            print(f"[ACTION] Bericht verwijderd met severity {max_severity}")
        else:
            print("[DEBUG] Bericht is acceptabel, geen actie ondernomen")
            
    except HttpResponseError as e:
        print(f"[ERROR] Azure error: {e}")
    except Exception as e:
        print(f"[ERROR] Onverwachte fout: {e}")
    
    await bot.process_commands(message)       

   

bot.run(token)




    