import os
import discord
from discord.ext import commands, tasks
from discord import app_commands
from flask import Flask
import threading
import datetime
import json
import pytz  
import asyncio
import time

# ==============================================================================
# 1. CORE CONFIGURATION & INTENTS SECURITY
# ==============================================================================
intents = discord.Intents.default()
intents.members = True  
intents.message_content = True
intents.presences = True

bot = commands.Bot(command_prefix="!", intents=intents)

WELCOME_CHANNEL_ID = 876543210987654321  

# Exact 32 custom colors registry matrix mapped properly split into 2 drops
COLOR_ROLES_1 = {
    "Crimson": "Crimson", "Hot pink": "Hot pink", "Magenta": "Magenta",
    "Yellow": "Yellow", "Chocolate": "Chocolate", "Aqua": "Aqua",
    "Spring green": "Spring green", "Silver": "Silver", "Red": "Red",
    "Blue": "Blue", "burgundy": "burgundy", "off white": "off white",
    "Laal Mirch": "Laal Mirch", "regular": "regular", "bubblegum": "bubblegum",
    "black": "black", "CB yellow": "CB yellow", "Volcanic Orange": "Volcanic Orange",
    "Nado Grey": "Nado Grey", "Mettalic Blue": "Mettalic Blue"
}

COLOR_ROLES_2 = {
    "Mettalic Bright...": "Mettalic Bright...", "Metallic Bronze": "Metallic Bronze",
    "Metallic Choco ...": "Metallic Choco ...", "Metallic Beach ...": "Metallic Beach ...",
    "Military Green": "Military Green", "Metallic Vermil...": "Metallic Vermil...",
    "Matte Lime Gree.": "Matte Lime Gree.", "Minty Green": "Minty Green",
    "Sandy Beige": "Sandy Beige", "Sugar Pink": "Sugar Pink",
    "Deep Mauve": "Deep Mauve", "paperteeth": "paperteeth"
}

ALL_COLOR_NAMES = list(COLOR_ROLES_1.values()) + list(COLOR_ROLES_2.values())

# ==============================================================================
# 2. DATABASE ROUTINES, STATE STORAGE & IST TIME PRESETS
# ==============================================================================
SNIPE_FILE = "snipe_logs.json"
QUIZ_FILE = "quizzes.json"
WARN_FILE = "warns.json"
CONFIG_FILE = "server_configs.json"
AFK_FILE = "afk_data.json"

def get_ist_time():
    ist = pytz.timezone('Asia/Kolkata')
    return datetime.datetime.now(ist)

def load_json_data(filename):
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_json_data(data, filename):
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Database write error on storage cluster: {e}")

snipe_data = {}

def get_flexible_channel(guild, keywords):
    if isinstance(keywords, str):
        keywords = [keywords]
    for channel in guild.text_channels:
        if any(kw in channel.name.lower() for kw in keywords):
            return channel
    return None

# ==============================================================================
# 3. INTERACTIVE UI ELEMENTS & OVERLAPPING ROLES PROTECTION
# ==============================================================================
class ColorSelectMenu(discord.ui.Select):
    def __init__(self, placeholder, options_dict, custom_id):
        options = [
            discord.SelectOption(label=label, value=role_name, emoji="🎨")
            for label, role_name in options_dict.items()
        ]
        super().__init__(placeholder=placeholder, min_values=1, max_values=1, options=options, custom_id=custom_id)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        member = interaction.user
        selected_color = self.values[0]

        roles_to_remove = [role for role in member.roles if role.name in ALL_COLOR_NAMES and role.name != selected_color]
        if roles_to_remove:
            try:
                await member.remove_roles(*roles_to_remove)
            except discord.Forbidden:
                await interaction.followup.send("❌ Discord Hierarchy limits: Put Bot's role above all color roles!", ephemeral=True)
                return

        target_role = discord.utils.get(guild.roles, name=selected_color)
        if target_role:
            try:
                if target_role in member.roles:
                    await member.remove_roles(target_role)
                    await interaction.followup.send(f"🎨 Removed your **{selected_color}** color configuration.", ephemeral=True)
                else:
                    await member.add_roles(target_role)
                    await interaction.followup.send(f"🎨 Success! Activated custom color shade **{selected_color}**.", ephemeral=True)
            except discord.Forbidden:
                await interaction.followup.send("❌ Role addition failed. Verify internal permission flags.", ephemeral=True)
        else:
            await interaction.followup.send(f"❌ Error: Visual role '{selected_color}' missing from Server configuration maps.", ephemeral=True)

