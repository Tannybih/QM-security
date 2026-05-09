import discord
from discord.ext import commands
import aiosqlite
import os
import asyncio
import datetime
import random
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database", "levels.db")

AUTO_BAN_THRESHOLD = 5

BADWORDS = [
    # English
    "fuck", "shit", "bitch", "bastard", "dick", "pussy", "cunt", "whore",
    "slut", "asshole", "nigga", "nigger", "fag", "faggot", "retard",
    # Urdu / Hindi
    "lund", "lun", "lunn", "mc", "bkl", "chutiya", "chut", "randi",
    "gandu", "harami", "madarchod", "behenchod", "bhenchod", "gaandu",
    "kamina", "kutta", "kutti", "bhosdi", "sala", "saala", "teri maa",
    "teri behen", "maa ki", "baap ki", "maderchod", "bhenchodd",
]

ROASTS = [
    "You're the reason they put instructions on shampoo.",
    "I'd roast you, but my mom said I'm not allowed to burn trash.",
    "You're like a cloud. When you disappear, it's a beautiful day.",
    "I'd agree with you, but then we'd both be wrong.",
    "You have something on your chin... no, the third one down.",
    "If laughter is the best medicine, your face must be curing diseases.",
    "You're not stupid; you just have bad luck thinking.",
    "I'd explain it to you but I left my crayons at home.",
    "Some day you'll go far — and I hope you stay there.",
    "You're proof that even evolution makes mistakes.",
]

QUOTES = [
    "The only way to do great work is to love what you do. — Steve Jobs",
    "In the middle of every difficulty lies opportunity. — Einstein",
    "It does not matter how slowly you go as long as you do not stop. — Confucius",
    "Success is not final, failure is not fatal. — Churchill",
    "Believe you can and you're halfway there. — Roosevelt",
    "You miss 100% of the shots you don't take. — Wayne Gretzky",
    "Hard work beats talent when talent doesn't work hard. — Kevin Durant",
    "Dream big. Work hard. Stay focused.",
    "Your only limit is your mind.",
    "Don't watch the clock; do what it does. Keep going. — Sam Levenson",
]

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="Q!", intents=intents)

# ==========================================
# CREATE DATABASE TABLES
# ==========================================

async def setup_database():

    async with aiosqlite.connect(DB_PATH) as db:

        await db.execute("""
            CREATE TABLE IF NOT EXISTS levels (
                user_id INTEGER PRIMARY KEY,
                xp INTEGER,
                level INTEGER
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS warnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                guild_id INTEGER,
                reason TEXT,
                moderator_id INTEGER
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS welcome (
                guild_id INTEGER PRIMARY KEY,
                channel_id INTEGER
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                guild_id INTEGER PRIMARY KEY,
                mod_log_channel_id INTEGER,
                announce_channel_id INTEGER,
                auto_role_id INTEGER,
                report_channel_id INTEGER
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                channel_id INTEGER,
                reminder TEXT,
                remind_at REAL
            )
        """)

        await db.commit()

# ==========================================
# BOT READY
# ==========================================

@bot.event
async def on_ready():

    await setup_database()
    bot.loop.create_task(reminder_loop())
    print(f"{bot.user} is online!")

# ==========================================
# HELPERS
# ==========================================

async def get_setting(guild_id, key):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(f"SELECT {key} FROM settings WHERE guild_id = ?", (guild_id,))
        row = await cursor.fetchone()
        return row[0] if row else None

async def send_mod_log(guild, embed):
    channel_id = await get_setting(guild.id, "mod_log_channel_id")
    if channel_id:
        channel = guild.get_channel(channel_id)
        if channel:
            await channel.send(embed=embed)

async def auto_ban_check(member, guild):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM warnings WHERE user_id = ? AND guild_id = ?",
            (member.id, guild.id)
        )
        count = (await cursor.fetchone())[0]

    if count >= AUTO_BAN_THRESHOLD:
        try:
            await member.ban(reason=f"Auto-ban: reached {AUTO_BAN_THRESHOLD} warnings")
            embed = discord.Embed(
                title="🔨 Auto-Ban",
                description=f"{member.mention} was auto-banned after reaching {AUTO_BAN_THRESHOLD} warnings.",
                color=discord.Color.red()
            )
            await send_mod_log(guild, embed)
        except discord.Forbidden:
            pass

