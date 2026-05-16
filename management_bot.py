import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import time
from datetime import datetime

# ================= CONFIGURATION =================
CONFIG_FILE = "config.json"
SCAMMERS_FILE = "scammers.json"
REPS_FILE = "reps.json"
TOKEN = os.getenv("MGMT_BOT_TOKEN")

def load_json(file):
    if not os.path.exists(file):
        with open(file, "w") as f:
            json.dump({}, f)
    with open(file, "r") as f:
        return json.load(f)

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)

config = load_json(CONFIG_FILE)

# ================= BOT SETUP =================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ================= UTILS =================
def is_co_owner_plus(interaction: discord.Interaction):
    roles = [config["ROLES"]["OWNER"], config["ROLES"]["CO_OWNER"]]
    return any(discord.utils.get(interaction.user.roles, id=r) for r in roles)

def black_embed(title=None, description=None):
    return discord.Embed(title=title, description=description, color=config.get("THEME_COLOR", 0x000000))

# ================= EVENTS =================
@bot.event
async def on_ready():
    print(f"✅ Management Bot logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(f"Sync error: {e}")

@bot.event
async def on_member_join(member):
    welcome_channel_id = config["CHANNELS"]["WELCOME"]
    if welcome_channel_id == 0: return
    
    channel = bot.get_channel(welcome_channel_id)
    if not channel: return
    
    embed = black_embed(
        title=f"{config['EMOJIS']['LIVESTOCK']} Welcome to {config['BOT_NAME']} {config['EMOJIS']['LIVESTOCK']}",
        description=f"Welcome {member.mention} to the server! We hope you enjoy your stay."
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="Member Count", value=f"{member.guild.member_count}", inline=True)
    embed.set_footer(text=f"ID: {member.id}")
    
    await channel.send(embed=embed)

# ================= COMMANDS =================

# ---- Sync ----
@bot.tree.command(name="sync", description="Sync bot commands (Owner only)")
async def sync(interaction: discord.Interaction):
    if not discord.utils.get(interaction.user.roles, id=config["ROLES"]["OWNER"]):
        await interaction.response.send_message("Owner only.", ephemeral=True)
        return
    await bot.tree.sync()
    await interaction.response.send_message("Commands synced!", ephemeral=True)

# ---- Reputation System ----
@bot.tree.command(name="rep", description="Submit a reputation/vouch for a user")
@app_commands.describe(user="The user you are vouching for", rating="Rating out of 5", message="Vouch details")
async def rep(interaction: discord.Interaction, user: discord.Member, rating: int, message: str):
    reviews_channel_id = config["CHANNELS"]["REVIEWS"]
    if reviews_channel_id == 0:
        await interaction.response.send_message("Reviews channel not configured.", ephemeral=True)
        return
    
    channel = bot.get_channel(reviews_channel_id)
    if not channel:
        await interaction.response.send_message("Reviews channel not found.", ephemeral=True)
        return
    
    if rating < 1 or rating > 5:
        await interaction.response.send_message("Rating must be between 1 and 5.", ephemeral=True)
        return
    
    stars = "⭐" * rating
    embed = black_embed(title=f"New Vouch for {user.display_name}", description=message)
    embed.add_field(name="Rating", value=stars, inline=True)
    embed.add_field(name="Voucher", value=interaction.user.mention, inline=True)
    embed.set_footer(text=f"{config['BOT_NAME']} Reviews")
    embed.timestamp = datetime.now()
    
    await channel.send(embed=embed)
    
    # Save rep
    reps = load_json(REPS_FILE)
    user_id = str(user.id)
    reps.setdefault(user_id, []).append({
        "voucher": interaction.user.id,
        "rating": rating,
        "message": message,
        "time": time.time()
    })
    save_json(REPS_FILE, reps)
    
    await interaction.response.send_message(f"Vouch submitted for {user.mention}!", ephemeral=True)

@bot.tree.command(name="vouch", description="Alias for /rep")
async def vouch(interaction: discord.Interaction, user: discord.Member, rating: int, message: str):
    await rep(interaction, user, rating, message)

@bot.tree.command(name="reps", description="View reputations for a user")
async def view_reps(interaction: discord.Interaction, user: discord.Member):
    reps = load_json(REPS_FILE)
    user_id = str(user.id)
    if user_id not in reps or not reps[user_id]:
        await interaction.response.send_message(f"No reputations found for {user.mention}.", ephemeral=True)
        return
    embed = black_embed(title=f"Reputations for {user.display_name}")
    for r in reps[user_id][-5:]:
        stars = "⭐" * r["rating"]
        embed.add_field(name=f"Rating: {stars}", value=f"\"{r['message']}\"\n— <@{r['voucher']}>", inline=False)
    await interaction.response.send_message(embed=embed)

# ---- Moderation ----
@bot.tree.command(name="ban", description="Ban a user from the server")
@app_commands.describe(member="The member to ban", reason="Reason for the ban")
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    if not interaction.user.guild_permissions.ban_members:
        await interaction.response.send_message("You don't have permission to ban members.", ephemeral=True)
        return
    
    try:
        await member.ban(reason=reason)
        embed = black_embed(title="User Banned", description=f"**User:** {member.mention}\n**Reason:** {reason}")
        embed.set_footer(text=f"Action by {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        await interaction.response.send_message(f"Failed to ban member: {e}", ephemeral=True)

@bot.tree.command(name="kick", description="Kick a user from the server")
@app_commands.describe(member="The member to kick", reason="Reason for the kick")
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    if not interaction.user.guild_permissions.kick_members:
        await interaction.response.send_message("You don't have permission to kick members.", ephemeral=True)
        return
    try:
        await member.kick(reason=reason)
        embed = black_embed(title="User Kicked", description=f"**User:** {member.mention}\n**Reason:** {reason}")
        embed.set_footer(text=f"Action by {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        await interaction.response.send_message(f"Failed to kick member: {e}", ephemeral=True)

@bot.tree.command(name="clear", description="Clear messages")
@app_commands.default_permissions(manage_messages=True)
async def clear(interaction: discord.Interaction, amount: int):
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.followup.send(f"Cleared `{len(deleted)}` messages.", ephemeral=True)

# ---- Custom Moderation (Example of synced/custom) ----
@bot.tree.command(name="custom_ban", description="Custom ban command with special formatting")
async def custom_ban(interaction: discord.Interaction, member: discord.Member, reason: str = "Violation of rules"):
    await ban(interaction, member, reason)

@bot.tree.command(name="custom_kick", description="Custom kick command with special formatting")
async def custom_kick(interaction: discord.Interaction, member: discord.Member, reason: str = "Violation of rules"):
    await kick(interaction, member, reason)

# ---- Protection ----
@bot.tree.command(name="bypass_antiraid", description="Add a user to the anti-raid bypass list")
async def bypass_antiraid(interaction: discord.Interaction, user: discord.User):
    if not is_co_owner_plus(interaction):
        await interaction.response.send_message("No permission.", ephemeral=True)
        return
    # In a real anti-raid system, you'd store this in a database
    await interaction.response.send_message(f"{user.mention} added to anti-raid bypass list.", ephemeral=True)

@bot.tree.command(name="unbypass_antiraid", description="Remove a user from the anti-raid bypass list")
async def unbypass_antiraid(interaction: discord.Interaction, user: discord.User):
    if not is_co_owner_plus(interaction):
        await interaction.response.send_message("No permission.", ephemeral=True)
        return
    await interaction.response.send_message(f"{user.mention} removed from anti-raid bypass list.", ephemeral=True)

# ---- Channel Management ----
@bot.tree.command(name="lock", description="Lock channel")
@app_commands.default_permissions(manage_channels=True)
async def lock(interaction: discord.Interaction):
    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
    await interaction.response.send_message(f"🔒 {interaction.channel.mention} locked.")

@bot.tree.command(name="unlock", description="Unlock channel")
@app_commands.default_permissions(manage_channels=True)
async def unlock(interaction: discord.Interaction):
    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=True)
    await interaction.response.send_message(f"🔓 {interaction.channel.mention} unlocked.")

@bot.tree.command(name="slowmode", description="Set slowmode")
@app_commands.default_permissions(manage_channels=True)
async def slowmode(interaction: discord.Interaction, seconds: int):
    await interaction.channel.edit(slowmode_delay=seconds)
    await interaction.response.send_message(f"Slowmode: `{seconds}`s.")

@bot.tree.command(name="nuke", description="Nuke channel")
async def nuke(interaction: discord.Interaction):
    if not discord.utils.get(interaction.user.roles, id=config["ROLES"]["OWNER"]):
        await interaction.response.send_message("Owner only.", ephemeral=True)
        return
    new = await interaction.channel.clone()
    await interaction.channel.delete()
    await new.edit(position=interaction.channel.position)
    await new.send(embed=black_embed(title="Channel Nuked"))

# ---- Scammer Lookup ----
@bot.tree.command(name="scammer", description="Lookup user information in the scammer database")
@app_commands.describe(user="The user to lookup (Member or ID)")
async def scammer(interaction: discord.Interaction, user: str):
    scammers = load_json(SCAMMERS_FILE)
    
    # Try to clean user ID if it's a mention
    clean_id = user.replace("<@", "").replace("!", "").replace(">", "")
    
    if clean_id not in scammers:
        await interaction.response.send_message(f"**UserID -** `{clean_id}` [<@{clean_id}>]\nNo more info sadly 😑", ephemeral=False)
        return
    
    data = scammers[clean_id]
    embed = black_embed(title="Scammer Information")
    
    for key, value in data.items():
        if key == "UserID":
            embed.add_field(name=f"> {key}", value=f"`{value}` [<@{value}>]", inline=False)
        else:
            embed.add_field(name=f"> {key}", value=f"`{value}`", inline=True)
    
    embed.set_footer(text=f"Database: {config['BOT_NAME']}")
    await interaction.response.send_message(embed=embed)

# ================= RUN BOT =================
if __name__ == "__main__":
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("Please set the MGMT_BOT_TOKEN environment variable.")
