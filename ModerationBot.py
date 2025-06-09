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
bot = commands.Bot(command_prefix='!', intents=intents)

GUILD_ID = int(os.getenv("GUILD_ID", 0))  
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_BOT", 0))
LOG_CHANNEL_MODERATOR_ID = int(os.getenv("LOG_CHANNEL_MODERATOR", 0))


if GUILD_ID == 0:
    raise ValueError("GUILD_ID is niet gevonden in .env file of is ongeldig")
if LOG_CHANNEL_ID == 0:
    raise ValueError("LOG_CHANNEL_BOT is niet gevonden in .env file of is ongeldig")

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

@bot.tree.command(name="mute", description="Mute een gebruiker")
@commands.has_permissions(manage_roles=True)
async def mute(interaction: discord.Interaction, gebruiker: discord.Member, reden: str = "Geen reden opgegeven"):
    """Mute een gebruiker"""
    # Controleer of de bot de gebruiker kan muten
    if gebruiker.top_role >= interaction.guild.me.top_role:
        await interaction.response.send_message("Ik kan deze gebruiker niet muten omdat ze een hogere/equal rol hebben.", ephemeral=True)
        return
    
    # Zoek of maak een muted rol
    muted_role = discord.utils.get(interaction.guild.roles, name="Muted")
    if not muted_role:
        try:
            muted_role = await interaction.guild.create_role(name="Muted")
            
            # Pas permissies aan voor alle kanalen
            for channel in interaction.guild.channels:
                await channel.set_permissions(muted_role, send_messages=False, speak=False)
        except discord.Forbidden:
            await interaction.response.send_message("Ik heb geen permissies om een Muted rol te maken.", ephemeral=True)
            return
    
    # Mute de gebruiker
    try:
        await gebruiker.add_roles(muted_role, reason=f"Gemute door {interaction.user}: {reden}")
    except discord.Forbidden:
        await interaction.response.send_message("Ik heb geen permissies om deze gebruiker te muten.", ephemeral=True)
        return
    
    # Stuur een DM naar de gemute gebruiker
    try:
        embed = discord.Embed(
            title=f"Je bent gemute in {interaction.guild.name}",
            description="Je kunt niet meer praten in tekst- en spraakkanalen.",
            color=discord.Color.orange()
        )
        embed.add_field(name="Reden", value=reden, inline=False)
        embed.add_field(name="Unmute aanvragen", value="Neem contact op met @yassin1255 om een unmute aan te vragen.", inline=False)
        embed.set_footer(text=f"Gemute door {interaction.user}")
        
        await gebruiker.send(embed=embed)
    except discord.Forbidden:
        pass  # Kan geen DM sturen, maar mute gaat wel door
    
    # Bevestiging naar de moderator
    embed = discord.Embed(
        title="Gebruiker gemute",
        description=f"{gebruiker.mention} is gemute.",
        color=discord.Color.green()
    )
    embed.add_field(name="Reden", value=reden, inline=False)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)
    
    # Log naar het logkanaal
    log_channel = bot.get_channel(LOG_CHANNEL_MODERATOR_ID)
    if log_channel:
        log_embed = discord.Embed(
            title="Mute Log",
            description=f"{gebruiker.mention} is gemute door {interaction.user.mention}",
            color=discord.Color.orange(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        log_embed.add_field(name="Reden", value=reden, inline=False)
        await log_channel.send(embed=log_embed)


@bot.tree.command(name="unmute", description="Unmute een gebruiker")
@commands.has_permissions(manage_roles=True)
async def unmute(interaction: discord.Interaction, gebruiker: discord.Member, reden: str = "Geen reden opgegeven"):
    """Handmatig een gebruiker unmuten"""
    muted_role = discord.utils.get(interaction.guild.roles, name="Muted")
    
    if not muted_role or muted_role not in gebruiker.roles:
        await interaction.response.send_message(f"{gebruiker.mention} is niet gemute.", ephemeral=True)
        return
    
    try:
        await gebruiker.remove_roles(muted_role, reason=f"Geunmute door {interaction.user}: {reden}")
        
        # Stuur een DM naar de geunmute gebruiker
        try:
            embed = discord.Embed(
                title=f"Je bent geunmute in {interaction.guild.name}",
                description="Je kunt weer praten in tekst- en spraakkanalen.",
                color=discord.Color.green()
            )
            embed.add_field(name="Bericht", value="Pas op voor volgende overtredingen!", inline=False)
            embed.set_footer(text=f"Geunmute door {interaction.user}")
            
            await gebruiker.send(embed=embed)
        except discord.Forbidden:
            pass  
        
        await interaction.response.send_message(f"{gebruiker.mention} is geunmute.", ephemeral=True )
        
        
        log_channel = bot.get_channel(LOG_CHANNEL_MODERATOR_ID)
        if log_channel:
            embed = discord.Embed(
                title="Unmute Log",
                description=f"{gebruiker.mention} is geunmute door {interaction.user.mention}",
                color=discord.Color.green(),
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            embed.add_field(name="Reden", value=reden, inline=False)
            await log_channel.send(embed=embed)
            
    except discord.Forbidden:
        await interaction.response.send_message("Ik heb geen permissies om deze gebruiker te unmuten.", ephemeral=True)

@bot.tree.command(name="kick", description="Kick een gebruiker van de server")
@commands.has_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, gebruiker: discord.Member, reden: str = "Geen reden opgegeven"):
    """Kick een gebruiker en stuur een DM met details"""
    
    # Controleer of de bot de gebruiker kan kicken
    if gebruiker.top_role >= interaction.guild.me.top_role:
        await interaction.response.send_message(
            "Ik kan deze gebruiker niet kicken omdat ze een hogere/equal rol hebben.",
            ephemeral=True
        )
        return
    
    try:
        # Stuur eerst een DM naar de gebruiker
        try:
            invite = await interaction.channel.create_invite(max_uses=1, unique=True)
            embed = discord.Embed(
                title=f"Je bent gekicked van {interaction.guild.name}",
                color=discord.Color.orange()
            )
            embed.add_field(name="Reden", value=reden, inline=False)
            embed.add_field(
                name="Je kunt weer joinen", 
                value=f"Gebruik deze invite link: {invite.url}\n"
                     f"Let op: deze link kan maar 1 keer gebruikt worden!",
                inline=False
            )
            embed.set_footer(text=f"Gekicked door {interaction.user}")
            
            await gebruiker.send(embed=embed)
        except discord.Forbidden:
            pass  # Kan geen DM sturen, maar kick gaat wel door
        
        # Voer de kick uit
        await gebruiker.kick(reason=f"Gekicked door {interaction.user}: {reden}")
        
        # Bevestiging naar de moderator (ephemeral)
        confirm_embed = discord.Embed(
            title="Gebruiker gekicked",
            description=f"{gebruiker.display_name} is gekicked van de server.",
            color=discord.Color.green()
        )
        confirm_embed.add_field(name="Reden", value=reden, inline=False)
        await interaction.response.send_message(embed=confirm_embed, ephemeral=True)
        
        # Log naar het logkanaal
        log_channel = bot.get_channel(LOG_CHANNEL_MODERATOR_ID)
        if log_channel:
            log_embed = discord.Embed(
                title="Kick Log",
                description=f"{gebruiker.mention} is gekicked door {interaction.user.mention}",
                color=discord.Color.orange(),
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            log_embed.add_field(name="Reden", value=reden, inline=False)
            await log_channel.send(embed=log_embed)
            
    except discord.Forbidden:
        await interaction.response.send_message(
            "Ik heb geen permissies om deze gebruiker te kicken.",
            ephemeral=True
        )


@bot.tree.command(name="ban", description="Ban een gebruiker van de server")
@commands.has_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, gebruiker: discord.Member, reden: str = "Geen reden opgegeven"):
    """Ban een gebruiker en stuur een DM met details"""
    
    # Controleer of de bot de gebruiker kan bannen
    if gebruiker.top_role >= interaction.guild.me.top_role:
        await interaction.response.send_message(
            "Ik kan deze gebruiker niet bannen omdat ze een hogere/equal rol hebben.",
            ephemeral=True
        )
        return
    
    try:
        # Stuur eerst een DM naar de gebruiker
        try:
            embed = discord.Embed(
                title=f"Je bent verbannen van {interaction.guild.name}",
                color=discord.Color.red()
            )
            embed.add_field(name="Reden", value=reden, inline=False)
            embed.add_field(
                name="Unban aanvragen", 
                value="Neem contact op met een moderator en vermeld @yassin1255 om een unban aan te vragen.",
                inline=False
            )
            embed.set_footer(text=f"Verbannen door {interaction.user}")
            
            await gebruiker.send(embed=embed)
        except discord.Forbidden:
            pass  # Kan geen DM sturen, maar ban gaat wel door
        
        # Voer de ban uit
        await gebruiker.ban(reason=f"Verbannen door {interaction.user}: {reden}", delete_message_days=0)
        
        # Bevestiging naar de moderator (ephemeral)
        confirm_embed = discord.Embed(
            title="Gebruiker verbannen",
            description=f"{gebruiker.display_name} is verbannen van de server.",
            color=discord.Color.green()
        )
        confirm_embed.add_field(name="Reden", value=reden, inline=False)
        await interaction.response.send_message(embed=confirm_embed, ephemeral=True)
        
        # Log naar het logkanaal
        log_channel = bot.get_channel(LOG_CHANNEL_MODERATOR_ID)
        if log_channel:
            log_embed = discord.Embed(
                title="Ban Log",
                description=f"{gebruiker.mention} is verbannen door {interaction.user.mention}",
                color=discord.Color.red(),
                timestamp=datetime.datetime.now(datetime.timezone.utc))
            log_embed.add_field(name="Reden", value=reden, inline=False)
            await log_channel.send(embed=log_embed)
            
    except discord.Forbidden:
        await interaction.response.send_message(
            "Ik heb geen permissies om deze gebruiker te bannen.",
            ephemeral=True
        )

@bot.tree.command(name="unban", description="Unban een gebruiker")
@commands.has_permissions(ban_members=True)
async def unban(interaction: discord.Interaction, gebruiker_id: str, reden: str = "Geen reden opgegeven"):
    """Unban een gebruiker op basis van ID"""
    try:
        gebruiker = await bot.fetch_user(int(gebruiker_id))
    except (discord.NotFound, ValueError):
        await interaction.response.send_message(
            "Ongeldig gebruikers-ID. Voer een geldig Discord gebruikers-ID in.",
            ephemeral=True
        )
        return
    
    try:
        await interaction.guild.unban(gebruiker, reason=f"Unban door {interaction.user}: {reden}")
        
        # Bevestiging naar de moderator
        confirm_embed = discord.Embed(
            title="Gebruiker geunbanned",
            description=f"{gebruiker.display_name} is weer toegestaan op de server.",
            color=discord.Color.green()
        )
        confirm_embed.add_field(name="Reden", value=reden, inline=False)
        await interaction.response.send_message(embed=confirm_embed, ephemeral=True)
        
        # Log naar het logkanaal
        log_channel = bot.get_channel(LOG_CHANNEL_MODERATOR_ID)
        if log_channel:
            log_embed = discord.Embed(
                title="Unban Log",
                description=f"{gebruiker.mention} is geunbanned door {interaction.user.mention}",
                color=discord.Color.green(),
                timestamp=datetime.datetime.now(datetime.timezone.utc))
            log_embed.add_field(name="Reden", value=reden, inline=False)
            await log_channel.send(embed=log_embed)
            
    except discord.NotFound:
        await interaction.response.send_message(
            "Deze gebruiker is niet verbannen.",
            ephemeral=True
        )
    except discord.Forbidden:
        await interaction.response.send_message(
            "Ik heb geen permissies om deze gebruiker te unbannen.",
            ephemeral=True
        )




@bot.event
async def on_ready():
    print(f"Moderatorbot is online als {bot.user}")
    
  
    try:
       
        
        guild = discord.Object(id=GUILD_ID)
        
        # Dit kopieert de globale commands naar je guild, zodat ze direct beschikbaar zijn
        bot.tree.copy_global_to(guild=guild)
        
        # Sync de commands met de specifieke guild
        await bot.tree.sync(guild=guild)
        print(f"Slash commands succesvol gesynced voor guild {GUILD_ID}")
        
    except Exception as e:
        print(f"Fout bij syncing commands: {str(e)}")

bot.run(token)