# ==========================================
# WELCOME NEW MEMBERS
# ==========================================

@bot.event
async def on_member_join(member):

    async with aiosqlite.connect(DB_PATH) as db:

        cursor = await db.execute(
            "SELECT channel_id FROM welcome WHERE guild_id = ?",
            (member.guild.id,)
        )
        row = await cursor.fetchone()

    # Welcome embed in welcome channel
    if row:
        channel = member.guild.get_channel(row[0])
        if channel:
            embed = discord.Embed(
                title=f"Welcome to {member.guild.name}!",
                description=f"Hey {member.mention}, glad to have you here! 🎉",
                color=discord.Color.gold()
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            await channel.send(embed=embed)

    # Announcement embed in #announcements
    announce_channel = discord.utils.get(member.guild.text_channels, name="announcements")
    if announce_channel:
        embed = discord.Embed(
            title="👋 New Member!",
            description=f"Welcome to the server, {member.mention}! We're glad to have you here. Make sure to read the rules and enjoy your stay!",
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"{member.guild.name} • {member.guild.member_count} members")
        await announce_channel.send(embed=embed)

    # Auto-role
    auto_role_id = await get_setting(member.guild.id, "auto_role_id")
    if auto_role_id:
        role = member.guild.get_role(auto_role_id)
        if role:
            try:
                await member.add_roles(role)
            except discord.Forbidden:
                pass

    # DM the new member
    try:
        dm_embed = discord.Embed(
            title=f"👋 Welcome to {member.guild.name}!",
            description=(
                f"Hey **{member.display_name}**! We're happy to have you.\n\n"
                f"Here are a few things to get started:\n"
                f"• Read the rules to stay safe\n"
                f"• Introduce yourself in the server\n"
                f"• Have fun and enjoy the community!\n\n"
                f"If you need help, feel free to open a ticket with `Q!ticket`."
            ),
            color=discord.Color.blurple()
        )
        dm_embed.set_thumbnail(url=member.guild.icon.url if member.guild.icon else None)
        await member.send(embed=dm_embed)
    except discord.Forbidden:
        pass

@bot.command()
@commands.has_permissions(administrator=True)
async def setwelcome(ctx, channel: discord.TextChannel):

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO welcome (guild_id, channel_id) VALUES (?, ?)",
            (ctx.guild.id, channel.id)
        )
        await db.commit()

    await ctx.send(f"✅ Welcome channel set to {channel.mention}.")

# ==========================================
# GIF CHECK HELPER
# ==========================================

def message_has_gif(message):
    if any(a.filename.lower().endswith(".gif") for a in message.attachments):
        return True
    for e in message.embeds:
        if e.type == "gifv":
            return True
        if e.url and ("tenor.com" in e.url or "giphy.com" in e.url or e.url.endswith(".gif")):
            return True
        if e.image and e.image.url and e.image.url.endswith(".gif"):
            return True
    if "tenor.com" in message.content or "giphy.com" in message.content:
        return True
    return False

async def check_gif(message):
    if message.author.bot:
        return
    if isinstance(message.channel, discord.DMChannel):
        return

    if message_has_gif(message):
        await message.delete()
        warning_msg = await message.channel.send(
            f"⚠️ {message.author.mention}, GIFs are not allowed here! Auto-warning issued."
        )
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO warnings (user_id, guild_id, reason, moderator_id) VALUES (?, ?, ?, ?)",
                (message.author.id, message.guild.id, "Auto-mod: GIF", bot.user.id)
            )
            await db.commit()
        await auto_ban_check(message.author, message.guild)
        await asyncio.sleep(5)
        await warning_msg.delete()
        return True

    return False

@bot.event
async def on_message_edit(before, after):
    await check_gif(after)

# ==========================================
# ON MESSAGE — XP + AUTOMOD
# ==========================================

