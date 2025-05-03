import os
import discord
from dotenv import load_dotenv
from groq import Groq
import io
from datetime import datetime



load_dotenv()
intents = discord.Intents.default()
intents.message_content = True  
bot = discord.Client(intents=intents)
groq_client = Groq(api_key=os.getenv("Groq_API_Key"))
 
 
@bot.event
async def on_ready():
    print(f'Bot is ingelogd als {bot.user}')

@bot.event
async def on_message(message):
    if bot.user.mentioned_in(message):
        user_input = message.content.replace(f'<@{bot.user.id}>', '').strip()
        
        async with message.channel.typing():
            try:
                response = groq_client.chat.completions.create(
                    model="llama3-70b-8192",
                    messages=[{"role": "user", "content": user_input}],
                    max_tokens=4000  # Meer tokens voor langere antwoorden
                )
                
                antwoord = response.choices[0].message.content
                
                if len(antwoord) > 1900:
                    # Maak een tekstbestand aan
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"antwoord_{timestamp}.txt"
                    
                    # Maak een 'file-like object' aan
                    file = io.StringIO(antwoord)
                    discord_file = discord.File(file, filename=filename)
                    
                    await message.reply("Hier is mijn uitgebreide antwoord:", file=discord_file)
                else:
                    await message.reply(antwoord)
                    
            except Exception as e:
                await message.reply(f"⚠️ Fout: {str(e)}")


# Start de bot
bot.run(os.getenv("Discord_StudyBot_Token"))    