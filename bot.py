import os
import discord
from discord.ext import commands
from discord import app_commands
from flask import Flask
import threading
import datetime
import json
import pytz  
import google.generativeai as genai
import asyncio

# --- INITIAL SETUP & INTENTS ---
intents = discord.Intents.default()
intents.members = True  
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# --- GEMINI AI CONFIGURATION ---
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
else:
    print("⚠️ WARNING: GEMINI_API_KEY environment variable not found!")

# --- TIMEZONE HELPER (IST FORCE) ---
def get_ist_time():
    ist = pytz.timezone('Asia/Kolkata')
    return datetime.datetime.now(ist)

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

# --- DATABASES (LEVELS, SNIPE, & QUIZ STORAGE) ---
LEVELS_FILE = "levels.json"
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
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)

# Global runtime cache for fast sniping
snipe_data = {}

# --- HELPER: DYNAMIC CHANNEL KEYWORD MATCHING ---
def get_flexible_channel(guild, keywords):
    if isinstance(keywords, str):
        keywords = [keywords]
    for channel in guild.text_channels:
        if any(kw in channel.name.lower() for kw in keywords):
            return channel
    return None

# --- COLOR SELECTION DROPDOWN SYSTEM ---
class ColorDropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Red", description="Bold & Fierce", emoji="🔴"),
            discord.SelectOption(label="Blue", description="Chill & Calm", emoji="🔵"),
            discord.SelectOption(label="Green", description="Fresh & Creative", emoji="🟢"),
            discord.SelectOption(label="Yellow", description="Bright & Energetic", emoji="🟡"),
            discord.SelectOption(label="Orange", description="Wild & Vibrant", emoji="🟠"),
            discord.SelectOption(label="Purple", description="Royal & Mystery", emoji="🟣"),
            discord.SelectOption(label="Pink", description="Aesthetic & Cute", emoji="🌸")
        ]
        super().__init__(placeholder="Tap here to pick your profile color...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        member = interaction.user
        selected_color = self.values[0]

        color_role_names = ["Red", "Purple", "Green", "Pink", "Orange", "Yellow", "Blue"]
        existing_target_role = discord.utils.get(member.roles, name=selected_color)
        
        roles_to_remove = [discord.utils.get(guild.roles, name=r) for r in color_role_names if r != selected_color]
        roles_to_remove = [r for r in roles_to_remove if r in member.roles]
        if roles_to_remove:
            await member.remove_roles(*roles_to_remove)

        if existing_target_role:
            try:
                await member.remove_roles(existing_target_role)
                await interaction.followup.send(f"🎨 Removed your **{selected_color}** color role profile styling.", ephemeral=True)
            except discord.Forbidden:
                await interaction.followup.send("❌ Error removing role. Check permissions layout.", ephemeral=True)
        else:
            target_role = discord.utils.get(guild.roles, name=selected_color)
            if target_role:
                try:
                    await member.add_roles(target_role)
                    await interaction.followup.send(f"🎨 Success! Your color role has been updated to **{selected_color}**.", ephemeral=True)
                except discord.Forbidden:
                    await interaction.followup.send("❌ Cannot assign role. Ensure 'Dhawal' role is physically above the color roles in your server settings!", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ Role '{selected_color}' not found in the server setup.", ephemeral=True)

class ColorView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ColorDropdown())


# --- WAVE INTERACTION BUTTON CLASS ---
class WelcomeView(discord.ui.View):
    def __init__(self, target_member: discord.Member):
        super().__init__(timeout=None)
        self.target_member = target_member

    @discord.ui.button(label="Wave", style=discord.ButtonStyle.blurple, emoji="👋")
    async def wave_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        waving_sticker_id = 1512147790975865043 
        
        try:
            sticker = await interaction.guild.fetch_sticker(waving_sticker_id)
            await interaction.channel.send(f"{interaction.user.mention} waved to {self.target_member.mention}! 👋", stickers=[sticker])
        except Exception:
            await interaction.channel.send(f"{interaction.user.mention} waved to {self.target_member.mention}! 👋👋👋")


# --- INTERACTIVE QUIZ PLAY BUTTONS VIEW ---
class QuizPlayView(discord.ui.View):
    def __init__(self, options, correct_answer):
        super().__init__(timeout=30.0)  # 30 Seconds overall timer for answering
        self.options = options
        self.correct_answer = correct_answer
        self.answered_correctly_by = None
        
        # Add a custom button for each choice dynamically
        prefixes = ["A", "B", "C", "D"]
        for i, option in enumerate(options):
            if i >= 4: break
            self.add_item(QuizButton(label=f"{prefixes[i]}. {option}", value=option, custom_id=f"quiz_opt_{i}"))

    async def on_timeout(self):
        # Disable all items when the session closes
        for item in self.children:
            item.disabled = True
        self.stop()


class QuizButton(discord.ui.Button):
    def __init__(self, label, value, custom_id):
        super().__init__(label=label, style=discord.ButtonStyle.secondary, custom_id=custom_id)
        self.value = value

    async def callback(self, interaction: discord.Interaction):
        view: QuizPlayView = self.view
        
        # Check if the clicked button matches the accurate database entry
        if self.value == view.correct_answer:
            view.answered_correctly_by = interaction.user
            self.style = discord.ButtonStyle.success
            
            # Disable everything since round is finished
            for child in view.children:
                child.disabled = True
                
            view.stop()
            
            # Award +15 XP instantly inside current session database
            level_db = load_json_data(LEVELS_FILE)
            u_id = str(interaction.user.id)
            if u_id not in level_db:
                level_db[u_id] = {"xp": 0, "level": 0}
            level_db[u_id]["xp"] += 15
            save_json_data(level_db, LEVELS_FILE)
            
            await interaction.response.edit_message(view=view)
            await interaction.followup.send(f"🎉 **SAHI JAWAAB!** {interaction.user.mention} ne sabse pehle correct option chunna! Aur unhe milte hain **+15 XP**! 🏆")
        else:
            # Ephemeral response so other server mates don't get distracted by wrong guesses
            await interaction.response.send_message("❌ Galat jawaab! Dobara koshish karo ya kisi aur ko dimaag lagane do!", ephemeral=True)


# --- EVENTS & LOGGING LISTENERS ---
@bot.event
async def on_ready():
    print(f'🤖 {bot.user.name} is ONLINE & AI QUIZ MODULE READY!')
    bot.add_view(ColorView())
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s) globally")
    except Exception as e:
        print(f"Error syncing on startup: {e}")

