import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import os
import aiofiles
import asyncio
import random
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ================= CONFIGURATION =================
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = 1504472803137814638  # Server ID

# Channel IDs
EXOTIC_PANEL_CHANNEL_ID = 1504498750155002042  
PREMIUM_PANEL_CHANNEL_ID = 1504474305851953202

# Role IDs
OWNER_ROLE_ID = 1504474785906950346
RESELLER_ROLE_ID = 1504763361169244211
EXOTIC_ROLE_ID = 1504763516803092512
PREMIUM_ROLE_ID = 1504763571362336849

# Emojis
EMOJI_CHECK = "<a:Clock1:1504765854133260340>"
EMOJI_CROSS = "<a:20819bloodrip:1504766150670815262>"
EMOJI_KEY = "<a:key:1504765531629027338>"
EMOJI_LIVESTOCK = "🌎" # Updated to the pink globe emoji as requested
EMOJI_TIMER = "<a:Clock1:1504765854133260340>"
EMOJI_STAR = "<a:81437star:1504766360947916930>"
EMOJI_PREMIUM = "<a:Monster52:1504766603122966609>"
EMOJI_EXOTIC = "<a:Monster52:1504766603122966609>"

# File paths
ACCOUNTS_FILE = "accounts.json"
USERS_FILE = "users.json"
CONFIG_FILE = "config.json"

# Default cooldown (seconds)
DEFAULT_COOLDOWN = 60

# ================= DATA MANAGEMENT =================
def load_json(file):
    if not os.path.exists(file):
        with open(file, "w") as f:
            json.dump({}, f)
    with open(file, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)

# ================= BOT SETUP =================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ================= COOLDOWN HANDLER =================
cooldowns = {}

def check_cooldown(user_id, tier="normal"):
    config = load_json(CONFIG_FILE)
    cooldown_seconds = config.get("cooldown", DEFAULT_COOLDOWN)
    if tier == "exotic":
        cooldown_seconds = 60  # 1 minute
    elif tier == "premium":
        cooldown_seconds = 30   # 30 seconds
    
    last_gen = cooldowns.get(user_id, 0)
    now = time.time()
    if now - last_gen < cooldown_seconds:
        remaining = int(cooldown_seconds - (now - last_gen))
        return False, remaining
    return True, 0

def set_cooldown(user_id):
    cooldowns[user_id] = time.time()

# ================= ACCOUNT GENERATION =================
def get_accounts_by_tier(tier):
    accounts = load_json(ACCOUNTS_FILE)
    return accounts.get(tier, [])

def generate_account(tier):
    pool = get_accounts_by_tier(tier)
    if not pool:
        return None
    
    # Pick random account
    account = random.choice(pool)
    
    # Remove used account
    all_accs = load_json(ACCOUNTS_FILE)
    if account in all_accs.get(tier, []):
        all_accs[tier].remove(account)
        save_json(ACCOUNTS_FILE, all_accs)
        return account
    return None

# ================= COMMANDS =================
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        print(f"Synced {len(synced)} commands to guild {GUILD_ID}")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

# Admin: /restock
@bot.tree.command(name="restock", description="Restock accounts via .txt file")
@app_commands.describe(tier="The tier to restock (normal/exotic/premium)", file="The .txt file containing accounts")
async def restock(interaction: discord.Interaction, tier: str, file: discord.Attachment):
    user = interaction.user
    if not (discord.utils.get(user.roles, id=OWNER_ROLE_ID) or discord.utils.get(user.roles, id=RESELLER_ROLE_ID)):
        await interaction.response.send_message(f"{EMOJI_CROSS} You need Owner or Reseller role.", ephemeral=True)
        return
    
    if tier not in ["normal", "exotic", "premium"]:
        await interaction.response.send_message(f"{EMOJI_CROSS} Tier must be `normal`, `exotic`, or `premium`", ephemeral=True)
        return
    
    if not file.filename.endswith(".txt"):
        await interaction.response.send_message(f"{EMOJI_CROSS} Please upload a .txt file.", ephemeral=True)
        return
    
    content = await file.read()
    lines = content.decode("utf-8").splitlines()
    new_accounts = [line.strip() for line in lines if line.strip()]
    
    if not new_accounts:
        await interaction.response.send_message(f"{EMOJI_CROSS} File is empty.", ephemeral=True)
        return
    
    accounts = load_json(ACCOUNTS_FILE)
    accounts.setdefault(tier, []).extend(new_accounts)
    save_json(ACCOUNTS_FILE, accounts)
    
    await interaction.response.send_message(f"{EMOJI_CHECK} Restocked `{len(new_accounts)}` accounts into **{tier}** tier.", ephemeral=False)

