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
EMOJI_LIVESTOCK = "<a:globe:1504764717451710484>" # Updated to animated globe as requested
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
async def load_json(file):
    if not os.path.exists(file):
        async with aiofiles.open(file, "w") as f:
            await f.write(json.dumps({}, indent=4))
    async with aiofiles.open(file, "r") as f:
        content = await f.read()
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {}

async def save_json(file, data):
    async with aiofiles.open(file, "w") as f:
        await f.write(json.dumps(data, indent=4))

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
async def get_accounts_by_tier(tier):
    accounts = await load_json(ACCOUNTS_FILE)
    return accounts.get(tier, [])

async def generate_account(tier):
    pool = await get_accounts_by_tier(tier)
    if not pool:
        return None
    
    # Pick random account
    account = random.choice(pool)
    
    # Remove used account
    all_accs = await load_json(ACCOUNTS_FILE)
    if account in all_accs.get(tier, []):
        all_accs[tier].remove(account)
        await save_json(ACCOUNTS_FILE, all_accs)
        return account
    return None

# ================= PERSISTENT VIEWS =================
class GeneratorView(discord.ui.View):
    def __init__(self, tier):
        super().__init__(timeout=None)
        self.tier = tier

    @discord.ui.button(label="Generate Account", style=discord.ButtonStyle.primary, custom_id="persistent_gen")
    async def generate_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        tier_role_id = EXOTIC_ROLE_ID if self.tier == "exotic" else PREMIUM_ROLE_ID
        emoji = EMOJI_EXOTIC if self.tier == "exotic" else EMOJI_PREMIUM
        color = 0xff6600 if self.tier == "exotic" else 0xffaa00
        
        if not discord.utils.get(interaction.user.roles, id=tier_role_id):
            await interaction.response.send_message(f"{EMOJI_CROSS} You need the correct role.", ephemeral=True)
            return
            
        can_gen, remaining = await check_cooldown_async(interaction.user.id, self.tier)
        if not can_gen:
            await interaction.response.send_message(f"{EMOJI_TIMER} Wait {remaining}s.", ephemeral=True)
            return
            
        acc = await generate_account(self.tier)
        if not acc:
            await interaction.response.send_message(f"{EMOJI_CROSS} Out of stock.", ephemeral=True)
            return
            
        set_cooldown(interaction.user.id)
        embed = discord.Embed(title=f"{emoji} {self.tier.capitalize()} Account", description=f"`{acc}`", color=color)
        try:
            await interaction.user.send(embed=embed)
            await interaction.response.send_message("Account sent to DMs!", ephemeral=True)
        except:
            await interaction.response.send_message(f"Your account: `{acc}` (Please enable DMs!)", ephemeral=True)

async def check_cooldown_async(user_id, tier="normal"):
    config = await load_json(CONFIG_FILE)
    cooldown_seconds = config.get("cooldown", DEFAULT_COOLDOWN)
    if tier == "exotic":
        cooldown_seconds = 60
    elif tier == "premium":
        cooldown_seconds = 30
    
    last_gen = cooldowns.get(user_id, 0)
    now = time.time()
    if now - last_gen < cooldown_seconds:
        remaining = int(cooldown_seconds - (now - last_gen))
        return False, remaining
    return True, 0

# ================= COMMANDS =================
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    print(f"Bot is currently in {len(bot.guilds)} servers:")
    for guild in bot.guilds:
        print(f" - {guild.name} (ID: {guild.id})")

    # Try Guild Sync (Instant)
    try:
        guild_obj = discord.Object(id=GUILD_ID)
        synced = await bot.tree.sync(guild=guild_obj)
        print(f"Synced {len(synced)} commands to guild {GUILD_ID}")
    except Exception as e:
        print(f"Guild sync failed: {e}")
        
    # Try Global Sync (Backup - can take up to 1 hour)
    try:
        synced_global = await bot.tree.sync()
        print(f"Synced {len(synced_global)} commands globally")
    except Exception as e:
        print(f"Global sync failed: {e}")

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
    
    accounts = await load_json(ACCOUNTS_FILE)
    accounts.setdefault(tier, []).extend(new_accounts)
    await save_json(ACCOUNTS_FILE, accounts)
    
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
    
    can_gen, remaining = await check_cooldown_async(user.id, tier)
    if not can_gen:
        await interaction.response.send_message(f"{EMOJI_TIMER} Cooldown! Try again in {remaining} seconds.", ephemeral=True)
        return
    
    account = await generate_account(tier)
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
    accounts = await load_json(ACCOUNTS_FILE)
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
    view = GeneratorView(tier="exotic")
    await channel.send(embed=embed, view=view)
    await interaction.response.send_message(f"{EMOJI_CHECK} Exotic panel posted.", ephemeral=True)

