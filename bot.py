import discord
from discord.ext import commands
from discord import app_commands
import datetime
from flask import Flask
from threading import Thread
import os

# --- FLASK WEB SERVER FOR CRON-JOB PING ---
app = Flask('')

@app.route('/')
def home():
    return "Dhawal Bot is Alive and Running 24/7!"

def run_web_server():
    # Render automatic 'PORT' environment variable deta hai, nahi toh default 8080
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web_server)
    t.start()
# ------------------------------------------

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        self.add_view(ColorView())
        await self.tree.sync()
        print("⚡ Dhawal Bot: All Commands Synced!")

bot = MyBot()

@bot.event
async def on_ready():
    print(f'🤖 Dhawal Bot is ONLINE as {bot.user.name}')
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="over the server!"))

# ----------------- 1. WELCOME SYSTEM -----------------
@bot.event
async def on_member_join(member):
    channel = discord.utils.get(member.guild.text_channels, name="general")
    if channel:
        embed = discord.Embed(
            title=f"🎉 Welcome to the Crew, {member.name}! 🎉",
            description=f"Yo {member.mention}! Server join karne ke liye shukriya.\n\nJangan mat bhoolna 🎨︱`pick-your-color` channel se apna name color choose karna!",
            color=discord.Color.from_rgb(88, 101, 242),
            timestamp=datetime.datetime.utcnow()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_author(name=member.guild.name, icon_url=member.guild.icon.url if member.guild.icon else None)
        embed.set_footer(text=f"Member #{len(member.guild.members)}")
        await channel.send(content=member.mention, embed=embed)

# ----------------- 2. UTILITY & MANAGEMENT COMMANDS -----------------
@bot.tree.command(name="purge", description="Delete a specific number of messages from this channel")
@app_commands.checks.has_permissions(manage_messages=True)
async def purge(interaction: discord.Interaction, amount: int):
    if amount < 1:
        await interaction.response.send_message("❌ Kam se kam 1 message delete karo bhai!", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.followup.send(f"🧹 Successfully cleared {len(deleted)} messages!", ephemeral=True)

@bot.tree.command(name="serverinfo", description="Get detailed information about this server")
async def serverinfo(interaction: discord.Interaction):
    guild = interaction.guild
    embed = discord.Embed(title=f"📊 {guild.name} Stats", color=discord.Color.teal())
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.add_field(name="Owner", value=guild.owner.mention if guild.owner else "Unknown", inline=True)
    embed.add_field(name="Total Members", value=str(guild.member_count), inline=True)
    embed.add_field(name="Text Channels", value=str(len(guild.text_channels)), inline=True)
    embed.add_field(name="Voice Channels", value=str(len(guild.voice_channels)), inline=True)
    embed.set_footer(text=f"Server Created: {guild.created_at.strftime('%d-%b-%Y')}")
    await interaction.response.send_message(embed=embed)

# ----------------- 3. MODERATION SUITE -----------------
@bot.tree.command(name="warn", description="Issue a single formal warning to a member")
@app_commands.checks.has_permissions(manage_messages=True)
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str):
    embed = discord.Embed(title="⚠️ Server Warning Issued", color=discord.Color.red())
    embed.add_field(name="User", value=member.mention, inline=True)
    embed.add_field(name="Warned By", value=interaction.user.mention, inline=True)
    embed.add_field(name="Reason", value=reason, inline=False)
    await interaction.channel.send(content=member.mention, embed=embed)
    await interaction.response.send_message("Warning logged successfully.", ephemeral=True)

@bot.tree.command(name="mute", description="Mute/Timeout a member (in minutes)")
@app_commands.checks.has_permissions(moderate_members=True)
async def mute(interaction: discord.Interaction, member: discord.Member, duration_minutes: int, reason: str = "No reason provided"):
    duration = datetime.timedelta(minutes=duration_minutes)
    try:
        await member.timeout(duration, reason=reason)
        await interaction.response.send_message(f"🔇 {member.mention} has been muted for {duration_minutes} minutes. Reason: {reason}")
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

@bot.tree.command(name="unmute", description="Remove timeout from a member")
@app_commands.checks.has_permissions(moderate_members=True)
async def unmute(interaction: discord.Interaction, member: discord.Member):
    try:
        await member.timeout(None)
        await interaction.response.send_message(f"🔊 {member.mention} has been unmuted!")
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

@bot.tree.command(name="kick", description="Kick a member from the server")
@app_commands.checks.has_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    await member.kick(reason=reason)
    await interaction.response.send_message(f"👢 {member.mention} has been kicked. Reason: {reason}")

@bot.tree.command(name="ban", description="Permanently ban a member")
@app_commands.checks.has_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    await member.ban(reason=reason)
    await interaction.response.send_message(f"🚫 {member.mention} has been banned. Reason: {reason}")

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("❌ Bhai, tumhare paas permissions nahi hain!", ephemeral=True)

# ----------------- 4. COLOR DROPDOWN SYSTEM -----------------
class ColorDropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Red", description="Choose Red", emoji="🔴"),
            discord.SelectOption(label="Blue", description="Choose Blue", emoji="🔵"),
            discord.SelectOption(label="Green", description="Choose Green", emoji="🟢"),
            discord.SelectOption(label="Yellow", description="Choose Yellow", emoji="🟡"),
            discord.SelectOption(label="Orange", description="Choose Orange", emoji="🟠"),
            discord.SelectOption(label="Purple", description="Choose Purple", emoji="🟣"),
            discord.SelectOption(label="Pink", description="Choose Pink", emoji="💗")
        ]
        super().__init__(placeholder="Tap here to pick your profile color...", min_values=1, max_values=1, options=options, custom_id="color_select_dropdown")

    async def callback(self, interaction: discord.Interaction):
        chosen_color = self.values[0]
        role = discord.utils.get(interaction.guild.roles, name=chosen_color)
        
        if not role:
            await interaction.response.send_message(f"❌ '{chosen_color}' role server me nahi mila!", ephemeral=True)
            return

        if role in interaction.user.roles:
            await interaction.user.remove_roles(role)
            await interaction.response.send_message(f"🔄 Removed **{chosen_color}**!", ephemeral=True)
        else:
            all_colors = ["Red", "Blue", "Green", "Yellow", "Orange", "Purple", "Pink"]
            roles_to_remove = [discord.utils.get(interaction.guild.roles, name=c) for c in all_colors if c != chosen_color]
            for old_role in roles_to_remove:
                if old_role and old_role in interaction.user.roles:
                    await interaction.user.remove_roles(old_role)
            await interaction.user.add_roles(role)
            await interaction.response.send_message(f"🎨 Success! Your color is now **{chosen_color}**!", ephemeral=True)

class ColorView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ColorDropdown())

@bot.tree.command(name="setup_colors", description="Send the superior profile color selection panel")
@app_commands.checks.has_permissions(manage_roles=True)
async def setup_colors(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🎨 SERVER PROFILE COLORS",
        description="Welcome! Customize your username color in this server by selecting a vibe from the dropdown menu below.",
        color=discord.Color.from_rgb(255, 182, 193)
    )
    embed.set_footer(text="Dhawal Custom Management System")
    await interaction.response.send_message(embed=embed, view=ColorView())

# Start Flask server background thread, then start bot
keep_alive()
import os

# Puraane token waali line hatao, aur ye likho:
token = os.environ.get('DISCORD_BOT_TOKEN')
bot.run(token)