class ColorView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ColorSelectMenu("Pick Color (Part 1: 1-20)...", COLOR_ROLES_1, "general:color_select_1"))
        self.add_item(ColorSelectMenu("Pick Color (Part 2: 21-32)...", COLOR_ROLES_2, "general:color_select_2"))

# ==============================================================================
# 4. GAMING INTERFACE & TIMED MULTIPLAYER ENGINE COMPONENTS
# ==============================================================================
class MultiQuizView(discord.ui.View):
    def __init__(self, options, correct_answer, scoreboard):
        super().__init__(timeout=15.0)
        self.options = options
        self.correct_answer = correct_answer
        self.scoreboard = scoreboard
        self.start_time = time.time()
        self.answered_users = set()

        prefixes = ["A", "B", "C", "D"]
        for i, option in enumerate(options):
            if i >= 4: break
            self.add_item(MultiQuizButton(label=f"{prefixes[i]}. {option}", value=option))

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        self.stop()

class MultiQuizButton(discord.ui.Button):
    def __init__(self, label, value):
        super().__init__(label=label, style=discord.ButtonStyle.secondary)
        self.value = value

    async def callback(self, interaction: discord.Interaction):
        view: MultiQuizView = self.view
        user = interaction.user
        user_id = str(user.id)

        if user_id in view.answered_users:
            await interaction.response.send_message("❌ View Attempt Lock: You can only input one answer per instance!", ephemeral=True)
            return

        view.answered_users.add(user_id)
        time_taken = time.time() - view.start_time

        if self.value == view.correct_answer:
            points_earned = max(20, int(100 - (time_taken * 5.33)))
            if user_id not in view.scoreboard:
                view.scoreboard[user_id] = {"name": user.name, "points": 0}
            view.scoreboard[user_id]["points"] += points_earned
            await interaction.response.send_message(f"✅ **Correct!** Speed matrix multiplier applied. Received **+{points_earned} Points**! ⚡", ephemeral=True)
        else:
            await interaction.response.send_message("❌ **Wrong Choice!** 0 points recorded for this frame.", ephemeral=True)

# ==============================================================================
# 5. DICTIONARIES, STRING CONSTANTS & QUOTE CACHE
# ==============================================================================
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

# ==============================================================================
# 6. EVENT DECORATORS & INTERCEPTORS (WELCOME, SNIPE, AND AFK PROCESSING)
# ==============================================================================
@bot.event
async def on_ready():
    print(f'🤖 {bot.user.name} Master Routing Cluster Bootstrapped successfully!')
    bot.add_view(ColorView())
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="Abhi9av 👑"))
    
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash commands into the system cache mapping.")
    except Exception as e:
        print(f"Global layout initialization tree mismatch error: {e}")