@bot.event
async def on_message(message):

    if message.author.bot:
        return

    if await check_gif(message):
        return

    # Bad word filter
    content_lower = message.content.lower()
    if any(word in content_lower for word in BADWORDS):
        await message.delete()
        warning_msg = await message.channel.send(
            f"⚠️ {message.author.mention}, watch your language! Auto-warning issued."
        )
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO warnings (user_id, guild_id, reason, moderator_id) VALUES (?, ?, ?, ?)",
                (message.author.id, message.guild.id, "Auto-mod: bad word", bot.user.id)
            )
            await db.commit()
        await auto_ban_check(message.author, message.guild)
        await asyncio.sleep(5)
        await warning_msg.delete()
        return

    # XP
    user_id = message.author.id
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT xp, level FROM levels WHERE user_id = ?", (user_id,))
        data = await cursor.fetchone()

        if data is None:
            await db.execute("INSERT INTO levels (user_id, xp, level) VALUES (?, ?, ?)", (user_id, 10, 1))
        else:
            xp, level = data
            xp += 10
            if xp >= level * 100:
                level += 1
                await message.channel.send(f"🎉 {message.author.mention} leveled up to level {level}!")
            await db.execute("UPDATE levels SET xp = ?, level = ? WHERE user_id = ?", (xp, level, user_id))

        await db.commit()

    await bot.process_commands(message)

# ==========================================
# RANK
# ==========================================

@bot.command()
async def rank(ctx):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT xp, level FROM levels WHERE user_id = ?", (ctx.author.id,))
        data = await cursor.fetchone()

    if data is None:
        await ctx.send("You have no XP yet.")
    else:
        xp, level = data
        await ctx.send(f"📈 Level: {level} | XP: {xp}")

# ==========================================
# LEADERBOARD
# ==========================================

@bot.command()
async def leaderboard(ctx):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT user_id, xp, level FROM levels ORDER BY level DESC, xp DESC LIMIT 10"
        )
        rows = await cursor.fetchall()

    if not rows:
        await ctx.send("No one has XP yet.")
        return

    embed = discord.Embed(title="🏆 XP Leaderboard", color=discord.Color.gold())
    for i, (user_id, xp, level) in enumerate(rows, 1):
        user = ctx.guild.get_member(user_id)
        name = user.display_name if user else f"Unknown ({user_id})"
        embed.add_field(name=f"#{i} {name}", value=f"Level {level} | XP {xp}", inline=False)

    await ctx.send(embed=embed)

# ==========================================
# KICK
# ==========================================

@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason="No reason provided"):
    await member.kick(reason=reason)
    await ctx.send(f"👢 {member.mention} has been kicked. Reason: {reason}")
    embed = discord.Embed(title="👢 Kick", description=f"{member} was kicked by {ctx.author}.\nReason: {reason}", color=discord.Color.orange())
    await send_mod_log(ctx.guild, embed)

@kick.error
async def kick_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to kick members.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Usage: `Q!kick @user [reason]`")

# ==========================================
# BAN
# ==========================================

@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason="No reason provided"):
    await member.ban(reason=reason)
    await ctx.send(f"🔨 {member.mention} has been banned. Reason: {reason}")
    embed = discord.Embed(title="🔨 Ban", description=f"{member} was banned by {ctx.author}.\nReason: {reason}", color=discord.Color.red())
    await send_mod_log(ctx.guild, embed)

@ban.error
async def ban_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to ban members.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Usage: `Q!ban @user [reason]`")

# ==========================================
# UNBAN
# ==========================================

@bot.command()
@commands.has_permissions(ban_members=True)
async def unban(ctx, user_id: int):
    try:
        user = await bot.fetch_user(user_id)
        await ctx.guild.unban(user)
        await ctx.send(f"✅ {user} has been unbanned.")
    except discord.NotFound:
        await ctx.send("❌ User not found or is not banned.")

@unban.error
async def unban_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to unban members.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Usage: `Q!unban <user_id>`")

# ==========================================
# TIMEOUT
# ==========================================

@bot.command()
@commands.has_permissions(moderate_members=True)
async def timeout(ctx, member: discord.Member, duration: int, *, reason="No reason provided"):
    until = discord.utils.utcnow() + datetime.timedelta(minutes=duration)
    await member.timeout(until, reason=reason)
    await ctx.send(f"⏱️ {member.mention} timed out for {duration} minute(s). Reason: {reason}")
    embed = discord.Embed(title="⏱️ Timeout", description=f"{member} timed out by {ctx.author} for {duration}m.\nReason: {reason}", color=discord.Color.orange())
    await send_mod_log(ctx.guild, embed)

@timeout.error
async def timeout_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to timeout members.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Usage: `Q!timeout @user <minutes> [reason]`")