# /generate
@bot.tree.command(name="generate", description="Generate an account")
async def generate(interaction: discord.Interaction):
    user = interaction.user
    tier = "normal"
    if discord.utils.get(user.roles, id=PREMIUM_ROLE_ID):
        tier = "premium"
    elif discord.utils.get(user.roles, id=EXOTIC_ROLE_ID):
        tier = "exotic"
    
    can_gen, remaining = check_cooldown(user.id, tier)
    if not can_gen:
        await interaction.response.send_message(f"{EMOJI_TIMER} Cooldown! Try again in {remaining} seconds.", ephemeral=True)
        return
    
    account = generate_account(tier)
    if not account:
        await interaction.response.send_message(f"{EMOJI_CROSS} No {tier} accounts left! Ask an admin to `/restock`.", ephemeral=True)
        return
    
    set_cooldown(user.id)
    embed = discord.Embed(title=f"{EMOJI_KEY} Account Generated ({tier.upper()})", color=0x00ff00)
    embed.add_field(name="Account", value=f"`{account}`", inline=False)
    embed.set_footer(text=f"Requested by {user.display_name}")
    
    try:
        await user.send(embed=embed)
        await interaction.response.send_message(f"{EMOJI_CHECK} Account sent to your DMs!", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message(f"{EMOJI_CROSS} I couldn't DM you! Please enable DMs from server members.", ephemeral=True)

# /livestock
@bot.tree.command(name="livestock", description="Show available account counts")
async def livestock(interaction: discord.Interaction):
    accounts = load_json(ACCOUNTS_FILE)
    normal = len(accounts.get("normal", []))
    exotic = len(accounts.get("exotic", []))
    premium = len(accounts.get("premium", []))
    
    embed = discord.Embed(title=f"{EMOJI_LIVESTOCK} **Livestock Report**", color=0x3498db)
    embed.add_field(name="Normal Accounts", value=f"`{normal}`", inline=True)
    embed.add_field(name="Exotic Accounts", value=f"`{exotic}`", inline=True)
    embed.add_field(name="Premium Accounts", value=f"`{premium}`", inline=True)
    await interaction.response.send_message(embed=embed, ephemeral=False)

# /exoticpanel
@bot.tree.command(name="exoticpanel", description="Post the Exotic Generator panel")
async def exoticpanel(interaction: discord.Interaction):
    if not (discord.utils.get(interaction.user.roles, id=OWNER_ROLE_ID) or discord.utils.get(interaction.user.roles, id=RESELLER_ROLE_ID)):
        await interaction.response.send_message(f"{EMOJI_CROSS} No permission.", ephemeral=True)
        return
    
    channel = bot.get_channel(EXOTIC_PANEL_CHANNEL_ID)
    if not channel:
        await interaction.response.send_message(f"{EMOJI_CROSS} Exotic panel channel not found.", ephemeral=True)
        return
    
    embed = discord.Embed(title=f"{EMOJI_EXOTIC} **EXOTIC GENERATOR** {EMOJI_EXOTIC}", description="Generate high-quality accounts every **1 minute**. Click below!", color=0xff6600)
    view = discord.ui.View()
    view.add_item(discord.ui.Button(label="Generate Exotic Account", style=discord.ButtonStyle.primary, custom_id="generate_exotic"))
    await channel.send(embed=embed, view=view)
    await interaction.response.send_message(f"{EMOJI_CHECK} Exotic panel posted.", ephemeral=True)

# /premiumpanel
@bot.tree.command(name="premiumpanel", description="Post the Premium Generator panel")
async def premiumpanel(interaction: discord.Interaction):
    if not (discord.utils.get(interaction.user.roles, id=OWNER_ROLE_ID) or discord.utils.get(interaction.user.roles, id=RESELLER_ROLE_ID)):
        await interaction.response.send_message(f"{EMOJI_CROSS} No permission.", ephemeral=True)
        return
    
    channel = bot.get_channel(PREMIUM_PANEL_CHANNEL_ID)
    if not channel:
        await interaction.response.send_message(f"{EMOJI_CROSS} Premium panel channel not found.", ephemeral=True)
        return
    
    embed = discord.Embed(title=f"{EMOJI_PREMIUM} **PREMIUM GENERATOR** {EMOJI_PREMIUM}", description="Generate **elite** accounts every 30 seconds. Click below!", color=0xffaa00)
    view = discord.ui.View()
    view.add_item(discord.ui.Button(label="Generate Premium Account", style=discord.ButtonStyle.success, custom_id="generate_premium"))
    await channel.send(embed=embed, view=view)
    await interaction.response.send_message(f"{EMOJI_CHECK} Premium panel posted.", ephemeral=True)

# Button Handlers
@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.component:
        custom_id = interaction.data.get("custom_id")
        if custom_id == "generate_exotic":
            if not discord.utils.get(interaction.user.roles, id=EXOTIC_ROLE_ID):
                await interaction.response.send_message(f"{EMOJI_CROSS} You need the Exotic role.", ephemeral=True)
                return
            can_gen, remaining = check_cooldown(interaction.user.id, "exotic")
            if not can_gen:
                await interaction.response.send_message(f"{EMOJI_TIMER} Wait {remaining}s.", ephemeral=True)
                return
            acc = generate_account("exotic")
            if not acc:
                await interaction.response.send_message(f"{EMOJI_CROSS} Out of stock.", ephemeral=True)
                return
            set_cooldown(interaction.user.id)
            embed = discord.Embed(title=f"{EMOJI_EXOTIC} Exotic Account", description=f"`{acc}`", color=0xff6600)
            try:
                await interaction.user.send(embed=embed)
                await interaction.response.send_message("Account sent to DMs!", ephemeral=True)
            except:
                await interaction.response.send_message(f"Your account: `{acc}` (Please enable DMs next time!)", ephemeral=True)
        
        elif custom_id == "generate_premium":
            if not discord.utils.get(interaction.user.roles, id=PREMIUM_ROLE_ID):
                await interaction.response.send_message(f"{EMOJI_CROSS} You need the Premium role.", ephemeral=True)
                return
            can_gen, remaining = check_cooldown(interaction.user.id, "premium")
            if not can_gen:
                await interaction.response.send_message(f"{EMOJI_TIMER} Wait {remaining}s.", ephemeral=True)
                return
            acc = generate_account("premium")
            if not acc:
                await interaction.response.send_message(f"{EMOJI_CROSS} Out of stock.", ephemeral=True)
                return
            set_cooldown(interaction.user.id)
            embed = discord.Embed(title=f"{EMOJI_PREMIUM} Premium Account", description=f"`{acc}`", color=0xffaa00)
            try:
                await interaction.user.send(embed=embed)
                await interaction.response.send_message("Account sent to DMs!", ephemeral=True)
            except:
                await interaction.response.send_message(f"Your account: `{acc}` (Please enable DMs next time!)", ephemeral=True)

if __name__ == "__main__":
    if not TOKEN:
        print("❌ Error: DISCORD_TOKEN environment variable not set.")
    else:
        bot.run(TOKEN)