@bot.event
async def on_member_join(member: discord.Member):
    guild = member.guild
    
    roles_to_add = []
    lil_dawg_role = discord.utils.get(guild.roles, name="Lil Dawg")
    newbies_role = discord.utils.get(guild.roles, name="Newbies")
    
    if lil_dawg_role:
        roles_to_add.append(lil_dawg_role)
    if newbies_role:
        roles_to_add.append(newbies_role)
        
    if roles_to_add:
        try:
            await member.add_roles(*roles_to_add)
        except discord.Forbidden:
            print(f"❌ Failed to assign join roles: Check bot hierarchy!")

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

    general_channel = get_flexible_channel(guild, "general")
    if general_channel:
        view = WelcomeView(target_member=member)
        await general_channel.send(f"Hey crew! {member.mention} has joined the server. Say hi or wave to them! 👋", view=view)


# --- DETECT DELETED MESSAGES (SNIPE ENGINE) ---
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


# --- DETECT EDITED MESSAGES (EDIT GHOST LOGGER) ---
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


# --- SPAM COUNTER FOR XP TRACKING ---
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    user_id = str(message.author.id)
    level_db = load_json_data(LEVELS_FILE)

    if user_id not in level_db:
        level_db[user_id] = {"xp": 0, "level": 0}

    level_db[user_id]["xp"] += 1
    current_xp = level_db[user_id]["xp"]
    current_lvl = level_db[user_id]["level"]

    next_lvl_xp = (current_lvl + 1) * 15

    if current_xp >= next_lvl_xp:
        level_db[user_id]["level"] += 1
        new_lvl = level_db[user_id]["level"]
        
        await message.channel.send(f"🔥 **LEVEL UP!** {message.author.mention} just hit **Level {new_lvl}**! Bakchodi chalte rehni chahiye! 🎉")

        if new_lvl == 10:
            guild = message.guild
            newbies_role = discord.utils.get(guild.roles, name="Newbies")
            mehmaan_role = discord.utils.get(guild.roles, name="Mehmaan")

            try:
                if newbies_role in message.author.roles:
                    await message.author.remove_roles(newbies_role)
                if mehmaan_role:
                    await message.author.add_roles(mehmaan_role)
                    await message.channel.send(f"👑 {message.author.mention} ab Newbie nahi rahe! Unhe **Mehmaan** ka V.I.P darja mil chuka hai!")
            except discord.Forbidden:
                print("❌ Role swap failed: Check bot hierarchy layout permissions.")

    save_json_data(level_db, LEVELS_FILE)
    await bot.process_commands(message)


