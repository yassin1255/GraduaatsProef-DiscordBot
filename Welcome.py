import discord
from discord import File 
from discord.ext import commands
from easy_pil import Editor, load_image_async, Font


bot = commands.Bot(command_prefix='>', intents=discord.Intents.all())

@bot.event
async def on_ready():
    print("bot is online")

@bot.event 
async def on_member_join(member):
    channel = bot.get_channel(1358385144024530964)
    if channel is None:
        print("Channel not found")
        return

    background = Editor("images/thousandsunny.jpg")
    profile_image = await load_image_async(str(member.avatar.url))

    profile = Editor(profile_image).resize((150, 150)).circle_image()
    poppins = Font.poppins(size=50, variant="bold")
    poppins_small = Font.poppins(size=20, variant="light")

    background.paste(profile, (325, 90))
    background.ellipse((325,90),150,150, outline="white",stroke_width=5)
    background.text((400, 260), f"WELCOME TO {member.guild.name}", font=poppins, color="white")
    background.text((400, 325), f"{member.name}#{member.discriminator}", font=poppins_small, color="white", align="center")

    file = discord.File(fp=background.image_bytes, filename="welcome.png")
    await channel.send(f"Hello  {member.mention}!  Welcome to {member.guild.name}!")
    await channel.send(file=File(fp=background.image_bytes, filename="welcome.png"))
    await channel.send("We hope you enjoy your stay!")

@bot.command(name='simjoin')
async def simulate_join(ctx):
    """Simuleer join met je eigen account"""
    try:
        await bot.on_member_join(ctx.author)
        await ctx.send("✅ Welkomstbericht gegenereerd!", delete_after=5)
    except Exception as e:
        await ctx.send(f"❌ Fout: {str(e)}", delete_after=15)
        print(f"Test error: {e}")

bot.run("MTM1NjcxNTM1MTA3NzAyODAyMA.GvY1HR.xUj-W0EtXGuHyrbLisReg6I-CGhTU2mX1s-cbo")