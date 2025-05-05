import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
from azure.ai.contentsafety import ContentSafetyClient
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError
import datetime
from io import BytesIO
from azure.ai.contentsafety.models import (
    AnalyzeTextOptions,
    AnalyzeImageOptions,
    ImageData,
    TextCategory,
    ImageCategory
)


load_dotenv()
token = os.getenv("Discord_ModeratorBot_Token")


intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='>', intents=intents)
LOG_CHANNEL_ID = 1365969751515332640 


content_safety_client = ContentSafetyClient(
    endpoint=os.getenv("Azure_Content_Safety_Endpoint"),
    credential=AzureKeyCredential(os.getenv("Azure_Content_Safety_Key"))
)
async def log_violation(log_channel, user, severity, content, channel=None, attachment=None):
    """Logt violations naar een specifiek kanaal met bewijs."""
    embed = discord.Embed(
        title="🚨 Content Violation",
        description=(
            f"**User:** {user.mention}\n"
            f"**Severity:** {severity}\n"
            f"**Channel:** {channel.mention if channel else 'DM'}"
        ),
        color=discord.Color.red(),
        timestamp=datetime.datetime.now(datetime.timezone.utc)  
    )
    
    embed.add_field(name="Content", value=f"```{content[:1000]}```", inline=False)
    
    if attachment:
        try:
            
            file = discord.File(
                BytesIO(await attachment.read()),
                filename=attachment.filename
            )
            embed.set_image(url=f"attachment://{attachment.filename}")
            await log_channel.send(embed=embed, file=file)
            return
        except Exception as e:
            print(f"[ERROR] Failed to process image: {e}")
            embed.add_field(name="Image Error", value="Could not process image", inline=False)
    
    await log_channel.send(embed=embed)

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
            await message.channel.send(f"{message.author.mention} is verbannen wegens ernstig ongepaste inhoud.", delete_after=15)
        except discord.Forbidden:
            await message.channel.send("Geen ban permissies.", delete_after=15)
    
    elif max_severity >= 3:
        try:
            await message.author.kick(reason=f"Inappropriate {content_type} (severity {max_severity})")
            await message.channel.send(f"{message.author.mention} is gekicked wegens ongepaste inhoud.", delete_after=15)
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
                await message.channel.send("Kan Muted rol niet maken.", delete_after=15)
                return
        
        try:
            await message.author.add_roles(muted_role)
            await message.channel.send(f"{message.author.mention} is gemute voor ongepaste inhoud.", delete_after=15)
        except discord.Forbidden:
            await message.channel.send("Geen mute permissies.", delete_after=15)
    
    await message.delete()
    print(f"[ACTION] {content_type.capitalize()} verwijderd met severity {max_severity}")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    # Skip commands and DMs
    if message.content.startswith(bot.command_prefix) or not message.guild:
        return await bot.process_commands(message)
    
    # Skip logkanaal
    if message.channel.id == LOG_CHANNEL_ID:
        return await bot.process_commands(message)
    
    try:
        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        max_severity = 0

        
        if message.content:
            print(f"[DEBUG] Analyzing text: {message.content}")
            text_severity = await analyze_text(message.content)
            print(f"[DEBUG] Text severity: {text_severity}")
            max_severity = max(max_severity, text_severity)

        
        for attachment in message.attachments:
            if any(attachment.filename.lower().endswith(ext) for ext in ['.jpg', '.png', '.jpeg']):
                print(f"[DEBUG] Analyzing image: {attachment.filename}")
                image_bytes = await attachment.read()
                image_severity = await analyze_image(image_bytes)
                print(f"[DEBUG] Image severity: {image_severity}")
                max_severity = max(max_severity, image_severity)
                
                if max_severity >= 2:
                     await log_violation(log_channel, message.author, image_severity,
                    f"Image: {attachment.filename} ({attachment.url})", 
                    message.channel, attachment)

        
        if max_severity >= 2:
            if message.content and not message.attachments:
                await log_violation(log_channel, message.author, max_severity,
                   message.content, message.channel)
            await take_action(message, max_severity)

    except HttpResponseError as e:
        print(f"[AZURE ERROR] {e}")
    except Exception as e:
        print(f"[ERROR] {e}")
    
    await bot.process_commands(message)

@bot.event
async def on_ready():
    print(f"Moderatorbot is online als {bot.user}")

bot.run(token)