# ==========================================
# WARN
# ==========================================

@bot.command()
@commands.has_permissions(manage_messages=True)
async def warn(ctx, member: discord.Member, *, reason="No reason provided"):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO warnings (user_id, guild_id, reason, moderator_id) VALUES (?, ?, ?, ?)",
            (member.id, ctx.guild.id, reason, ctx.author.id)
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT COUNT(*) FROM warnings WHERE user_id = ? AND guild_id = ?",
            (member.id, ctx.guild.id)
        )
        count = (await cursor.fetchone())[0]

    await ctx.send(f"⚠️ {member.mention} warned. Reason: {reason} (Total: {count})")
    embed = discord.Embed(title="⚠️ Warn", description=f"{member} warned by {ctx.author}.\nReason: {reason}\nTotal warnings: {count}", color=discord.Color.yellow())
    await send_mod_log(ctx.guild, embed)
    await auto_ban_check(member, ctx.guild)

@warn.error
async def warn_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to warn members.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Usage: `Q!warn @user [reason]`")

# ==========================================
# WARNINGS
# ==========================================

@bot.command()
@commands.has_permissions(manage_messages=True)
async def warnings(ctx, member: discord.Member):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, reason, moderator_id FROM warnings WHERE user_id = ? AND guild_id = ?",
            (member.id, ctx.guild.id)
        )
        rows = await cursor.fetchall()

    if not rows:
        await ctx.send(f"✅ {member.mention} has no warnings.")
        return

    embed = discord.Embed(title=f"Warnings for {member}", color=discord.Color.orange())
    for warn_id, reason, mod_id in rows:
        mod = ctx.guild.get_member(mod_id)
        mod_name = mod.name if mod else f"ID: {mod_id}"
        embed.add_field(name=f"Warning #{warn_id}", value=f"Reason: {reason}\nBy: {mod_name}", inline=False)

    await ctx.send(embed=embed)

@warnings.error
async def warnings_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to view warnings.")

# ==========================================
# CLEAR WARNINGS
# ==========================================

@bot.command()
@commands.has_permissions(administrator=True)
async def clearwarns(ctx, member: discord.Member):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM warnings WHERE user_id = ? AND guild_id = ?", (member.id, ctx.guild.id))
        await db.commit()

    await ctx.send(f"✅ All warnings cleared for {member.mention}.")

@clearwarns.error
async def clearwarns_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to clear warnings.")

# ==========================================
# PURGE
# ==========================================

@bot.command()
@commands.has_permissions(manage_messages=True)
async def purge(ctx, amount: int):
    if amount < 1 or amount > 100:
        await ctx.send("❌ Please provide a number between 1 and 100.")
        return
    await ctx.channel.purge(limit=amount + 1)
    msg = await ctx.send(f"🧹 Deleted {amount} message(s).")
    await asyncio.sleep(3)
    await msg.delete()

@purge.error
async def purge_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to delete messages.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Usage: `Q!purge <amount>`")

# ==========================================
# LOCK / UNLOCK
# ==========================================

@bot.command()
@commands.has_permissions(manage_channels=True)
async def lock(ctx):
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False)
    await ctx.send(f"🔒 {ctx.channel.mention} has been locked.")

@bot.command()
@commands.has_permissions(manage_channels=True)
async def unlock(ctx):
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=True)
    await ctx.send(f"🔓 {ctx.channel.mention} has been unlocked.")

# ==========================================
# SLOWMODE
# ==========================================

@bot.command()
@commands.has_permissions(manage_channels=True)
async def slowmode(ctx, seconds: int):
    if seconds < 0 or seconds > 21600:
        await ctx.send("❌ Slowmode must be between 0 and 21600 seconds.")
        return
    await ctx.channel.edit(slowmode_delay=seconds)
    if seconds == 0:
        await ctx.send("✅ Slowmode disabled.")
    else:
        await ctx.send(f"🐢 Slowmode set to {seconds} second(s).")

@slowmode.error
async def slowmode_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Usage: `Q!slowmode <seconds>` (0 to disable)")

# ==========================================
# NICK
# ==========================================

@bot.command()
@commands.has_permissions(manage_nicknames=True)
async def nick(ctx, member: discord.Member, *, nickname=None):
    await member.edit(nick=nickname)
    if nickname:
        await ctx.send(f"✅ Nickname for {member.mention} changed to **{nickname}**.")
    else:
        await ctx.send(f"✅ Nickname for {member.mention} has been reset.")