# /premium generate panel
@bot.tree.command(name="premium_generate_panel", description="Post the Premium Generator panel")
async def premium_generate_panel(interaction: discord.Interaction):
    if not (discord.utils.get(interaction.user.roles, id=OWNER_ROLE_ID) or discord.utils.get(interaction.user.roles, id=RESELLER_ROLE_ID)):
        await interaction.response.send_message(f"{EMOJI_CROSS} No permission.", ephemeral=True)
        return
    
    channel = bot.get_channel(PREMIUM_PANEL_CHANNEL_ID)
    if not channel:
        await interaction.response.send_message(f"{EMOJI_CROSS} Premium panel channel not found.", ephemeral=True)
        return
    
    embed = discord.Embed(title=f"{EMOJI_PREMIUM} **PREMIUM GENERATOR** {EMOJI_PREMIUM}", description="Generate **elite** accounts every 30 seconds. Click below!", color=0xffaa00)
    view = GeneratorView(tier="premium")
    await channel.send(embed=embed, view=view)
    await interaction.response.send_message(f"{EMOJI_CHECK} Premium panel posted.", ephemeral=True)

# /generate keys alias
@bot.tree.command(name="generate_keys", description="Generate an account (Alias)")
async def generate_keys(interaction: discord.Interaction):
    await generate(interaction)

# /setcooldown
@bot.tree.command(name="setcooldown", description="Set the global cooldown for normal tier")
async def setcooldown(interaction: discord.Interaction, seconds: int):
    if not discord.utils.get(interaction.user.roles, id=OWNER_ROLE_ID):
        await interaction.response.send_message(f"{EMOJI_CROSS} Owner only.", ephemeral=True)
        return
    config = await load_json(CONFIG_FILE)
    config["cooldown"] = seconds
    await save_json(CONFIG_FILE, config)
    await interaction.response.send_message(f"{EMOJI_CHECK} Cooldown set to {seconds}s.", ephemeral=False)

# /addowner
@bot.tree.command(name="addowner", description="Give Owner role to a user")
async def addowner(interaction: discord.Interaction, member: discord.Member):
    if not discord.utils.get(interaction.user.roles, id=OWNER_ROLE_ID):
        await interaction.response.send_message(f"{EMOJI_CROSS} Owner only.", ephemeral=True)
        return
    role = interaction.guild.get_role(OWNER_ROLE_ID)
    if role:
        await member.add_roles(role)
        await interaction.response.send_message(f"{EMOJI_CHECK} Added {member.mention} as Owner.")
    else:
        await interaction.response.send_message(f"{EMOJI_CROSS} Owner role not found.")

# /addreseller
@bot.tree.command(name="addreseller", description="Give Reseller role to a user")
async def addreseller(interaction: discord.Interaction, member: discord.Member):
    if not discord.utils.get(interaction.user.roles, id=OWNER_ROLE_ID):
        await interaction.response.send_message(f"{EMOJI_CROSS} Owner only.", ephemeral=True)
        return
    role = interaction.guild.get_role(RESELLER_ROLE_ID)
    if role:
        await member.add_roles(role)
        await interaction.response.send_message(f"{EMOJI_CHECK} Added {member.mention} as Reseller.")
    else:
        await interaction.response.send_message(f"{EMOJI_CROSS} Reseller role not found.")

if __name__ == "__main__":
    if not TOKEN:
        print("❌ Error: DISCORD_TOKEN environment variable not set.")
    else:
        bot.run(TOKEN)