@bot.event
async def on_member_join(member: discord.Member):
    guild = member.guild
    
    # Priority check for general channels first, then falls back to welcome
    channel = get_flexible_channel(guild, ["general", "general-chat", "chat"]) or bot.get_channel(WELCOME_CHANNEL_ID) or get_flexible_channel(guild, "welcome")
    
    if channel:
        total_members = len(guild.members)
        
        # Suffix handling logic for member count
        if total_members % 10 == 1 and total_members % 100 != 11: suffix = "st"
        elif total_members % 10 == 2 and total_members % 100 != 12: suffix = "nd"
        elif total_members % 10 == 3 and total_members % 100 != 13: suffix = "rd"
        else: suffix = "th"

        # Dynamic Emoji Fetch for :Aquasmile:
        aquasmile_emoji = discord.utils.get(guild.emojis, name="Aquasmile")
        emoji_str = str(aquasmile_emoji) if aquasmile_emoji else "😊"
        
        # Dynamic Mention Resolution for Channels and Roles
        rules_channel = get_flexible_channel(guild, "rules")
        rules_mention = rules_channel.mention if rules_channel else "#rules"
        
        staff_role = discord.utils.get(guild.roles, name="Staff")
        staff_mention = staff_role.mention if staff_role else "@Staff"
        
        # Outer text includes user mention AND staff role tag
        outer_content_text = f"Welcome to Kuch Bhi Family 🤗 {member.mention} {staff_mention}"
        
        # Embed description layout (Removed the Ping Staff line completely as requested!)
        clean_welcome_text = (
            f"Drop a hello {emoji_str}\n"
            f"Check out {rules_mention}\n"
            f"Have fun!\n\n"
            f"**You are our {total_members}{suffix} member!**"
        )
        
        embed = discord.Embed(
            description=clean_welcome_text,
            color=discord.Color.from_rgb(255, 182, 193)
        )
        embed.set_author(name=member.name, icon_url=member.display_avatar.url)
        
        if os.path.exists("welcome.webp"):
            file = discord.File("welcome.webp", filename="welcome.webp")
            embed.set_thumbnail(url="attachment://welcome.webp")
            await channel.send(content=outer_content_text, file=file, embed=embed)
        else:
            await channel.send(content=outer_content_text, embed=embed)
        return

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild: return

    afk_db = load_json_data(AFK_FILE)
    author_id = str(message.author.id)
    guild_id = str(message.guild.id)

    # 1. Check if the sender was AFK -> Remove AFK status
    if guild_id in afk_db and author_id in afk_db[guild_id]:
        # Reset nickname back if changed
        original_name = afk_db[guild_id][author_id].get("original_name", message.author.display_name)
        afk_db[guild_id].pop(author_id)
        save_json_data(afk_db, AFK_FILE)
        
        try:
            await message.author.edit(nick=original_name)
        except discord.Forbidden:
            pass # Ignore if bot lacks hierarchy permissions to edit owner/admin nickname

        await message.channel.send(f"wb {message.author.mention}, maine aapka AFK status hata diya hai! 👋", delete_after=5)

    # 2. Check if message mentions anyone who is currently AFK
    if message.mentions:
        for mentioned_user in message.mentions:
            m_id = str(mentioned_user.id)
            if guild_id in afk_db and m_id in afk_db[guild_id]:
                reason = afk_db[guild_id][m_id]["reason"]
                afk_time = afk_db[guild_id][m_id]["time"]
                
                # Calculate duration format
                elapsed = int(time.time() - afk_time)
                if elapsed < 60: duration_str = f"{elapsed}s ago"
                elif elapsed < 3600: duration_str = f"{elapsed // 60}m ago"
                else: duration_str = f"{elapsed // 3600}h ago"

                await message.channel.send(
                    f"💤 {mentioned_user.name} abhi AFK hain: **{reason}** ({duration_str})",
                    reference=message
                )

    await bot.process_commands(message)

@bot.event
async def on_message_delete(message):
    if message.author.bot or not message.guild: return
    channel_id = str(message.channel.id)
    guild_id = str(message.guild.id)
    
    history_db = load_json_data(SNIPE_FILE)
    msg_id = str(message.id)
    was_edited = msg_id in history_db and history_db[msg_id].get("guild_id") == guild_id
    
    edit_note = ""
    if was_edited:
        edit_note = f"\n*(⚠️ Note: Message was updated prior to deletion. State captured: \"{history_db[msg_id]['before']}\")*"

    snipe_data[channel_id] = {
        "content": message.content if message.content else "[Empty Layer or File Stream Embedded]",
        "author": message.author.name,
        "avatar": message.author.display_avatar.url,
        "timestamp": get_ist_time().strftime("%I:%M:%S %p"),
        "extra_info": edit_note
    }