@nick.error
async def nick_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to change nicknames.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Usage: `Q!nick @user [new nickname]`")

# ==========================================
# NUKE
# ==========================================

@bot.command()
@commands.has_permissions(administrator=True)
async def nuke(ctx):
    channel = ctx.channel
    new_channel = await channel.clone(reason=f"Nuked by {ctx.author}")
    await channel.delete()
    await new_channel.send(f"💥 Channel nuked by {ctx.author.mention}.")

@nuke.error
async def nuke_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to nuke channels.")

# ==========================================
# ROLE
# ==========================================

@bot.command()
@commands.has_permissions(manage_roles=True)
async def role(ctx, member: discord.Member, rolename: discord.Role):
    if rolename in member.roles:
        await member.remove_roles(rolename)
        await ctx.send(f"✅ Removed **{rolename.name}** from {member.mention}.")
    else:
        await member.add_roles(rolename)
        await ctx.send(f"✅ Added **{rolename.name}** to {member.mention}.")

@role.error
async def role_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to manage roles.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Usage: `Q!role @user @role`")

# ==========================================
# AUTO ROLE SETUP
# ==========================================

@bot.command()
@commands.has_permissions(administrator=True)
async def setautorole(ctx, rolename: discord.Role):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO settings (guild_id, auto_role_id) VALUES (?, ?) ON CONFLICT(guild_id) DO UPDATE SET auto_role_id = ?",
            (ctx.guild.id, rolename.id, rolename.id)
        )
        await db.commit()
    await ctx.send(f"✅ Auto-role set to **{rolename.name}**. New members will get this role automatically.")

# ==========================================
# MOD LOG SETUP
# ==========================================

@bot.command()
@commands.has_permissions(administrator=True)
async def setmodlog(ctx, channel: discord.TextChannel):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO settings (guild_id, mod_log_channel_id) VALUES (?, ?) ON CONFLICT(guild_id) DO UPDATE SET mod_log_channel_id = ?",
            (ctx.guild.id, channel.id, channel.id)
        )
        await db.commit()
    await ctx.send(f"✅ Mod log channel set to {channel.mention}.")

# ==========================================
# REPORT SETUP + COMMAND
# ==========================================

@bot.command()
@commands.has_permissions(administrator=True)
async def setreports(ctx, channel: discord.TextChannel):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO settings (guild_id, report_channel_id) VALUES (?, ?) ON CONFLICT(guild_id) DO UPDATE SET report_channel_id = ?",
            (ctx.guild.id, channel.id, channel.id)
        )
        await db.commit()
    await ctx.send(f"✅ Reports channel set to {channel.mention}.")

@bot.command()
async def report(ctx, member: discord.Member, *, reason):
    channel_id = await get_setting(ctx.guild.id, "report_channel_id")
    if not channel_id:
        await ctx.send("❌ No reports channel set. Ask an admin to use `Q!setreports #channel`.")
        return

    channel = ctx.guild.get_channel(channel_id)
    if channel:
        embed = discord.Embed(title="🚨 New Report", color=discord.Color.red())
        embed.add_field(name="Reported User", value=member.mention, inline=True)
        embed.add_field(name="Reported By", value=ctx.author.mention, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_footer(text=f"User ID: {member.id}")
        await channel.send(embed=embed)

    await ctx.message.delete()
    msg = await ctx.send("✅ Your report has been submitted to the mods.")
    await asyncio.sleep(5)
    await msg.delete()

@report.error
async def report_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Usage: `Q!report @user <reason>`")

# ==========================================
# ANNOUNCE
# ==========================================

@bot.command()
@commands.has_permissions(manage_guild=True)
async def announce(ctx, *, message):
    channel = discord.utils.get(ctx.guild.text_channels, name="announcements")
    if not channel:
        await ctx.send("❌ No #announcements channel found.")
        return

    embed = discord.Embed(
        title="📢 Announcement",
        description=message,
        color=discord.Color.blurple()
    )
    embed.set_footer(text=f"Posted by {ctx.author.display_name}")
    await channel.send(embed=embed)
    await ctx.message.delete()

@announce.error
async def announce_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to make announcements.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Usage: `Q!announce <message>`")

# ==========================================
# REMIND
# ==========================================

@bot.command()
async def remind(ctx, duration: str, *, reminder):
    units = {"s": 1, "m": 60, "h": 3600}
    unit = duration[-1]
    if unit not in units or not duration[:-1].isdigit():
        await ctx.send("❌ Usage: `Q!remind 10m do something` (s/m/h)")
        return

    seconds = int(duration[:-1]) * units[unit]
    remind_at = datetime.datetime.utcnow().timestamp() + seconds

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO reminders (user_id, channel_id, reminder, remind_at) VALUES (?, ?, ?, ?)",
            (ctx.author.id, ctx.channel.id, reminder, remind_at)
        )
        await db.commit()

    await ctx.send(f"⏰ Got it! I'll remind you in **{duration}**: {reminder}")

