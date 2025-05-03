import os
import discord
from dotenv import load_dotenv
from groq import Groq



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
    # Negeer berichten van de bot zelf
    if message.author == bot.user:
        return

    # Reageer alleen als de bot wordt genoemd (@BotNaam)
    if bot.user.mentioned_in(message):
        # Verwijder de @mention uit de vraag
        vraag = message.content.replace(f'<@{bot.user.id}>', '').strip()
        
        # Toon "typing" indicator terwijl de AI werkt
        async with message.channel.typing():
            try:
                # Vraag antwoord aan Groq AI
                response = groq_client.chat.completions.create(
                    model="mixtral-8x7b-32768",
                    messages=[{"role": "user", "content": vraag}],
                    temperature=0.7
                )
                antwoord = response.choices[0].message.content
                
                # Stuur het antwoord terug
                await message.reply(antwoord)
                
            except Exception as e:
                await message.reply(f"⚠️ Fout: {str(e)}")


# Start de bot
bot.run(os.getenv("Discord_StudyBot_Token"))    