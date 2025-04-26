import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
from azure.ai.contentsafety import ContentSafetyClient
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError
from azure.ai.contentsafety.models import (
    AnalyzeTextOptions,
    AnalyzeImageOptions,
    ImageData,
    TextCategory,
    ImageCategory
)

# Load environment variables
load_dotenv()
token = os.getenv("Discord_ModeratorBot_Token")

# Initialize bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='>', intents=intents)

# Initialize Azure clients
content_safety_client = ContentSafetyClient(
    endpoint=os.getenv("Azure_Content_Safety_Endpoint"),
    credential=AzureKeyCredential(os.getenv("Azure_Content_Safety_Key"))
)

async def analyze_text(content):
    """Analyze text content using Azure Content Safety"""
    request = AnalyzeTextOptions(text=content)
    response = content_safety_client.analyze_text(request)
    return max(item.severity for item in response.categories_analysis)

async def analyze_image(image_bytes):
    """Analyze image content using Azure Content Safety"""
    request = AnalyzeImageOptions(image=ImageData(content=image_bytes))
    response = content_safety_client.analyze_image(request)
    return max(item.severity for item in response.categories_analysis)

async def take_action(message, max_severity, content_type="text"):
    """Take appropriate action based on severity"""
    if max_severity >= 4:
        try:
            await message.author.ban(reason=f"Inappropriate {content_type} (severity {max_severity})")
            await message.channel.send(f"{message.author.mention} is verbannen wegens ernstig ongepaste inhoud.")
        except discord.Forbidden:
            await message.channel.send("Geen ban permissies.")
    
    elif max_severity >= 3:
        try:
            await message.author.kick(reason=f"Inappropriate {content_type} (severity {max_severity})")
            await message.channel.send(f"{message.author.mention} is gekicked wegens ongepaste inhoud.")
        except discord.Forbidden:
            await message.channel.send("Geen kick permissies.")
    
    elif max_severity >= 2:
        muted_role = discord.utils.get(message.guild.roles, name="Muted")
        if not muted_role:
            try:
                muted_role = await message.guild.create_role(name="Muted")
                for channel in message.guild.channels:
                    await channel.set_permissions(muted_role, send_messages=False)
            except discord.Forbidden:
                await message.channel.send("Kan Muted rol niet maken.")
                return
        
        try:
            await message.author.add_roles(muted_role)
            await message.channel.send(f"{message.author.mention} is gemute voor ongepaste inhoud.")
        except discord.Forbidden:
            await message.channel.send("Geen mute permissies.")
    
    await message.delete()
    print(f"[ACTION] {content_type.capitalize()} verwijderd met severity {max_severity}")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    # Skip commands and DMs
    if message.content.startswith(bot.command_prefix) or not message.guild:
        return await bot.process_commands(message)
    
    try:
        # Text analysis
        if message.content:
            print(f"[DEBUG] Analyzing text: {message.content}")
            text_severity = await analyze_text(message.content)
            print(f"[DEBUG] Text severity: {text_severity}")
            
            if text_severity >= 2:
                await take_action(message, text_severity, "text")
                return
        
        # Image analysis
        for attachment in message.attachments:
            if any(attachment.filename.lower().endswith(ext) for ext in ['.jpg', '.png', '.jpeg']):
                print(f"[DEBUG] Analyzing image: {attachment.filename}")
                image_bytes = await attachment.read()
                image_severity = await analyze_image(image_bytes)
                print(f"[DEBUG] Image severity: {image_severity}")
                
                if image_severity >= 2:
                    await take_action(message, image_severity, "image")
                    return
    
    except HttpResponseError as e:
        print(f"[AZURE ERROR] {e}")
    except Exception as e:
        print(f"[ERROR] {e}")
    
    await bot.process_commands(message)

@bot.event
async def on_ready():
    print(f"Moderatorbot is online als {bot.user}")

bot.run(token)