@bot.event
async def on_message_edit(before, after):
    if before.author.bot or before.content == after.content or not before.guild: return
    guild_id = str(before.guild.id)
    history_db = load_json_data(SNIPE_FILE)
    history_db[str(before.id)] = {
        "guild_id": guild_id,
        "author": before.author.name,
        "author_id": str(before.author.id),
        "before": before.content,
        "after": after.content,
        "timestamp": get_ist_time().strftime("%Y-%m-%d %I:%M %p")
    }
    if len(history_db) > 100:
        history_db.pop(list(history_db.keys())[0])
    save_json_data(history_db, SNIPE_FILE)

# ==============================================================================
# 7. SLASH COMMAND CORE SET: AFK & SERVER CUSTOM CHANNELS
# ==============================================================================
@bot.tree.command(name="afk", description="Set your profile status to Away From Keyboard with a custom reason.")
async def afk(interaction: discord.Interaction, reason: str = "Working / Afk"):
    afk_db = load_json_data(AFK_FILE)
    user_id = str(interaction.user.id)
    guild_id = str(interaction.guild.id)

    if guild_id not in afk_db:
        afk_db[guild_id] = {}

    current_display_name = interaction.user.display_name
    afk_db[guild_id][user_id] = {
        "reason": reason,
        "time": time.time(),
        "original_name": current_display_name
    }
    save_json_data(afk_db, AFK_FILE)

    # Change nickname to show [AFK] prefix cleanly
    try:
        new_nick = f"[AFK] {current_display_name}"[:32] # Discord limit is 32 chars
        await interaction.user.edit(nick=new_nick)
    except discord.Forbidden:
        pass

    await interaction.response.send_message(f"💤 {interaction.user.mention}, aap ab AFK hain: **{reason}**")

