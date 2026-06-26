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
# 1. BOT INTENTS, INITIALIZATION & CORE BRANDING
# ==============================================================================
intents = discord.Intents.default()
intents.members = True  
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ==============================================================================
# 2. SERVER SPECIFIC HARDCODED CONFIGURATION VALUES
# ==============================================================================
KUCH_BHI_SERVER_ID = 123456789012345678  # 👈 Apna actual "Kuch Bhi" server ID yahan daalna
WELCOME_CHANNEL_ID = 876543210987654321  # 👈 Apna actual welcome channel ID yahan daalna

# Image image_b96521.png ke 32 exact custom colors mapping (Split due to Discord UI limits)
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
# 3. HELPER FUNCTIONS, DATABASES AND TIMEZONE SYSTEM
# ==============================================================================
def get_ist_time():
    ist = pytz.timezone('Asia/Kolkata')
    return datetime.datetime.now(ist)

SNIPE_FILE = "snipe_logs.json"
QUIZ_FILE = "quizzes.json"

def load_json_data(filename):
    if os.path.exists(filename):
        try:
            with open(filename, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_json_data(data, filename):
    try:
        with open(filename, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Error saving database JSON structure: {e}")

# High-speed operational cache for sniping module
snipe_data = {}

def get_flexible_channel(guild, keywords):
    if isinstance(keywords, str):
        keywords = [keywords]
    for channel in guild.text_channels:
        if any(kw in channel.name.lower() for kw in keywords):
            return channel
    return None

# ==============================================================================
# 4. DISCORD INTERACTION UI COMPONENTS (COLOR MENU & DROPDOWNS)
# ==============================================================================
class ColorSelectMenu(discord.ui.Select):
    def __init__(self, placeholder, options_dict, custom_id):
        options = [
            discord.SelectOption(label=label, value=role_name, emoji="🎨")
            for label, role_name in options_dict.items()
        ]
        super().__init__(placeholder=placeholder, min_values=1, max_values=1, options=options, custom_id=custom_id)

    async def callback(self, interaction: discord.Interaction):
        if interaction.guild_id != KUCH_BHI_SERVER_ID:
            await interaction.response.send_message("❌ This UI view element is locked to 'Kuch Bhi' server rules.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        member = interaction.user
        selected_color = self.values[0]

        # Purane active profile colors wipeout mechanism
        roles_to_remove = [role for role in member.roles if role.name in ALL_COLOR_NAMES and role.name != selected_color]
        if roles_to_remove:
            try:
                await member.remove_roles(*roles_to_remove)
            except discord.Forbidden:
                await interaction.followup.send("❌ Error removing old role. Check bot hierarchy permissions setup.", ephemeral=True)
                return

        target_role = discord.utils.get(guild.roles, name=selected_color)
        if target_role:
            try:
                if target_role in member.roles:
                    await member.remove_roles(target_role)
                    await interaction.followup.send(f"🎨 Removed your **{selected_color}** color role styling.", ephemeral=True)
                else:
                    await member.add_roles(target_role)
                    await interaction.followup.send(f"🎨 Success! Your color role has been updated to **{selected_color}**.", ephemeral=True)
            except discord.Forbidden:
                await interaction.followup.send("❌ Cannot assign role. Ensure bot role is physically above color roles in server settings!", ephemeral=True)
        else:
            await interaction.followup.send(f"❌ Role '{selected_color}' server settings mein nahi mila.", ephemeral=True)

class ColorView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # Persistent across restarts
        self.add_item(ColorSelectMenu("Pick Color (Part 1: 1-20)...", COLOR_ROLES_1, "kuchbhi:color_select_1"))
        self.add_item(ColorSelectMenu("Pick Color (Part 2: 21-32)...", COLOR_ROLES_2, "kuchbhi:color_select_2"))

# ==============================================================================
# 5. MULTIPLAYER QUIZ ENGINE COMPONENTS & UI
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
            await interaction.response.send_message("❌ Aap is question par apna attempt le chuke hain!", ephemeral=True)
            return

        view.answered_users.add(user_id)
        time_taken = time.time() - view.start_time

        if self.value == view.correct_answer:
            points_earned = max(20, int(100 - (time_taken * 5.33))) 

            if user_id not in view.scoreboard:
                view.scoreboard[user_id] = {"name": user.name, "points": 0}
            
            view.scoreboard[user_id]["points"] += points_earned
            await interaction.response.send_message(f"✅ **Sahi Jawab!** Aapne **{time_taken:.2f}s** mein answer kiya aur paaye **+{points_earned} Points**! ⚡", ephemeral=True)
        else:
            await interaction.response.send_message("❌ **Galat Jawab!** Is question mein aapko 0 points mile.", ephemeral=True)

# ==============================================================================
# 6. MOTIVATIONAL QUOTES ARCHIVE STRUCTURE
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
# 7. DISCORD BACKEND LOOPS & MOTIVATIONAL TASKS
# ==============================================================================
@tasks.loop(hours=2.0)
async def bump_reminder_loop():
    await bot.wait_until_ready()
    for guild in bot.guilds:
        bump_channel = get_flexible_channel(guild, ["bump", "bot-commands", "general"])
        if bump_channel:
            staff_role = discord.utils.get(guild.roles, name="Staff")
            mention_text = staff_role.mention if staff_role else "@here"
            
            embed = discord.Embed(
                title="⏰ SERVER BUMP TIME! ⏰",
                description=(
                    f"Hey {mention_text}! **2 ghante poore ho chuke hain.**\n\n"
                    "Server ki growth ke liye please Disboard ya custom bumper use karke server ko bump karein!\n"
                    "👉 `/bump` type karke boom karein!"
                ),
                color=discord.Color.gold()
            )
            embed.set_footer(text="Automated Growth Management System")
            try:
                await bump_channel.send(content=mention_text, embed=embed)
            except Exception as e:
                print(f"Error sending bump reminder to guild {guild.name}: {e}")

# ==============================================================================
# 8. SYSTEM BROADCAST LISTENERS & AUTOMATION EVENTS
# ==============================================================================
@bot.event
async def on_ready():
    print(f'🤖 {bot.user.name} is ONLINE & CUSTOM PRODUCTION READY!')
    bot.add_view(ColorView()) 
    
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="Abhi9av 👑"))
    
    if not bump_reminder_loop.is_running():
        bump_reminder_loop.start()
        
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash commands globally.")
    except Exception as e:
        print(f"Error syncing globally on boot setup: {e}")

@bot.event
async def on_member_join(member: discord.Member):
    guild = member.guild
    
    if guild.id == KUCH_BHI_SERVER_ID:
        channel = bot.get_channel(WELCOME_CHANNEL_ID)
        if channel:
            embed = discord.Embed(
                title="👋 Welcome to Kuch Bhi!",
                description=f"Arey waah, {member.mention} server mein aa chuke hain! 🎉\n\nApna pasandida rang lene ke liye niche diye gaye panel se color select karein!",
                color=discord.Color.random()
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            await channel.send(content=member.mention, embed=embed)
        return

    roles_to_add = []
    lil_dawg_role = discord.utils.get(guild.roles, name="Lil Dawg")
    newbies_role = discord.utils.get(guild.roles, name="Newbies")
    
    if lil_dawg_role: roles_to_add.append(lil_dawg_role)
    if newbies_role: roles_to_add.append(newbies_role)
        
    if roles_to_add:
        try:
            await member.add_roles(*roles_to_add)
        except discord.Forbidden:
            print("❌ Permission Error: Bot role position invalid on hierarchy grid.")

    welcome_channel = get_flexible_channel(guild, "welcome")
    if welcome_channel:
        total_members = len(guild.members)
        quote_index = (total_members - 1) % len(QUOTES)
        selected_quote = QUOTES[quote_index]

        embed = discord.Embed(
            title=f"Welcome to the Server, {member.name}! 🎉",
            description=f"We are glad to have you here with us!\n\n✨ *{selected_quote}*",
            color=discord.Color.from_rgb(114, 137, 218)
        )
        
        color_channel = get_flexible_channel(guild, ["color", "colours"])
        if color_channel:
            embed.add_field(name="🎨 Get Roles", value=f"Head over to {color_channel.mention} to grab your custom colors!", inline=False)
            
        rules_channel = get_flexible_channel(guild, "rules")
        if rules_channel:
            embed.add_field(name="📜 Server Rules", value=f"Make sure to check out {rules_channel.mention} to keep the community clean.", inline=False)

        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Member #{total_members}")
        await welcome_channel.send(content=member.mention, embed=embed)

@bot.event
async def on_message_delete(message):
    if message.author.bot or not message.guild:
        return
        
    channel_id = str(message.channel.id)
    guild_id = str(message.guild.id)
    
    history_db = load_json_data(SNIPE_FILE)
    msg_id = str(message.id)
    was_edited = msg_id in history_db and history_db[msg_id].get("guild_id") == guild_id
    
    edit_note = ""
    if was_edited:
        edit_note = f"\n*(⚠️ Note: This message was edited before deletion. Original: \"{history_db[msg_id]['before']}\")*"

    snipe_data[channel_id] = {
        "content": message.content if message.content else "[No text or attachment contained]",
        "author": message.author.name,
        "avatar": message.author.display_avatar.url,
        "timestamp": get_ist_time().strftime("%I:%M:%S %p"),
        "extra_info": edit_note
    }

@bot.event
async def on_message_edit(before, after):
    if before.author.bot or before.content == after.content or not before.guild:
        return

    guild_id = str(before.guild.id)
    history_db = load_json_data(SNIPE_FILE)
    history_db[str(before.id)] = {
        "guild_id": guild_id,
        "author": before.author.name,
        "before": before.content,
        "after": after.content,
        "timestamp": get_ist_time().strftime("%Y-%m-%d %I:%M:%S %p")
    }
    
    if len(history_db) > 100:
        first_key = list(history_db.keys())[0]
        history_db.pop(first_key)
        
    save_json_data(history_db, SNIPE_FILE)

# ==============================================================================
# 9. UTILITY SLASH COMMANDS (BUMP & MANAGEMENT PANELS)
# ==============================================================================
@bot.tree.command(name="bump", description="Bump the server to boost rankings and visibility!")
async def bump(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🚀 SERVER BUMPED SUCCESSFULLY!",
        description=(
            f"Thank you {interaction.user.mention}! **{interaction.guild.name}** has been successfully bumped!\n\n"
            "📈 Visibility increased on listing boards. Agla auto-reminder **2 ghante** mein staff ko mil jayega."
        ),
        color=discord.Color.green()
    )
    embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
    embed.set_footer(text=f"Bumped by {interaction.user.name}")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="setup-colors", description="Kuch Bhi server ke liye custom color menu setup karein. (Admin Only)")
@app_commands.checks.has_permissions(administrator=True)
async def setup_colors(interaction: discord.Interaction):
    if interaction.guild_id != KUCH_BHI_SERVER_ID:
        await interaction.response.send_message("❌ Yeh command sirf 'Kuch Bhi' server mein valid hai.", ephemeral=True)
        return

    embed = discord.Embed(
        title="🌈 Kuch Bhi - Custom Color Picker",
        description="Niche diye gaye menus se apna manpasand custom color chunain! Ek baar mein ek hi color active rahega.",
        color=discord.Color.blurple()
    )
    await interaction.response.send_message("Panel send kiya jaa raha hai...", ephemeral=True)
    await interaction.channel.send(embed=embed, view=ColorView())

# ==============================================================================
# 10. QUIZ DATA CREATION & MANAGEMENT INTERFACE
# ==============================================================================
@bot.tree.command(name="create-quiz", description="Initialize a new empty quiz group (Admin Only)")
@app_commands.checks.has_permissions(manage_messages=True)
async def create_quiz(interaction: discord.Interaction, name: str):
    quiz_db = load_json_data(QUIZ_FILE)
    quiz_key = name.lower().replace(" ", "_")

    if quiz_key in quiz_db:
        await interaction.response.send_message(f"❌ **'{name}'** naam se quiz pehle se hi exist karti hai!", ephemeral=True)
        return

    quiz_db[quiz_key] = {
        "title": name,
        "creator": interaction.user.name,
        "created_at": get_ist_time().strftime("%Y-%m-%d %I:%M %p"),
        "questions": []
    }
    save_json_data(quiz_db, QUIZ_FILE)
    await interaction.response.send_message(f"✅ **Quiz Created Successfully!**\nGroup Name: `{name}`\nAb aap `/add-question` use karke isme manually savaal daal sakte hain!")

@bot.tree.command(name="add-question", description="Manually add a question, options, and correct answer (Admin Only)")
@app_commands.checks.has_permissions(manage_messages=True)
async def add_question(interaction: discord.Interaction, quiz_name: str, question: str, options: str, correct_answer: str):
    quiz_db = load_json_data(QUIZ_FILE)
    quiz_key = quiz_name.lower().replace(" ", "_")

    if quiz_key not in quiz_db:
        await interaction.response.send_message(f"❌ Quiz `{quiz_name}` nahi mili! Pehle `/create-quiz` chalao.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=False)
    try:
        parsed_options = [opt.strip() for opt in options.split(",")]
        correct_answer_clean = correct_answer.strip()

        if correct_answer_clean not in parsed_options:
            await interaction.followup.send(f"❌ **Error:** Correct answer ({correct_answer_clean}) options se match nahi ho raha!")
            return
        if len(parsed_options) < 2:
            await interaction.followup.send("❌ **Error:** Kam se kam 2 options dena zaroori hai!")
            return

        parsed_question_entry = {
            "question": question,
            "options": parsed_options,
            "correct": correct_answer_clean
        }
        quiz_db[quiz_key]["questions"].append(parsed_question_entry)
        save_json_data(quiz_db, QUIZ_FILE)

        embed = discord.Embed(title=f"📝 Question Added Manually!", color=discord.Color.green())
        embed.add_field(name="Quiz Group", value=quiz_db[quiz_key]["title"], inline=True)
        embed.add_field(name="Total Questions Now", value=str(len(quiz_db[quiz_key]["questions"])), inline=True)
        embed.add_field(name="💬 Question Statement", value=question, inline=False)
        
        options_preview = ""
        for idx, opt in enumerate(parsed_options, 1):
            marker = "🔹"
            if opt == correct_answer_clean: marker = "✅ (Correct)"
            options_preview += f"{idx}. {opt} {marker}\n"
            
        embed.add_field(name="📋 Options Entered", value=options_preview, inline=False)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"❌ Question add karne mein dikkat aayi: `{str(e)}`")

@bot.tree.command(name="remove-question", description="Remove a specific question from a quiz using its number (Admin Only)")
@app_commands.checks.has_permissions(manage_messages=True)
async def remove_question(interaction: discord.Interaction, quiz_name: str, question_number: int):
    quiz_db = load_json_data(QUIZ_FILE)
    quiz_key = quiz_name.lower().replace(" ", "_")

    if quiz_key not in quiz_db:
        await interaction.response.send_message(f"❌ Quiz `{quiz_name}` nahi mili!", ephemeral=True)
        return

    questions_list = quiz_db[quiz_key]["questions"]
    total_q = len(questions_list)

    if total_q == 0:
        await interaction.response.send_message(f"❌ `{quiz_name}` mein koi question bacha hi nahi hai!", ephemeral=True)
        return
    if question_number < 1 or question_number > total_q:
        await interaction.response.send_message(f"❌ Invalid question number! Total `{total_q}` questions hain.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=False)
    try:
        removed_q = questions_list.pop(question_number - 1)
        quiz_db[quiz_key]["questions"] = questions_list
        save_json_data(quiz_db, QUIZ_FILE)

        embed = discord.Embed(title="🗑️ Question Removed Successfully!", color=discord.Color.red())
        embed.add_field(name="Quiz Group", value=quiz_db[quiz_key]["title"], inline=True)
        embed.add_field(name="Removed Question #", value=str(question_number), inline=True)
        embed.add_field(name="Remaining Questions", value=str(len(questions_list)), inline=True)
        embed.add_field(name="💬 Removed Content", value=removed_q["question"], inline=False)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"❌ Question remove karne mein error aaya: `{str(e)}`")

# ==============================================================================
# 11. LIVE MULTIPLAYER QUIZ RUNTIME ENGINE COMMAND
# ==============================================================================
@bot.tree.command(name="start-quiz", description="Launch the Multiplayer Arena with live speed leaderboards (Admin Only)")
@app_commands.checks.has_permissions(manage_messages=True)
async def start_quiz(interaction: discord.Interaction, quiz_name: str):
    quiz_db = load_json_data(QUIZ_FILE)
    quiz_key = quiz_name.lower().replace(" ", "_")

    if quiz_key not in quiz_db or not quiz_db[quiz_key]["questions"]:
        await interaction.response.send_message(f"❌ Quiz `{quiz_name}` nahi mili ya usme koi questions nahi hain!", ephemeral=True)
        return

    await interaction.response.send_message(f"🚀 **MULTIPLAYER ARENA ACTIVE!**\nQuiz: `{quiz_db[quiz_key]['title']}`\n\n⚡ **Rules:** Har question ke liye sirf **15 Seconds** milenge. Ready ho jao crew!", ephemeral=False)
    channel = interaction.channel

    questions_list = quiz_db[quiz_key]["questions"]
    session_scoreboard = {}

    for idx, q_item in enumerate(questions_list, 1):
        q_text = q_item["question"]
        opts = q_item["options"]
        correct = q_item["correct"]

        embed = discord.Embed(
            title=f"❓ Question {idx} of {len(questions_list)}",
            description=f"**{q_text}**",
            color=discord.Color.blue()
        )
        embed.set_footer(text="Aapke paas sirf 15 seconds hain answer karne ke liye!")
        
        view = MultiQuizView(options=opts, correct_answer=correct, scoreboard=session_scoreboard)
        quiz_msg = await channel.send(embed=embed, view=view)
        
        await asyncio.sleep(15.0)
        view.stop()
        
        embed.color = discord.Color.gold()
        embed.add_field(name="🎯 Correct Answer Was", value=f"👉 **{correct}**", inline=False)
        await quiz_msg.edit(embed=embed, view=None)

        if session_scoreboard:
            sorted_scores = sorted(session_scoreboard.items(), key=lambda x: x[1]["points"], reverse=True)[:5]
            lb_text = ""
            for rank, (uid, u_data) in enumerate(sorted_scores, 1):
                lb_text += f"🏅 **#{rank}** {u_data['name']} ➔ `{u_data['points']} pts`\n"
            
            lb_embed = discord.Embed(title=f"🏁 Leaderboard Standings (Round {idx})", description=lb_text, color=discord.Color.purple())
            await channel.send(embed=lb_embed)
        
        await asyncio.sleep(4.0)

    await channel.send("🏆 **QUIZ ARENA OVER!** Shabaash sabhi participants ko!")

# ==============================================================================
# 12. WEB SERVER FOR 24/7 PRODUCTION KEEP ALIVE
# ==============================================================================
app = Flask('')

@app.route('/')
def home():
    return "Dhawal Bot Engine Operational 24/7!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = threading.Thread(target=run_web_server)
    t.start()

# ==============================================================================
# 13. EXECUTION BLOCK FOR COMPILER ENVIRONMENT
# ==============================================================================
if __name__ == "__main__":
    keep_alive()
    # Dynamic fetching from configuration block for safety
    TOKEN = os.getenv("DISCORD_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
    bot.run(TOKEN)