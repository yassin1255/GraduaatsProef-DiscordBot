import os
import discord
from dotenv import load_dotenv
from discord import app_commands
from discord.ext import commands
from atproto import Client, models
import datetime
import requests
import matplotlib.pyplot as plt
import pandas as pd
from io import BytesIO
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage


load_dotenv()

DISCORD_TOKEN = os.getenv("Discord_SocialsBot_Token")
BSKY_HANDLE = os.getenv("BSKY_HANDLE")
BSKY_APP_PASSWORD = os.getenv("BSKY_APP_PASSWORD")
STATS_CHANNEL_ID = int(os.getenv("STATS_CHANNEL_ID"))
GUILD_ID = int(os.getenv("GUILD_ID")) 
LIVE_CHANNEL_ID = int(os.getenv("LIVE_CHANNEL_ID"))  
STREAM_URL = os.getenv("STREAM_URL") 

DEFAULT_EMAIL = os.getenv("DEFAULT_EMAIL")
EMAIL_FROM = os.getenv("EMAIL_FROM")
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")


intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)
bsky_client = Client()


def parse_bluesky_timestamp(timestamp_str):
    """Speciale parser voor Bluesky timestamps die niet altijd perfect ISO format zijn"""
    try:
        # Verwijder nanoseconden als die te lang zijn
        if '.' in timestamp_str:
            parts = timestamp_str.split('.')
            if len(parts[1]) > 6:  # Meer dan 6 decimalen
                timestamp_str = f"{parts[0]}.{parts[1][:6]}{parts[1][6:]}"
        
        # Zorg voor correcte timezone format
        if timestamp_str.endswith('Z'):
            timestamp_str = timestamp_str[:-1] + '+00:00'
        elif '+' in timestamp_str and timestamp_str.count(':') == 2:  # Alleen tijd heeft :
            timestamp_str = timestamp_str.replace('+', '+00:')
        elif '-' in timestamp_str and timestamp_str.count(':') == 2:
            timestamp_str = timestamp_str.replace('-', '-00:')
        
        # Parse de datetime
        dt = datetime.datetime.fromisoformat(timestamp_str)
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt
    except ValueError as e:
        print(f"Fout bij parsen timestamp {timestamp_str}: {str(e)}")
        return None

@bot.tree.command(name="statsvandaag", description="Toon stats van posts in de afgelopen 24 uur")
@app_commands.describe(email="Optioneel emailadres om de stats naar toe te sturen")
async def statsvandaag(interaction: discord.Interaction, email: str = None):
    if interaction.channel_id != STATS_CHANNEL_ID:
        await interaction.response.send_message(
            "❌ Dit commando werkt alleen in het stats-kanaal!",
            ephemeral=True
        )
        return
    
    try:
        await interaction.response.defer()
        
        # Bereken 24 uur geleden
        now = datetime.datetime.now(datetime.timezone.utc)
        twenty_four_hours_ago = now - datetime.timedelta(hours=24)
        
        # Haal posts op en filter op tijd
        feed = bsky_client.get_author_feed(actor=BSKY_HANDLE)
        recent_posts = [
            post for post in feed.feed 
            if parse_bluesky_timestamp(post.post.record.created_at) >= twenty_four_hours_ago
        ]
        
        if not recent_posts:
            await interaction.followup.send("❌ Geen posts gevonden in de afgelopen 24 uur!", ephemeral=True)
            return
        
       
        post_data = []
        for post in recent_posts:
            post_time = parse_bluesky_timestamp(post.post.record.created_at)
            hour = post_time.hour
            likes = post.post.like_count or 0
            reposts = post.post.repost_count or 0
            replies = post.post.reply_count or 0
            
            post_data.append({
                'hour': hour,
                'likes': likes,
                'reposts': reposts,
                'replies': replies,
                'total_engagement': likes + reposts + replies,
                'post_text': post.post.record.text[:50] + "..." if len(post.post.record.text) > 50 else post.post.record.text,
                'post_url': f"https://bsky.app/profile/{BSKY_HANDLE}/post/{post.post.uri.split('/')[-1]}"
            })
        
        df = pd.DataFrame(post_data)
        hourly_stats = df.groupby('hour').agg({
            'likes': 'sum',
            'reposts': 'sum',
            'replies': 'sum',
            'total_engagement': 'sum',
        }).reindex(range(24), fill_value=0)
        
        
        plt.figure(figsize=(10, 5))
        plt.bar(hourly_stats.index, hourly_stats['total_engagement'], color='skyblue', alpha=0.7, label='Engagement')
        plt.plot(hourly_stats.index, hourly_stats['likes'], 'r-', label='Likes')
        plt.plot(hourly_stats.index, hourly_stats['reposts'], 'g-', label='Reposts')
        plt.xlabel('Uur van de dag')
        plt.ylabel('Aantal')
        plt.title('Activiteit laatste 24 uur')
        plt.legend()
        plt.tight_layout()
        
        
        img_buffer = BytesIO()
        plt.savefig(img_buffer, format='png', dpi=100)
        plt.close()
        img_buffer.seek(0)
        
        
        top_post = df.loc[df['total_engagement'].idxmax()]
        embed = discord.Embed(
            title="📊 Stats laatste 24 uur",
            description=f"**Top post:** {top_post['post_text']}\n"
                       f"❤️ {top_post['likes']} | 🔄 {top_post['reposts']} | 💬 {top_post['replies']}\n"
                       f"🔗 [Bekijk post]({top_post['post_url']})",
            color=0x1DA1F2
        )
        embed.set_image(url="attachment://stats.png")
        
       
        await interaction.followup.send(
            embed=embed,
            file=discord.File(img_buffer, filename='stats.png')
        )
        
       
        if email or DEFAULT_EMAIL:
            msg = MIMEMultipart()
            msg['From'] = EMAIL_FROM or DEFAULT_EMAIL
            msg['To'] = email or DEFAULT_EMAIL
            msg['Subject'] = f"Bluesky stats - {now.strftime('%d/%m/%Y')}"
            
            email_text = f"Bluesky statistieken laatste 24 uur\n\n" \
                        f"Totaal posts: {len(recent_posts)}\n" \
                        f"Totaal engagement: {df['total_engagement'].sum()}\n" \
                        f"Top post: {top_post['post_text']}\n" \
                        f"Likes: {top_post['likes']} | Reposts: {top_post['reposts']} | Replies: {top_post['replies']}\n" \
                        f"Link: {top_post['post_url']}"
            
            msg.attach(MIMEText(email_text))
            img_buffer.seek(0)
            msg.attach(MIMEImage(img_buffer.read()))
            
            try:
                with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                    server.starttls()
                    server.login(SMTP_USERNAME, SMTP_PASSWORD)
                    server.send_message(msg)
                await interaction.followup.send(f"✅ Stats verzonden naar {email or DEFAULT_EMAIL}", ephemeral=True)
            except Exception as e:
                await interaction.followup.send(f"⚠️ Email versturen mislukt: {str(e)}", ephemeral=True)
        
    except Exception as e:
        await interaction.followup.send(f"⚠️ Fout: {str(e)}", ephemeral=True)

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