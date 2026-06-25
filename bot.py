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

# --- INITIAL SETUP & INTENTS ---
intents = discord.Intents.default()
intents.members = True  
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

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

# --- DATABASES (SNIPE, & QUIZ STORAGE) ---
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


# --- MULTIPLAYER QUIZ LOGIC WITH SPEED-BASED SCORING ---
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


# --- AUTOMATED BUMP REMINDER TASK LOOP (Every 2 Hours) ---
@tasks.loop(hours=2.0)
async def bump_reminder_loop():
    await bot.wait_until_ready()
    for guild in bot.guilds:
        # Puraani system ki tarah text keyword se channels match karega
        bump_channel = get_flexible_channel(guild, ["bump", "bot-commands", "general"])
        if bump_channel:
            # Staff role ko server hierarchy mein search karega
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


# --- EVENTS & LOGGING LISTENERS ---
@bot.event
async def on_ready():
    print(f'🤖 {bot.user.name} is ONLINE & MULTIPLAYER SPEED QUIZ + BUMP SYSTEMS READY!')
    bot.add_view(ColorView())
    
    # Start the automated 2-hour bump loop safely if not running
    if not bump_reminder_loop.is_running():
        bump_reminder_loop.start()
        
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


# --- BUMP SLASH COMMAND ---
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


# --- MANUAL & MULTIPLAYER QUIZ COMMANDS ---

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
            if opt == correct_answer_clean:
                marker = "✅ (Correct)"
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
            title=f"🔥 Question {idx} of {len(questions_list)}",
            description=f"### {q_text}\n\n" + "\n".join([f"🔹 {o}" for o in opts]),
            color=discord.Color.blurple()
        )
        embed.set_footer(text="Timer: 15 Seconds! Tap fast!")

        view = MultiQuizView(options=opts, correct_answer=correct, scoreboard=session_scoreboard)
        msg = await channel.send(embed=embed, view=view)

        await view.wait()

        for child in view.children:
            child.disabled = True

        timeout_embed = discord.Embed(
            title=f"⏰ Question {idx} Stopped!",
            description=f"**Question:** {q_text}\n\n✅ **Correct Answer:** `{correct}`",
            color=discord.Color.dark_grey()
        )
        await msg.edit(embed=timeout_embed, view=view)

        # --- LIVE LEADERBOARD DISPLAY ---
        sorted_board = sorted(session_scoreboard.values(), key=lambda x: x["points"], reverse=True)
        board_text = ""
        medals = ["🥇", "🥈", "🥉", "✨"]
        for rank, p_data in enumerate(sorted_board[:10], 1):
            icon = medals[rank-1] if rank <= 3 else medals[3]
            board_text += f"{icon} **#{rank} {p_data['name']}** — `{p_data['points']} pts`\n"

        if not board_text:
            board_text = "*Kisi ne abhi tak koi points nahi score kiye!*"

        board_embed = discord.Embed(
            title=f"📊 Live Leaderboard (After Q{idx})",
            description=board_text,
            color=discord.Color.gold()
        )
        await channel.send(embed=board_embed)

        await asyncio.sleep(5.0)

    # --- FINAL STANDINGS GENERATION ---
    final_sorted = sorted(session_scoreboard.values(), key=lambda x: x["points"], reverse=True)
    final_text = ""
    for rank, p_data in enumerate(final_sorted, 1):
        if rank == 1:
            final_text += f"👑 **CHAMPION: {p_data['name']}** — `{p_data['points']} pts` 🏆\n"
        elif rank == 2:
            final_text += f"🥈 **Runner Up: {p_data['name']}** — `{p_data['points']} pts`\n"
        elif rank == 3:
            final_text += f"🥉 **Third Place: {p_data['name']}** — `{p_data['points']} pts`\n"
        else:
            final_text += f"🔹 **#{rank} {p_data['name']}** — `{p_data['points']} pts`\n"

    if not final_text:
        final_text = "⚠️ Lagta hai kisi ne bhi sahi jawab nahi diya pooray quiz mein!"

    final_embed = discord.Embed(
        title=f"🏁 FINAL STANDINGS: {quiz_db[quiz_key]['title']}",
        description=final_text,
        color=discord.Color.green()
    )
    await channel.send(embed=final_embed)


# --- SNIPE COMMAND ---
@bot.tree.command(name="snipe", description="Catch the last deleted message in this channel instantly")
async def snipe(interaction: discord.Interaction):
    channel_id = str(interaction.channel.id)
    if channel_id not in snipe_data:
        await interaction.response.send_message("🔍 Is channel me koi bhi deleted message nahi mila!", ephemeral=True)
        return

    data = snipe_data[channel_id]
    embed = discord.Embed(title="🎯 Message Sniped!", description=f"{data['content']}{data['extra_info']}", color=discord.Color.red())
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
        await interaction.response.send_message(f"🔍 **{member.name}** ne koi message edit nahi kiya hai!", ephemeral=True)
        return

    user_logs.reverse()
    embed = discord.Embed(title=f"🕵️‍♂️ Ghost Edit Logs: {member.name}", color=discord.Color.orange())
    for idx, log in enumerate(user_logs[:5], 1):
        embed.add_field(name=f"📝 Edit #{idx} ({log['timestamp']})", value=f"**Before:** {log['before']}\n**After:** {log['after']}", inline=False)
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
        description="Select a vibe from the dropdown menu below to customize your role color!",
        color=discord.Color.from_rgb(231, 76, 60)
    )
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
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="avatar", description="View or download someone's profile picture")
async def avatar(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    embed = discord.Embed(title=f"{member.name}'s Avatar")
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
    await interaction.response.send_message(f"🚨 **{member.name}** has been kicked.")

@bot.tree.command(name="ban", description="Ban a member from the server")
@app_commands.checks.has_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    await member.ban(reason=reason)
    await interaction.response.send_message(f"🔨 **{member.name}** has been banned permanently.")

@bot.tree.command(name="mute", description="Mute (Timeout) a member")
@app_commands.checks.has_permissions(moderate_members=True)
async def mute(interaction: discord.Interaction, member: discord.Member, duration_minutes: int = 10, reason: str = "No reason provided"):
    duration = datetime.timedelta(minutes=duration_minutes)
    await member.timeout(duration, reason=reason)
    await interaction.response.send_message(f"🔇 **{member.name}** has been muted for {duration_minutes} minutes.")

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
    embed.add_field(name="Reason", value=reason, inline=False)
    await interaction.response.send_message(content=member.mention, embed=embed)

# --- BOT RUNNER ---
if __name__ == "__main__":
    threading.Thread(target=run_web_server, daemon=True).start()
    token = os.environ.get('DISCORD_BOT_TOKEN')
    bot.run(token)