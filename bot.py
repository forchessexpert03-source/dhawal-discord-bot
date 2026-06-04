import os
import discord
from discord.ext import commands
from discord import app_commands
from flask import Flask
import threading

# --- INIITAL SETUP & INTENTS ---
intents = discord.Intents.default()
intents.members = True  # Required for welcome and auto-role
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# --- FLASK WEB SERVER FOR RENDER ---
app = Flask('')

@app.route('/')
def home():
    return "Dhawal Bot is Alive and Running 24/7!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- 20 BEAUTIFUL LOOPING QUOTES ---
QUOTES = [
    "“An early-morning walk is a blessing for the whole day.”",
    "“The secret of getting ahead is getting started.”",
    "“Opportunities don't happen, you create them.”",
    "“Do what you can, with what you have, where you are.”",
    "“Believe you can and you're halfway there.”",
    "“The only way to do great work is to love what you do.”",
    "“Act as if what you do makes a difference. It does.”",
    "“Success is not final, failure is not fatal: it is the courage to continue that counts.”",
    "“Never bend your head. Always hold it high. Look the world straight in the eye.”",
    "“What you get by achieving your goals is not as important as what you become by achieving your goals.”",
    "“You must do the things you think you cannot do.”",
    "“Keep your face always toward the sunshine—and shadows will fall behind you.”",
    "“Limit your 'always' and your 'nevers'.”",
    "“Hardships often prepare ordinary people for an extraordinary destiny.”",
    "“The big secret in life is that there is no big secret. Whatever your goal, you can get there if you are willing to work.”",
    "“Grow through what you go through.”",
    "“Be so good they can't ignore you.”",
    "“Your talent determines what you can do. Your motivation determines how much you are willing to do.”",
    "“Yesterday I was clever, so I wanted to change the world. Today I am wise, so I am changing myself.”",
    "“The best way to predict your future is to create it.”"
]

# --- WAVE INTERACTION BUTTON & STICKER CLASS ---
class WelcomeView(discord.ui.View):
    def __init__(self, target_member: discord.Member):
        super().__init__(timeout=None) # Keeps button active permanently
        self.target_member = target_member

    @discord.ui.button(label="Wave", style=discord.ButtonStyle.blurple, emoji="👋")
    async def wave_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 4. Standard Discord Waving Sticker ID
        waving_sticker_id = 749054660769218631 
        sticker = interaction.guild.get_sticker(waving_sticker_id)
        
        # Checking if standard sticker is available, otherwise falls back to message text
        if sticker:
            await interaction.channel.send(
                f"{interaction.user.mention} waved to {self.target_member.mention}! 👋", 
                stickers=[sticker]
            )
        else:
            await interaction.channel.send(
                f"{interaction.user.mention} waved to {self.target_member.mention}! 👋👋👋"
            )
        
        # Acknowledge the interaction secretly so the button doesn't show "interaction failed"
        await interaction.response.defer()

# --- EVENTS ---
@bot.event
async def on_ready():
    print(f'🤖 {bot.user.name} is ONLINE and synced!')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(e)

@bot.event
async def on_member_join(member: discord.Member):
    guild = member.guild
    
    # 1. AUTO-ROLE ASSIGNMENT ("Lil Dawg")
    role = discord.utils.get(guild.roles, name="Lil Dawg")
    if role:
        try:
            await member.add_roles(role)
            print(f"Assigned 'Lil Dawg' role to {member.name}")
        except discord.Forbidden:
            print(f"❌ Failed to assign role: Check bot hierarchy!")
        except Exception as e:
            print(f"Error assigning role: {e}")

    # 2. #WELCOME CHANNEL LOGIC (Sequential Looping Quotes)
    # Fetch channel named 'welcome'
    welcome_channel = discord.utils.get(guild.text_channels, name="welcome")
    if welcome_channel:
        total_members = len(guild.members)
        # Using Modulus (%) trick to cycle through 20 quotes sequentially
        quote_index = (total_members - 1) % len(QUOTES)
        selected_quote = QUOTES[quote_index]

        # Dynamic channel mentions
        color_channel = discord.utils.get(guild.text_channels, name="pick-your-color")
        rules_channel = discord.utils.get(guild.text_channels, name="rules")
        
        color_mention = color_channel.mention if color_channel else "#pick-your-color"
        rules_mention = rules_channel.mention if rules_channel else "#rules"

        # Beautiful Welcome Embed Creation
        embed = discord.Embed(
            title=f"Welcome to the Server, {member.name}! 🎉",
            description=f"We are glad to have you here with us!\n\n✨ *{selected_quote}*",
            color=discord.Color.from_rgb(114, 137, 218) # Classic Discord Blurple
        )
        embed.add_field(
            name="🎨 Get Roles", 
            value=f"Head over to {color_mention} to grab your custom colors!", 
            inline=False
        )
        embed.add_field(
            name="📜 Server Rules", 
            value=f"Make sure to check out {rules_mention} to keep the community clean.", 
            inline=False
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Member #{total_members}")

        await welcome_channel.send(content=member.mention, embed=embed)

    # 3. GENERAL CHAT LOGIC (Wave Trigger with Interactive Button)
    general_channel = discord.utils.get(guild.text_channels, name="general")
    if general_channel:
        view = WelcomeView(target_member=member)
        await general_channel.send(
            f"Hey crew! {member.mention} has joined the server. Say hi or wave to them! 👋",
            view=view
        )

# --- KEEP EXISTING SLASH COMMANDS BELOW THIS LINE UNCHANGED ---
@bot.tree.command(name="ping", description="Test bot response")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"Pong! {round(bot.latency * 1000)}ms")

# --- BOT RUNNER ---
if __name__ == "__main__":
    # Start Flask on a separate background thread
    threading.Thread(target=run_web_server, daemon=True).start()
    
    # Run Discord Bot
    token = os.environ.get('DISCORD_BOT_TOKEN')
    bot.run(token)