@bot.tree.command(name="color-list", description="Uploads the structural custom colors identity preview sheet template illustration.")
async def color_list(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Admin Access Denied: You need the Administrator permission flag array to invoke this panel framework.", ephemeral=True)
        return
        
    target_file = "color_list.webp"
    if not os.path.exists(target_file):
        await interaction.response.send_message("❌ Media Reference Failure: Local asset file designated `color_list.webp` not found in root storage matrix.", ephemeral=True)
        return
        
    await interaction.response.defer()
    file = discord.File(target_file, filename="color_list.webp")
    embed = discord.Embed(
        title="🎨 Kuch Bhi - Colors Ledger Selection Guide",
        description="Review the reference identity mapping chart below to preview visual configuration values.",
        color=discord.Color.from_rgb(47, 49, 54)
    )
    embed.set_image(url="attachment://color_list.webp")
    await interaction.followup.send(file=file, embed=embed)

@bot.tree.command(name="setup-colors", description="Custom color display menu dropdown setup engine panel.")
async def setup_colors(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Admin Access Denied: You need the Administrator permission flag array to invoke this panel framework.", ephemeral=True)
        return
        
    embed = discord.Embed(
        title="🌈 Custom Color Picker Panel",
        description="Select your desired identity color role setup using the multi-dropdown matrix arrays below.\n\nChoose any tone to map it instantly!",
        color=discord.Color.blurple()
    )
    await interaction.response.send_message(embed=embed, view=ColorView())

@bot.tree.command(name="snipe", description="Retrieve the last deleted message string from the runtime cache wrapper.")
async def snipe(interaction: discord.Interaction):
    channel_id = str(interaction.channel.id)
    if channel_id not in snipe_data:
        await interaction.response.send_message("❌ There are no recent text string deletions found in this tracking loop scope.", ephemeral=True)
        return
    data = snipe_data[channel_id]
    embed = discord.Embed(description=f"{data['content']}{data['extra_info']}", color=discord.Color.red())
    embed.set_author(name=f"Deleted by: {data['author']}", icon_url=data['avatar'])
    embed.set_footer(text=f"Time: {data['timestamp']} (IST Zone Forced)")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="editlogs", description="Check historical updates and original message text prior to edit modifications.")
async def editlogs(interaction: discord.Interaction, member: discord.Member):
    history_db = load_json_data(SNIPE_FILE)
    guild_id = str(interaction.guild.id)
    target_user_id = str(member.id)
    
    found_log = None
    for msg_id in reversed(list(history_db.keys())):
        log = history_db[msg_id]
        if log.get("guild_id") == guild_id and log.get("author_id") == target_user_id:
            found_log = log
            break
            
    if not found_log:
        await interaction.response.send_message(f"✅ Zero trace adjustments: No edited frames found for {member.name} in state database.", ephemeral=True)
        return
        
    embed = discord.Embed(title=f"📝 Message Edit Log Asset: {member.name}", color=discord.Color.blue())
    embed.add_field(name="⏪ Original Form String", value=f"```\n{found_log['before']}\n```", inline=False)
    embed.add_field(name="⏩ Modified Target State", value=f"```\n{found_log['after']}\n```", inline=False)
    embed.set_footer(text=f"Timestamp: {found_log['timestamp']} (IST Matrix)")
    await interaction.response.send_message(embed=embed)

# ==============================================================================
# 8. SLASH COMMAND CORE SET: MODERATION & USER PROTECTION COMMANDS
# ==============================================================================
@bot.tree.command(name="warn", description="Issue a formal backend system warning to a server member.")
@app_commands.checks.has_permissions(manage_messages=True)
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str):
    warns_db = load_json_data(WARN_FILE)
    m_id = str(member.id)
    g_id = str(interaction.guild.id)
    
    if g_id not in warns_db: warns_db[g_id] = {}
    if m_id not in warns_db[g_id]: warns_db[g_id][m_id] = []
    
    warn_payload = {
        "warn_id": len(warns_db[g_id][m_id]) + 1,
        "moderator": interaction.user.name,
        "reason": reason,
        "timestamp": get_ist_time().strftime("%Y-%m-%d %I:%M %p")
    }
    warns_db[g_id][m_id].append(warn_payload)
    save_json_data(warns_db, WARN_FILE)
    
    embed = discord.Embed(title="⚠️ Member Warning Registered", color=discord.Color.orange())
    embed.add_field(name="User Info", value=member.mention, inline=True)
    embed.add_field(name="Total Violations", value=str(len(warns_db[g_id][m_id])), inline=True)
    embed.add_field(name="Reason Specification", value=reason, inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="warns", description="View warning historical data sheets for an active entity profile.")
async def views_warns(interaction: discord.Interaction, member: discord.Member):
    warns_db = load_json_data(WARN_FILE)
    m_id = str(member.id)
    g_id = str(interaction.guild.id)
    
    if g_id not in warns_db or m_id not in warns_db[g_id] or not warns_db[g_id][m_id]:
        await interaction.response.send_message(f"✅ Clean Slate: {member.name} contains zero moderation flags on this registry.", ephemeral=True)
        return
        
    embed = discord.Embed(title=f"📋 Enforcement Violation Log: {member.name}", color=discord.Color.yellow())
    for item in warns_db[g_id][m_id]:
        embed.add_field(
            name=f"Case ID: #{item['warn_id']} | Date: {item['timestamp']}",
            value=f"**Reason:** {item['reason']}\n**Issued By:** {item['moderator']}",
            inline=False
        )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="clear-warns", description="Purge administrative infraction registries completely.")