async def reminder_loop():
    await bot.wait_until_ready()
    while not bot.is_closed():
        now = datetime.datetime.utcnow().timestamp()
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT id, user_id, channel_id, reminder FROM reminders WHERE remind_at <= ?", (now,))
            rows = await cursor.fetchall()
            for row in rows:
                rid, user_id, channel_id, reminder = row
                channel = bot.get_channel(channel_id)
                if channel:
                    await channel.send(f"⏰ <@{user_id}> Reminder: **{reminder}**")
                await db.execute("DELETE FROM reminders WHERE id = ?", (rid,))
            await db.commit()
        await asyncio.sleep(10)

# ==========================================
# USERINFO
# ==========================================

@bot.command()
async def userinfo(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = discord.Embed(title=f"User Info — {member}", color=discord.Color.blue())
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="ID", value=member.id, inline=True)
    embed.add_field(name="Nickname", value=member.nick or "None", inline=True)
    embed.add_field(name="Account Created", value=member.created_at.strftime("%Y-%m-%d"), inline=True)
    embed.add_field(name="Joined Server", value=member.joined_at.strftime("%Y-%m-%d"), inline=True)
    embed.add_field(name="Top Role", value=member.top_role.mention, inline=True)
    embed.add_field(name="Bot", value=member.bot, inline=True)
    await ctx.send(embed=embed)

# ==========================================
# SERVERINFO
# ==========================================

@bot.command()
async def serverinfo(ctx):
    guild = ctx.guild
    embed = discord.Embed(title=f"Server Info — {guild.name}", color=discord.Color.green())
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.add_field(name="ID", value=guild.id, inline=True)
    embed.add_field(name="Owner", value=guild.owner.mention, inline=True)
    embed.add_field(name="Members", value=guild.member_count, inline=True)
    embed.add_field(name="Channels", value=len(guild.channels), inline=True)
    embed.add_field(name="Roles", value=len(guild.roles), inline=True)
    embed.add_field(name="Created", value=guild.created_at.strftime("%Y-%m-%d"), inline=True)
    await ctx.send(embed=embed)

# ==========================================
# AVATAR
# ==========================================