# --- AI QUIZ ENGINE COMMANDS ---

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
    await interaction.response.send_message(f"✅ **Quiz Created Successfully!**\nGroup Name: `{name}`\nAb aap `/add-question` use karke isme AI-powered sawaal daal sakte hain!")


@bot.tree.command(name="add-question", description="Submit a raw question statement; AI will auto-generate 4 accurate options (Admin Only)")
@app_commands.checks.has_permissions(manage_messages=True)
async def add_question(interaction: discord.Interaction, quiz_name: str, question: str):
    quiz_db = load_json_data(QUIZ_FILE)
    quiz_key = quiz_name.lower().replace(" ", "_")

    if quiz_key not in quiz_db:
        await interaction.response.send_message(f"❌ Quiz `{quiz_name}` nahi mili! Pehle `/create-quiz` chalao.", ephemeral=True)
        return

    if not GEMINI_KEY:
        await interaction.response.send_message("❌ Error: Bot ke andar Gemini API Key configured nahi hai!", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=False)

    try:
        # Fixed: Using gemini-1.5-flash-latest to resolve 404 endpoint issues
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        
        prompt = (
            f"You are a quiz master helper bot. For the following question, find the mathematically or contextually accurate correct answer, "
            f"and then generate 3 additional highly relevant but incorrect multiple-choice options. "
            f"Your output must be strictly in raw valid JSON format without markdown ticks, like this:\n"
            f'{{"correct": "Correct Answer Value", "options": ["Option 1", "Option 2", "Option 3", "Option 4"]}}\n'
            f"Note that the correct answer MUST be one of the items inside the 4 items of the options array list! "
            f"Mix the correct answer position randomly inside the array. Here is the question: {question}"
        )

        response = model.generate_content(prompt)
        raw_text = response.text.strip()
        
        if raw_text.startswith("```json"):
            raw_text = raw_text.replace("
```json", "").replace("```", "").strip()
        elif raw_text.startswith("```"):
            raw_text = raw_text.replace("
```", "").strip()

        ai_data = json.loads(raw_text)
        
        parsed_question_entry = {
            "question": question,
            "options": ai_data["options"],
            "correct": ai_data["correct"]
        }

        quiz_db[quiz_key]["questions"].append(parsed_question_entry)
        save_json_data(quiz_db, QUIZ_FILE)

        embed = discord.Embed(title=f"🧠 AI Question Processed & Added!", color=discord.Color.purple())
        embed.add_field(name="Quiz Group", value=quiz_db[quiz_key]["title"], inline=True)
        embed.add_field(name="Total Questions Now", value=str(len(quiz_db[quiz_key]["questions"])), inline=True)
        embed.add_field(name="💬 Question Statement", value=question, inline=False)
        
        options_preview = ""
        for idx, opt in enumerate(ai_data["options"], 1):
            marker = "🔹"
            if opt == ai_data["correct"]:
                marker = "✅ (Correct)"
            options_preview += f"{idx}. {opt} {marker}\n"
            
        embed.add_field(name="📋 Auto Generated Options", value=options_preview, inline=False)
        embed.set_footer(text="Powered by Google Gemini AI")

        await interaction.followup.send(embed=embed)

    except Exception as e:
        print(f"Quiz AI Generation failed: {e}")
        await interaction.followup.send(f"❌ AI options generation process fail ho gaya! Error: `{str(e)}`")


@bot.tree.command(name="start-quiz", description="Launch and stream the full question stack of a quiz group live (Admin Only)")
@app_commands.checks.has_permissions(manage_messages=True)
async def start_quiz(interaction: discord.Interaction, quiz_name: str):
    quiz_db = load_json_data(QUIZ_FILE)
    quiz_key = quiz_name.lower().replace(" ", "_")

    if quiz_key not in quiz_db or not quiz_db[quiz_key]["questions"]:
        await interaction.response.send_message(f"❌ Quiz `{quiz_name}` nahi mili ya usme koi questions nahi hain!", ephemeral=True)
        return

    # Acknowledge command first
    await interaction.response.send_message(f"🚀 **Starting Quiz:** `{quiz_db[quiz_key]['title']}`! Get ready server crew!", ephemeral=False)
    channel = interaction.channel

    questions_list = quiz_db[quiz_key]["questions"]
    
    # Loop through every question inside the selected quiz setup
    for idx, q_item in enumerate(questions_list, 1):
        q_text = q_item["question"]
        opts = q_item["options"]
        correct = q_item["correct"]

        # Formulate display layout
        embed = discord.Embed(
            title=f"❓ Question {idx} of {len(questions_list)}",
            description=f"**{q_text}**\n\n" + "\n".join([f"🔹 {o}" for o in opts]),
            color=discord.Color.blue()
        )
        embed.set_footer(text="Aapke paas jawab dene ke liye 30 seconds hain! Faster responses win!")

        view = QuizPlayView(options=opts, correct_answer=correct)
        msg = await channel.send(embed=embed, view=view)

        # Wait until someone clicks correctly or timeout triggers
        await view.wait()

        # If nobody gave the right answer during active period
        if view.answered_correctly_by is None:
            # Re-fetch or programmatically disable old interactive views
            for child in view.children:
                child.disabled = True
            
            timeout_embed = discord.Embed(
                title=f"⏰ Time's Up for Question {idx}!",
                description=f"**Question:** {q_text}\n\n❌ Kisi ne sahi jawaab nahi diya!\n✅ **Correct Answer:** `{correct}`",
                color=discord.Color.red()
            )
            await msg.edit(embed=timeout_embed, view=view)
        
        # Short resting buffer before blasting the next round setup
        await asyncio.sleep(4.0)

    await channel.send(f"🏁 **QUIZ FINISHED!** `{quiz_db[quiz_key]['title']}` khatam ho chuki hai. Sabhi participants ko shabaashi! 🎉")


# --- SNIPE COMMAND ---
@bot.tree.command(name="snipe", description="Catch the last deleted message in this channel instantly")
async def snipe(interaction: discord.Interaction):
    channel_id = str(interaction.channel.id)
    
    if channel_id not in snipe_data:
        await interaction.response.send_message("🔍 Is channel me mujhe koi bhi haal hi me deleted message nahi mila!", ephemeral=True)
        return

    data = snipe_data[channel_id]
    
    embed = discord.Embed(
        title="🎯 Message Sniped!",
        description=f"{data['content']}{data['extra_info']}",
        color=discord.Color.red()
    )
    embed.set_author(name=f"Sent by {data['author']}", icon_url=data['avatar'])
    embed.set_footer(text=f"Deleted at {data['timestamp']}")
    
    await interaction.response.send_message(embed=embed)


# --- EDIT LOGS COMMAND ---
@bot.tree.command(name="editlogs", description="Check the ghost edit history of a specific user in this server")
@app_commands.checks.has_permissions(manage_messages=True)
async def editlogs(interaction: discord.Interaction, member: discord.Member):
    history_db = load_json_data(SNIPE_FILE)
    current_guild_id = str(interaction.guild.id)
    user_logs = []

    for msg_id, log in history_db.items():
        if log.get("author") == member.name and log.get("guild_id") == current_guild_id:
            user_logs.append(log)

    if not user_logs:
        await interaction.response.send_message(f"🔍 **{member.name}** ne *iss server me* haal hi me koi message edit nahi kiya hai!", ephemeral=True)
        return

    user_logs.reverse()
    latest_logs = user_logs[:5]

    embed = discord.Embed(
        title=f"🕵️‍♂️ Ghost Edit Logs: {member.name}",
        description=f"Pichle kuch edited messages (Only in {interaction.guild.name}):",
        color=discord.Color.orange()
    )
    embed.set_thumbnail(url=member.display_avatar.url)

    for idx, log in enumerate(latest_logs, 1):
        embed.add_field(
            name=f"📝 Edit #{idx} ({log['timestamp']})",
            value=f"**Before:** {log['before']}\n**After:** {log['after']}",
            inline=False
        )

    await interaction.response.send_message(embed=embed)


# --- LEVEL COMMAND ---
@bot.tree.command(name="level", description="Check your current chat status level and message progress")
async def level(interaction: discord.Interaction, member: discord.Member = None):
    target_user = member or interaction.user
    user_id = str(target_user.id)
    level_db = load_json_data(LEVELS_FILE)

    if user_id not in level_db:
        await interaction.response.send_message(f"📊 **{target_user.name}** ne abhi tak chat shuru nahi ki hai! Level: 0 (0 Messages)", ephemeral=False)
        return

    lvl = level_db[user_id]["level"]
    xp = level_db[user_id]["xp"]
    next_xp = (lvl + 1) * 15

    embed = discord.Embed(title=f"📊 {target_user.name}'s Level Stats", color=discord.Color.green())
    embed.add_field(name="Current Level", value=f"✨ **Level {lvl}**", inline=True)
    embed.add_field(name="Total Messages Sent", value=f"💬 **{xp} Messages**", inline=True)
    embed.add_field(name="Next Level At", value=f"📈 **{next_xp} Messages**", inline=False)
    embed.set_thumbnail(url=target_user.display_avatar.url)
    
    await interaction.response.send_message(embed=embed)


# --- MASTER FORCE-SYNC TEXT COMMAND ---
@bot.command()
@commands.is_owner()
async def sync(ctx):
    try:
        await bot.tree.sync()
        await ctx.send("🔄 Saari Slash Commands refresh aur sync ho gayi hain!")
    except Exception as e:
        await ctx.send(f"❌ Sync failed: {e}")

# --- SETUP COMPONENT SLASH COMMAND ---
@bot.tree.command(name="setupcolors", description="Deploy the custom color selection dropdown in this channel")
@app_commands.checks.has_permissions(administrator=True)
async def setupcolors(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🌈 SERVER PROFILE COLORS",
        description=(
            "Welcome! Customize your username color in this server by selecting a vibe from the dropdown menu below.\n\n"
            "🔴 **Red** — Bold & Fierce\n"
            "🔵 **Blue** — Chill & Calm\n"
            "🟢 **Green** — Fresh & Creative\n"
            "🟡 **Yellow** — Bright & Energetic\n"
            "🟠 **Orange** — Wild & Vibrant\n"
            "🟣 **Purple** — Royal & Mystery\n"
            "🌸 **Pink** — Aesthetic & Cute\n\n"
            "**How it works:**\n"
            "1. Click the dropdown menu below.\n"
            "2. Select your favorite color.\n"
            "3. Want to change or remove it? Just select a new one or click the same color again!"
        ),
        color=discord.Color.from_rgb(231, 76, 60)
    )
    embed.set_footer(text="Dhawal Custom Management System")
    await interaction.response.send_message(embed=embed, view=ColorView())

# --- BASIC UTILITY & MODERATION SLASH COMMANDS ---

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

@bot.tree.command(name="purge", description="Delete a specified amount of messages from the channel")
@app_commands.checks.has_permissions(manage_messages=True)
async def purge(interaction: discord.Interaction, amount: int):
    if amount < 1 or amount > 100:
        await interaction.response.send_message("❌ Please specify an amount between 1 and 100.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.followup.send(f"✅ Cleaned up **{len(deleted)}** messages safely!")

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