@app_commands.checks.has_permissions(administrator=True)
async def clear_warns(interaction: discord.Interaction, member: discord.Member):
    warns_db = load_json_data(WARN_FILE)
    m_id = str(member.id)
    g_id = str(interaction.guild.id)
    
    if g_id in warns_db and m_id in warns_db[g_id]:
        warns_db[g_id].pop(m_id)
        save_json_data(warns_db, WARN_FILE)
    await interaction.response.send_message(f"🗑️ System cleanup: Warnings ledger cleared for {member.mention}.")

@bot.tree.command(name="mute", description="Timeout an operational profile user across chat bands.")
@app_commands.checks.has_permissions(moderate_members=True)
async def mute(interaction: discord.Interaction, member: discord.Member, minutes: int, reason: str = "Unspecified"):
    duration = datetime.timedelta(minutes=minutes)
    try:
        await member.timeout(duration, reason=reason)
        embed = discord.Embed(title="🤫 Member Isolated (Timeout Applied)", color=discord.Color.dark_gray())
        embed.add_field(name="Target User", value=member.mention, inline=True)
        embed.add_field(name="Duration", value=f"{minutes} Minutes", inline=True)
        embed.add_field(name="Reasoning context", value=reason, inline=False)
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        await interaction.response.send_message(f"❌ Operation execution halted: `{str(e)}`", ephemeral=True)

@bot.tree.command(name="unmute", description="Revoke communication isolation timeout rules early.")
@app_commands.checks.has_permissions(moderate_members=True)
async def unmute(interaction: discord.Interaction, member: discord.Member):
    try:
        await member.timeout(None)
        await interaction.response.send_message(f"🔊 Communication routing restored for profile user {member.mention}.")
    except Exception as e:
        await interaction.response.send_message(f"❌ Execution failure: `{str(e)}`", ephemeral=True)

@bot.tree.command(name="kick", description="Eject a problematic target user from server access.")
@app_commands.checks.has_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "Unspecified"):
    try:
        await member.kick(reason=reason)
        await interaction.response.send_message(f"👢 Kicked {member.name} successfully. Reason code: `{reason}`")
    except Exception as e:
        await interaction.response.send_message(f"❌ Command denied execution path: `{str(e)}`", ephemeral=True)

@bot.tree.command(name="ban", description="Blacklist a user profile from the gateway node routing structures.")
@app_commands.checks.has_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "Unspecified"):
    try:
        await member.ban(reason=reason)
        await interaction.response.send_message(f"🔨 Banned user identity hash {member.name} cleanly. Reason: `{reason}`")
    except Exception as e:
        await interaction.response.send_message(f"❌ Execution pipeline blocked: `{str(e)}`", ephemeral=True)