@bot.command()
async def avatar(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = discord.Embed(title=f"{member.display_name}'s Avatar", color=discord.Color.blurple())
    embed.set_image(url=member.display_avatar.url)
    await ctx.send(embed=embed)

# ==========================================
# PING
# ==========================================

@bot.command()
async def ping(ctx):
    latency = round(bot.latency * 1000)
    await ctx.send(f"🏓 Pong! Latency: **{latency}ms**")

# ==========================================
# 8BALL
# ==========================================

@bot.command(name="8ball")
async def eightball(ctx, *, question):
    responses = [
        "It is certain.", "Without a doubt.", "Yes, definitely.",
        "You may rely on it.", "As I see it, yes.", "Most likely.",
        "Outlook good.", "Yes.", "Signs point to yes.",
        "Reply hazy, try again.", "Ask again later.", "Better not tell you now.",
        "Cannot predict now.", "Concentrate and ask again.",
        "Don't count on it.", "My reply is no.", "My sources say no.",
        "Outlook not so good.", "Very doubtful.", "Absolutely not."
    ]
    answer = random.choice(responses)
    embed = discord.Embed(color=discord.Color.purple())
    embed.add_field(name="Question", value=question, inline=False)
    embed.add_field(name="Answer", value=answer, inline=False)
    await ctx.send(embed=embed)

@eightball.error
async def eightball_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Usage: `Q!8ball <question>`")

# ==========================================
# COINFLIP
# ==========================================

@bot.command()
async def coinflip(ctx):
    result = random.choice(["Heads 🪙", "Tails 🪙"])
    await ctx.send(f"The coin landed on **{result}**!")

# ==========================================
# DICE
# ==========================================

@bot.command()
async def dice(ctx):
    result = random.randint(1, 6)
    await ctx.send(f"🎲 You rolled a **{result}**!")

# ==========================================
# ROCK PAPER SCISSORS
# ==========================================

@bot.command()
async def rps(ctx, choice: str):
    choice = choice.lower()
    if choice not in ("rock", "paper", "scissors"):
        await ctx.send("❌ Choose `rock`, `paper`, or `scissors`.")
        return

    bot_choice = random.choice(["rock", "paper", "scissors"])
    emojis = {"rock": "🪨", "paper": "📄", "scissors": "✂️"}

    if choice == bot_choice:
        result = "It's a tie!"
    elif (choice == "rock" and bot_choice == "scissors") or \
         (choice == "paper" and bot_choice == "rock") or \
         (choice == "scissors" and bot_choice == "paper"):
        result = "You win! 🎉"
    else:
        result = "I win! 😈"

    await ctx.send(f"You: {emojis[choice]} vs Me: {emojis[bot_choice]} — **{result}**")

@rps.error
async def rps_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Usage: `Q!rps <rock/paper/scissors>`")

# ==========================================
# ROAST
# ==========================================

@bot.command()
async def roast(ctx, member: discord.Member = None):
    member = member or ctx.author
    roast = random.choice(ROASTS)
    await ctx.send(f"{member.mention}, {roast}")

@roast.error
async def roast_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Usage: `Q!roast @user`")

# ==========================================
# QUOTE
# ==========================================

@bot.command()
async def quote(ctx):
    q = random.choice(QUOTES)
    embed = discord.Embed(description=f"💬 {q}", color=discord.Color.teal())
    await ctx.send(embed=embed)

# ==========================================
# POLL
# ==========================================

@bot.command()
async def poll(ctx, *, question):
    embed = discord.Embed(title="📊 Poll", description=question, color=discord.Color.teal())
    embed.set_footer(text=f"Poll by {ctx.author.display_name}")
    msg = await ctx.send(embed=embed)
    await msg.add_reaction("✅")
    await msg.add_reaction("❌")

@poll.error
async def poll_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Usage: `Q!poll <question>`")

# ==========================================
# CLEAR GIFS
# ==========================================

@bot.command()
@commands.has_permissions(manage_messages=True)
async def cleargifs(ctx):
    deleted = 0
    async for message in ctx.channel.history(limit=500):
        if message_has_gif(message):
            await message.delete()
            deleted += 1
            await asyncio.sleep(0.5)

    msg = await ctx.send(f"🧹 Cleared {deleted} GIF(s) from this channel.")
    await asyncio.sleep(5)
    await msg.delete()

@cleargifs.error
async def cleargifs_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to delete messages.")

# ==========================================
# TICKET
# ==========================================

@bot.command()
async def ticket(ctx):
    guild = ctx.guild
    member = ctx.author
    existing = discord.utils.get(guild.text_channels, name=f"ticket-{member.name.lower()}")

    if existing:
        await ctx.send(f"❌ You already have an open ticket: {existing.mention}")
        return

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        member: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
    }

    channel = await guild.create_text_channel(
        f"ticket-{member.name.lower()}",
        overwrites=overwrites,
        reason=f"Ticket opened by {member}"
    )

    embed = discord.Embed(
        title="🎫 Ticket Opened",
        description=f"Hello {member.mention}! A mod will be with you shortly.\nType `Q!closeticket` to close this ticket.",
        color=discord.Color.green()
    )
    await channel.send(embed=embed)
    await ctx.send(f"✅ Your ticket has been created: {channel.mention}")

@bot.command()
async def closeticket(ctx):
    if not ctx.channel.name.startswith("ticket-"):
        await ctx.send("❌ This is not a ticket channel.")
        return
    await ctx.send("🔒 Closing ticket in 5 seconds...")
    await asyncio.sleep(5)
    await ctx.channel.delete()

# ==========================================

bot.run(os.getenv("TOKEN"))
