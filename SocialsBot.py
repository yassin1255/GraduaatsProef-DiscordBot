import os
import discord
from dotenv import load_dotenv
from discord import app_commands
from discord.ext import commands
from atproto import Client
import datetime

load_dotenv()


DISCORD_TOKEN = os.getenv("Discord_SocialsBot_Token")
BSKY_HANDLE = os.getenv("BSKY_HANDLE")
BSKY_APP_PASSWORD = os.getenv("BSKY_APP_PASSWORD")
STATS_CHANNEL_ID = int(os.getenv("STATS_CHANNEL_ID"))
GUILD_ID = int(os.getenv("GUILD_ID")) 


intents = discord.Intents.default()
intents.message_content = True

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix='!',
            intents=intents,
            help_command=None
        )
        self.bsky_client = Client()
        self.guild = discord.Object(id=GUILD_ID) if GUILD_ID else None

    async def setup_hook(self):
       
        if self.guild:
            self.tree.copy_global_to(guild=self.guild)
            await self.tree.sync(guild=self.guild)
            print(f"Commands gesynced voor guild {GUILD_ID}")
        else:
            await self.tree.sync()
            print("Globale commands gesynced")

bot = MyBot()

@bot.event
async def on_ready():
    print(f"Bot is online als {bot.user}")
    try:
        bot.bsky_client.login(BSKY_HANDLE, BSKY_APP_PASSWORD)
        print("Bluesky login succesvol")
    except Exception as e:
        print(f"Bluesky login fout: {str(e)}")

@bot.tree.command(name="post", description="Post een bericht naar Bluesky")
@app_commands.describe(message="Het bericht dat je wilt posten")
async def post(interaction: discord.Interaction, message: str):
    try:
        await interaction.response.defer(ephemeral=True)
        
        # Post naar Bluesky
        post = bot.bsky_client.send_post(message)
        post_link = f"https://bsky.app/profile/{BSKY_HANDLE}/post/{post.uri.split('/')[-1]}"
        
        embed = discord.Embed(
            title="✅ Bericht gepost op Bluesky",
            description=message,
            color=0x1DA1F2,
            url=post_link
        )
        embed.add_field(name="🔗 Link", value=f"[Bekijk post]({post_link})", inline=False)
        
        await interaction.followup.send(embed=embed, ephemeral=True)
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
        feed = bot.bsky_client.get_author_feed(actor=BSKY_HANDLE)
        
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