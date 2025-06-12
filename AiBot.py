import os
import discord
from dotenv import load_dotenv
from groq import Groq
import io
from datetime import datetime
import PyPDF2
from collections import deque  

load_dotenv()
intents = discord.Intents.default()
intents.message_content = True  
bot = discord.Client(intents=intents)
groq_client = Groq(api_key=os.getenv("Groq_API_Key"))

STUDY_CHANNEL_ID = os.getenv("STUDYBOT_CHANNEL")

MAX_HISTORY = 12  
message_history = deque(maxlen=MAX_HISTORY)  #deue voor historie bijhouden 

def extract_text_from_pdf(file_content):# functie voor pdf te kunnen lezen voor de ai
    text = ""
    try:
        with io.BytesIO(file_content) as pdf_file:
            reader = PyPDF2.PdfReader(pdf_file)
            for page in reader.pages:
                text += page.extract_text() # tekst uit de pdf halen
    except Exception as e:
        print(f"Fout bij PDF extractie: {e}")
    return text

def extract_text_from_txt(file_content): #tekst uit .txt bestand halen 
    try:
        return file_content.decode('utf-8') #naar utf 8 decoderen 
    except Exception as e:
        print(f"Fout bij TXT extractie: {e}")
        return ""

async def process_attachments(message): # functie voor te kijken of bijlagen pdf of txt zijn en deze te verwerken
    extracted_texts = []
    for attachment in message.attachments:
        if attachment.filename.lower().endswith('.pdf'):
            file_content = await attachment.read()
            text = extract_text_from_pdf(file_content)
            if text:
                extracted_texts.append(f"PDF-bestand '{attachment.filename}':\n{text[:20000]}...")
        elif attachment.filename.lower().endswith('.txt'):
            file_content = await attachment.read()
            text = extract_text_from_txt(file_content)
            if text:
                extracted_texts.append(f"Tekstbestand '{attachment.filename}':\n{text[:20000]}...")
    return "\n\n".join(extracted_texts) if extracted_texts else None

@bot.event
async def on_ready():
    print(f'Bot is ingelogd als {bot.user}')

@bot.event
async def on_message(message):
    
    if bot.user.mentioned_in(message):
        user_input = message.content.replace(f'<@{bot.user.id}>', '').strip()
        
        
        if "nieuw onderwerp" in user_input.lower():# reset de historie voor van nul te beginnen
            message_history.clear()
            await message.reply("🔄 Oké, ik begin met een schone lei!")
            return
        
        attachment_text = "" ## voor het verwerken van bijlagen
        if message.attachments:
            attachment_text = await process_attachments(message)
            if attachment_text:
                user_input += f"\n\nHier is de inhoud van de bijgevoegde bestanden:\n{attachment_text}"
        
        
        message_history.append({"role": "user", "content": user_input})

        async with message.channel.typing():
            try:
               
                response = groq_client.chat.completions.create(
                    model="llama3-70b-8192",
                    messages=list(message_history),  
                    max_tokens=4000
                )
                
                antwoord = response.choices[0].message.content
                
               
                message_history.append({"role": "assistant", "content": antwoord})

                if len(antwoord) > 1900: # als het antwoord te lang is, sla het op in een txt bestand en verstuur ddat
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"antwoord_{timestamp}.txt"
                    file = io.StringIO(antwoord)
                    discord_file = discord.File(file, filename=filename)
                    await message.reply("Hier is mijn uitgebreide antwoord:", file=discord_file)
                else:
                    await message.reply(antwoord)
                    
            except Exception as e:
                await message.reply(f"⚠️ Fout: {str(e)}")

bot.run(os.getenv("Discord_StudyBot_Token"))