@bot.tree.command(name="purge", description="Bulk clear recent text traces from memory frames.")
@app_commands.checks.has_permissions(manage_messages=True)
async def purge(interaction: discord.Interaction, count: int):
    if count < 1:
        await interaction.response.send_message("❌ Parameter constraint failed. Count integer value must be >= 1.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=count)
    await interaction.followup.send(f"🗑️ Bulk cleanup sweep over. Extinguished `{len(deleted)}` old trace packages.")

# ==============================================================================
# 9. SLASH COMMAND CORE SET: INFORMATIONAL SYSTEMS & METRICS 
# ==============================================================================
@bot.tree.command(name="userinfo", description="Expose targeted registration signatures and identity status.")
async def userinfo(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    roles_str = ", ".join([r.mention for r in member.roles[1:15]]) or "No custom roles structural overrides found."
    embed = discord.Embed(title=f"Identity Profile: {member.name}", color=member.color)
    embed.add_field(name="Network Identity Handle", value=f"`{member.id}`", inline=True)
    embed.add_field(name="Account Spawned", value=member.created_at.strftime("%Y-%m-%d"), inline=True)
    embed.add_field(name="Gateway Gateway Node Entry", value=member.joined_at.strftime("%Y-%m-%d"), inline=True)
    embed.add_field(name="Assigned Security Arrays", value=roles_str, inline=False)
    embed.set_thumbnail(url=member.display_avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="serverinfo", description="Expose statistical architecture tracking telemetry data.")
async def serverinfo(interaction: discord.Interaction):
    g = interaction.guild
    embed = discord.Embed(title=f"Architecture Report: {g.name}", color=discord.Color.blue())
    embed.add_field(name="Structural ID", value=f"`{g.id}`", inline=True)
    embed.add_field(name="Primary Owner Node", value=g.owner.mention if g.owner else "Null Reference", inline=True)
    embed.add_field(name="Population Registry", value=f"Total: `{g.member_count}`", inline=True)
    embed.add_field(name="Channel Subsections", value=f"Text: `{len(g.text_channels)}` | Voice: `{len(g.voice_channels)}`", inline=False)
    if g.icon: embed.set_thumbnail(url=g.icon.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="avatar", description="Extract the graphic assets source link for an active profile avatar.")
async def avatar(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    embed = discord.Embed(title=f"Graphic Source: {member.name}'s Avatar")
    embed.set_image(url=member.display_avatar.url)
    await interaction.response.send_message(embed=embed)

# ==============================================================================
# 10. SLASH COMMAND CORE SET: GAME ARENA & QUIZ STORAGE DRIVERS
# ==============================================================================
@bot.tree.command(name="create-quiz", description="Initialize a new empty quiz group (Admin Only)")
@app_commands.checks.has_permissions(manage_messages=True)
async def create_quiz(interaction: discord.Interaction, name: str):
    quiz_db = load_json_data(QUIZ_FILE)
    quiz_key = name.lower().replace(" ", "_")
    if quiz_key in quiz_db:
        await interaction.response.send_message(f"❌ Key Constraint Error: Quiz identifier `{name}` exists.", ephemeral=True)
        return
    quiz_db[quiz_key] = {
        "title": name,
        "creator": interaction.user.name,
        "created_at": get_ist_time().strftime("%Y-%m-%d %I:%M %p"),
        "questions": []
    }
    save_json_data(quiz_db, QUIZ_FILE)
    await interaction.response.send_message(f"✅ **Database Index Generated!** Group: `{name}`. Add components with `/add-question`.")

@bot.tree.command(name="add-question", description="Manually add a question, options, and correct answer (Admin Only)")
@app_commands.checks.has_permissions(manage_messages=True)
async def add_question(interaction: discord.Interaction, quiz_name: str, question: str, options: str, correct_answer: str):
    quiz_db = load_json_data(QUIZ_FILE)
    quiz_key = quiz_name.lower().replace(" ", "_")
    if quiz_key not in quiz_db:
        await interaction.response.send_message(f"❌ Data Query Error: Target Group `{quiz_name}` missing.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=False)
    try:
        parsed_options = [opt.strip() for opt in options.split(",")]
        correct_answer_clean = correct_answer.strip()
        if correct_answer_clean not in parsed_options:
            await interaction.followup.send(f"❌ Matrix Validation Intercept: Correct choice mapping must exist inside options pool arrays!")
            return
        if len(parsed_options) < 2:
            await interaction.followup.send("❌ Error: Minimum structural option boundaries require length value >= 2")
            return
        parsed_question_entry = {
            "question": question,
            "options": parsed_options,
            "correct": correct_answer_clean
        }
        quiz_db[quiz_key]["questions"].append(parsed_question_entry)
        save_json_data(quiz_db, QUIZ_FILE)
        
        embed = discord.Embed(title=f"📝 Question Structured & Saved!", color=discord.Color.green())
        embed.add_field(name="Target Index Group", value=quiz_db[quiz_key]["title"], inline=True)
        embed.add_field(name="Question String", value=question, inline=False)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"❌ Exception safely isolated inside parse loop execution: `{str(e)}`")

@bot.tree.command(name="remove-question", description="Remove a specific question from a quiz using its number (Admin Only)")
@app_commands.checks.has_permissions(manage_messages=True)
async def remove_question(interaction: discord.Interaction, quiz_name: str, question_number: int):
    quiz_db = load_json_data(QUIZ_FILE)
    quiz_key = quiz_name.lower().replace(" ", "_")
    if quiz_key not in quiz_db:
        await interaction.response.send_message(f"❌ Target context block tracking failure.", ephemeral=True)
        return
    q_list = quiz_db[quiz_key]["questions"]
    if question_number < 1 or question_number > len(q_list):
        await interaction.response.send_message("❌ Range evaluate limits matched exception flag out bounds.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=False)
    removed = q_list.pop(question_number - 1)
    quiz_db[quiz_key]["questions"] = q_list
    save_json_data(quiz_db, QUIZ_FILE)
    await interaction.followup.send(f"🗑️ Purged question array index entry safely: \"{removed['question']}\"")

@bot.tree.command(name="start-quiz", description="Launch the Multiplayer Arena with live speed leaderboards (Admin Only)")
@app_commands.checks.has_permissions(manage_messages=True)
async def start_quiz(interaction: discord.Interaction, quiz_name: str):
    quiz_db = load_json_data(QUIZ_FILE)
    quiz_key = quiz_name.lower().replace(" ", "_")
    if quiz_key not in quiz_db or not quiz_db[quiz_key]["questions"]:
        await interaction.response.send_message("❌ Matchmaker core blocked: Database empty or index configuration corrupted.", ephemeral=True)
        return
    await interaction.response.send_message(f"🚀 **MULTIPLAYER MATCHMAKING CORES ACTIVE!**\nArena Session: `{quiz_db[quiz_key]['title']}`\nTimer settings configured to **15 Seconds** per loop. Syncing thread blocks...", ephemeral=False)
    channel = interaction.channel
    q_list = quiz_db[quiz_key]["questions"]
    session_scoreboard = {}

    for idx, q_item in enumerate(q_list, 1):
        embed = discord.Embed(title=f"❓ Phase {idx} of {len(q_list)}", description=f"**{q_item['question']}**", color=discord.Color.blue())
        
        item_target = q_item["correct"]
        view = MultiQuizView(options=q_item["options"], correct_answer=item_target, scoreboard=session_scoreboard)
        quiz_msg = await channel.send(embed=embed, view=view)
        
        await asyncio.sleep(15.0)
        view.stop()
        
        embed.color = discord.Color.gold()
        embed.add_field(name="🎯 Correct Solution Resolved", value=f"👉 **{item_target}**", inline=False)
        await quiz_msg.edit(embed=embed, view=None)

        if session_scoreboard:
            sorted_scores = sorted(session_scoreboard.items(), key=lambda x: x[1]["points"], reverse=True)[:5]
            lb_text = "".join([f"🏅 **#{r}** {d['name']} ➔ `{d['points']} pts`\n" for r, (uid, d) in enumerate(sorted_scores, 1)])
            await channel.send(embed=discord.Embed(title=f"🏁 Session Leaderboard Framework State (Round {idx})", description=lb_text, color=discord.Color.purple()))
        await asyncio.sleep(4.0)
    await channel.send("🏆 **COMPILER LEAGUE ARENA TERMINATED.** Session state cleared smoothly from execution heap.")

# ==============================================================================
# 11. RUNTIME KEEP-ALIVE NET NET ENGINE (WEB-FACING PROXY)
# ==============================================================================
app = Flask('')

@app.route('/')
def home():
    return "Dhawal Master Core Architecture Operational 24/7!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = threading.Thread(target=run_web_server)
    t.start()

# ==============================================================================
# 12. BOOT ENGINE INSTANTIATOR
# ==============================================================================
if __name__ == "__main__":
    keep_alive()
    TOKEN = os.getenv("DISCORD_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
    bot.run(TOKEN)