import os
import discord
from discord.ext import commands
from discord import app_commands
from flask import Flask
import threading
import datetime

# --- INITIAL SETUP & INTENTS ---
intents = discord.Intents.default()
intents.members = True  # Required for welcome system and auto-role
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
    "Hardships often prepare ordinary people for an extraordinary destiny.",
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
        super().__init__(timeout=None)
        self.target_member = target_member

    @discord.ui.button(label="Wave", style=discord.ButtonStyle.blurple, emoji="👋")
    async def wave_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # INSTANTLY defer to make sure Discord registers the click under 3 seconds
        await interaction.response.defer()
        
        # Exact Sticker ID parsed from your Discord URL
        waving_sticker_id = 1512147790975865043 
        sticker = interaction.guild.get_sticker(waving_sticker_id)
        
        if sticker:
            await interaction.channel.send(
                f"{interaction.user.mention} waved to {self.target_member.mention}! 👋", 
                stickers=[sticker]
            )
        else:
            # Safe text fallback if the bot faces latency while fetching the sticker asset
            await interaction.channel.send(
                f"{interaction.user.mention} waved to {self.target_member.mention}! 👋👋👋"
            )

# --- EVENTS ---
@bot.event
async def on_ready():
    print(f'🤖 {bot.user.name} is ONLINE!')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s) globally")
    except Exception as e:
        print(f"Error syncing on startup: {e}")

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

    # 2. #WELCOME CHANNEL LOGIC
    welcome_channel = discord.utils.get(guild.text_channels, name="welcome")
    if welcome_channel:
        total_members = len(guild.members)
        quote_index = (total_members - 1) % len(QUOTES)
        selected_quote = QUOTES[quote_index]

        # Exact matched channel names from your layout
        color_channel = discord.utils.get(guild.text_channels, name="🎨︱pick-your-color")
        rules_channel = discord.utils.get(guild.text_channels, name="📜rules")
        
        color_mention = color_channel.mention if color_channel else "`🎨︱pick-your-color`"
        rules_mention = rules_channel.mention if rules_channel else "`📜rules`"

        embed = discord.Embed(
            title=f"Welcome to the Server, {member.name}! 🎉",
            description=f"We are glad to have you here with us!\n\n✨ *{selected_quote}*",
            color=discord.Color.from_rgb(114, 137, 218)
        )
        embed.add_field(name="🎨 Get Roles", value=f"Head over to {color_mention} to grab your custom colors!", inline=False)
        embed.add_field(name="📜 Server Rules", value=f"Make sure to check out {rules_mention} to keep the community clean.", inline=False)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Member #{total_members}")

        await welcome_channel.send(content=member.mention, embed=embed)

    # 3. GENERAL CHAT LOGIC
    general_channel = discord.utils.get(guild.text_channels, name="general")
    if general_channel:
        view = WelcomeView(target_member=member)
        await general_channel.send(
            f"Hey crew! {member.mention} has joined the server. Say hi or wave to them! 👋",
            view=view
        )

# --- MASTER FORCE-SYNC TEXT COMMAND ---
@bot.command()
@commands.is_owner()
async def sync(ctx):
    try:
        await bot.tree.sync()
        await ctx.send("🔄 Saari Slash Commands refresh aur sync ho gayi hain!")
    except Exception as e:
        await ctx.send(f"❌ Sync failed: {e}")

# --- BASIC & UTILITY SLASH COMMANDS ---

@bot.tree.command(name="ping", description="Test bot response speed")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"Pong! {round(bot.latency * 1000)}ms")

@bot.tree.command(name="serverinfo", description="Get detailed server statistics")
async def serverinfo(interaction: discord.Interaction):
    guild = interaction.guild
    embed = discord.Embed(title=f"{guild.name} Info", color=discord.Color.blue())
    embed.add_field(name="Total Members", value=guild.member_count, inline=True)
    embed.add_field(name="Created At", value=guild.created_at.strftime("%B %d, %Y"), inline=True)
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="avatar", description="View or download someone's profile picture")
async def avatar(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    embed = discord.Embed(title=f"{member.name}'s Avatar", color=discord.Color.random())
    embed.set_image(url=member.display_avatar.url)
    await interaction.response.send_message(embed=embed)

# --- MODERATION SLASH COMMANDS ---

@bot.tree.command(name="kick", description="Kick a member from the server")
@app_commands.checks.has_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    await member.kick(reason=reason)
    await interaction.response.send_message(f"🚨 **{member.name}** has been kicked. Reason: {reason}")

@bot.tree.command(name="ban", description="Ban a member from the server")
@app_commands.checks.has_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    await member.ban(reason=reason)
    await interaction.response.send_message(f"🔨 **{member.name}** has been banned permanently. Reason: {reason}")

@bot.tree.command(name="mute", description="Mute (Timeout) a member")
@app_commands.checks.has_permissions(moderate_members=True)
async def mute(interaction: discord.Interaction, member: discord.Member, duration_minutes: int = 10, reason: str = "No reason provided"):
    duration = datetime.timedelta(minutes=duration_minutes)
    await member.timeout(duration, reason=reason)
    await interaction.response.send_message(f"🔇 **{member.name}** has been muted for {duration_minutes} minutes. Reason: {reason}")

@bot.tree.command(name="unmute", description="Remove mute (Timeout) from a member")
@app_commands.checks.has_permissions(moderate_members=True)
async def unmute(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    await member.timeout(None, reason=reason)
    await interaction.response.send_message(f"🔊 **{member.name}** has been unmuted.")

@bot.tree.command(name="warn", description="Warn a member in the channel")
@app_commands.checks.has_permissions(manage_messages=True)
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    embed = discord.Embed(title="⚠️ Warning Issued", color=discord.Color.orange())
    embed.add_field(name="User", value=member.mention, inline=True)
    embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
    embed.add_field(name="Reason", value=reason, inline=False)
    await interaction.response.send_message(content=member.mention, embed=embed)

# --- BOT RUNNER ---
if __name__ == "__main__":
    threading.Thread(target=run_web_server, daemon=True).start()
    token = os.environ.get('DISCORD_BOT_TOKEN')
    bot.run(token)