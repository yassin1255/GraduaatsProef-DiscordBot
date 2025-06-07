import os
import discord
from dotenv import load_dotenv
from discord import app_commands
from discord.ext import commands
from atproto import Client, models
import datetime
import requests
from io import BytesIO

load_dotenv()

DISCORD_TOKEN = os.getenv("Discord_SocialsBot_Token")
BSKY_HANDLE = os.getenv("BSKY_HANDLE")
BSKY_APP_PASSWORD = os.getenv("BSKY_APP_PASSWORD")
STATS_CHANNEL_ID = int(os.getenv("STATS_CHANNEL_ID"))
GUILD_ID = int(os.getenv("GUILD_ID")) 
LIVE_CHANNEL_ID = int(os.getenv("LIVE_CHANNEL_ID"))  
STREAM_URL = os.getenv("STREAM_URL") 

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)
bsky_client = Client()

@bot.event
async def on_ready():
    print(f"Bot is online als {bot.user}")
    try:
        bsky_client.login(BSKY_HANDLE, BSKY_APP_PASSWORD)
        print("Bluesky login succesvol")
        
        if GUILD_ID:
            guild = discord.Object(id=GUILD_ID)
            bot.tree.copy_global_to(guild=guild)
            await bot.tree.sync(guild=guild)
            print(f"Commands gesynced voor guild {GUILD_ID}")
        else:
            await bot.tree.sync()
            print("Globale commands gesynced")
    except Exception as e:
        print(f"Bluesky login fout: {str(e)}")

async def download_media(url):
    response = requests.get(url)
    if response.status_code == 200:
        return BytesIO(response.content)
    return None

@bot.tree.command(name="live", description="Maak een live aankondiging")
@app_commands.describe(
    message="Optioneel bericht voor de aankondiging (laat leeg voor standaard bericht)",
    stream_url="Stream URL (laat leeg voor standaard URL)"
)
async def live(
    interaction: discord.Interaction, 
    message: str = None,
    stream_url: str = None
):
    try:
        await interaction.response.defer(ephemeral=True)
        
        # Gebruik standaard waarden als niet opgegeven
        final_stream_url = stream_url or STREAM_URL
        if not final_stream_url:
            await interaction.followup.send("⚠️ Geen stream URL gevonden!", ephemeral=True)
            return
        
        final_message = message or "I'm live! Join the stream"
        full_text = f"{final_message}\n\n{final_stream_url}"
        
        # Post naar Bluesky
        post = bsky_client.send_post(text=full_text)
        
        # Stuur bericht naar live kanaal
        live_channel = bot.get_channel(LIVE_CHANNEL_ID)
        if live_channel:
            try:
                discord_msg = await live_channel.send(
                    f"@everyone\n{final_message}\n\n{final_stream_url}"
                )
                try:
                    await discord_msg.pin()
                except discord.Forbidden:
                    await interaction.followup.send(
                        "⚠️ Kon bericht niet pinnen - controleer bot permissies (Manage Messages nodig)",
                        ephemeral=True
                    )
            except discord.Forbidden:
                await interaction.followup.send(
                    "⚠️ Kon geen bericht sturen naar live kanaal - controleer bot permissies",
                    ephemeral=True
                )
        
        # Stuur bevestiging naar gebruiker
        post_link = f"https://bsky.app/profile/{BSKY_HANDLE}/post/{post.uri.split('/')[-1]}"
        discord_embed = discord.Embed(
            title="✅ Live aankondiging gemaakt",
            description=full_text,
            color=0x9147FF
        )
        discord_embed.add_field(name="🔗 Bluesky Post", value=f"[Bekijk op Bluesky]({post_link})", inline=False)
        
        if live_channel:
            discord_embed.add_field(
                name="📌 Discord Kanaal", 
                value=f"Bericht gestuurd naar <#{LIVE_CHANNEL_ID}>", 
                inline=False
            )
        
        await interaction.followup.send(embed=discord_embed, ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"⚠️ Fout: {str(e)}", ephemeral=True)


@bot.tree.command(name="post", description="Post een bericht naar Bluesky")
@app_commands.describe(
    message="Het bericht dat je wilt posten",
    media1="Eerste afbeelding (optioneel)",
    media2="Tweede afbeelding (optioneel)",
    media3="Derde afbeelding (optioneel)",
    media4="Vierde afbeelding (optioneel)"
)
async def post(
    interaction: discord.Interaction, 
    message: str, 
    media1: discord.Attachment = None,
    media2: discord.Attachment = None,
    media3: discord.Attachment = None,
    media4: discord.Attachment = None
):
    try:
        await interaction.response.defer(ephemeral=True)
        
        embed = None
        media_items = [m for m in [media1, media2, media3, media4] if m is not None and m.content_type.startswith('image/')]
        
        if media_items:
            images = []
            
            for attachment in media_items:
                media_data = await download_media(attachment.url)
                if media_data:
                    upload = bsky_client.upload_blob(media_data.getvalue())
                    images.append(models.AppBskyEmbedImages.Image(
                        image=upload.blob,
                        alt=f"Afbeelding {len(images)+1}"
                    ))
            
            if len(images) > 4:
                await interaction.followup.send("⚠️ Maximaal 4 afbeeldingen toegestaan!", ephemeral=True)
                return
            
            if images:
                embed = models.AppBskyEmbedImages.Main(images=images)
        
        post = bsky_client.send_post(text=message, embed=embed)
        post_link = f"https://bsky.app/profile/{BSKY_HANDLE}/post/{post.uri.split('/')[-1]}"
        
        discord_embed = discord.Embed(
            title="✅ Bericht gepost op Bluesky",
            description=message,
            color=0x1DA1F2,
            url=post_link
        )
        
        if media_items:
            discord_embed.add_field(
                name="Media",
                value=f"✅ {len(media_items)} afbeelding(en) bijgevoegd",
                inline=False
            )
            discord_embed.set_image(url=media_items[0].url)
        
        discord_embed.add_field(name="🔗 Link", value=f"[Bekijk post]({post_link})", inline=False)
        
        await interaction.followup.send(embed=discord_embed, ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"⚠️ Fout: {str(e)}", ephemeral=True)

@bot.tree.command(name="stats", description="Toon stats van laatste Bluesky post")
async def stats(interaction: discord.Interaction):
    if interaction.channel_id != STATS_CHANNEL_ID:
        await interaction.response.send_message(
            "❌ Dit commando werkt alleen in het stats-kanaal!",
            ephemeral=True
        )
        return
    
    try:
        await interaction.response.defer()
        feed = bsky_client.get_author_feed(actor=BSKY_HANDLE)
        
        if not feed.feed:
            await interaction.followup.send("❌ Geen posts gevonden!", ephemeral=True)
            return
        
        post = feed.feed[0].post
        post_link = f"https://bsky.app/profile/{BSKY_HANDLE}/post/{post.uri.split('/')[-1]}"
        
        embed = discord.Embed(
            title="📊 Laatste Bluesky Stats",
            description=post.record.text[:500] + ("..." if len(post.record.text) > 500 else ""),
            color=0x1DA1F2,
            url=post_link
        )
        embed.add_field(name="❤️ Likes", value=post.like_count, inline=True)
        embed.add_field(name="🔄 Reposts", value=post.repost_count, inline=True)
        embed.add_field(name="💬 Replies", value=post.reply_count, inline=True)
        embed.add_field(name="🔗 Link", value=f"[Bekijk post]({post_link})", inline=False)
        
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"⚠️ Fout: {str(e)}", ephemeral=True)

bot.run(DISCORD_TOKEN)