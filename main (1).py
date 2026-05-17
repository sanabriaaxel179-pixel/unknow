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

# ================= CONFIGURATION =================
TOKEN = "YOUR_BOT_TOKEN"
GUILD_ID = 1504472803137814638  # Replace with your server ID

# Channel IDs
EXOTIC_PANEL_CHANNEL_ID = 1504498750155002042  # Channel where /exoticpanel sends embed
PREMIUM_PANEL_CHANNEL_ID = 1504474305851953202
DATABASE_CHANNEL_ID = 1504501876920418327      # Channel for storing accounts.json backups

# Role IDs (get from Discord by right-clicking role -> Copy ID)
OWNER_ROLE_ID = 1504474785906950346
RESELLER_ROLE_ID = 1504763361169244211
EXOTIC_ROLE_ID = 1504763516803092512
PREMIUM_ROLE_ID = 1504763571362336849

# Emoji IDs (use custom nitro emojis, format: <:emoji_name:EMOJI_ID>)
EMOJI_CHECK = "<a:Clock1:1504765854133260340>"
EMOJI_CROSS = "<a:20819bloodrip:1504766150670815262>"
EMOJI_KEY = "<a:key:1504765531629027338>"
EMOJI_LIVESTOCK = "<a:globe:1504764717451710484>"
EMOJI_TIMER = "<a:Clock1:1504765854133260340>"
EMOJI_STAR = "<a:81437star:1504766360947916930>"
EMOJI_PREMIUM = "<a:Monster52:1504766603122966609>"
EMOJI_EXOTIC = "<a:Monster52:1504766603122966609>"

# File paths
# If using Railway, set DATA_DIR in your environment variables to your volume mount path (e.g., /app/data)
DATA_DIR = os.getenv("DATA_DIR", ".")
ACCOUNTS_FILE = os.path.join(DATA_DIR, "accounts.json")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")

# Default cooldown (seconds)
DEFAULT_COOLDOWN = 60

# ================= DATA MANAGEMENT =================
def load_json(file):
    if not os.path.exists(file):
        with open(file, "w") as f:
            json.dump({}, f)
    with open(file, "r") as f:
        return json.load(f)

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)

# ================= BOT SETUP =================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ================= DISCORD DATABASE (BACKUP SYSTEM) =================
async def backup_data():
    """Uploads the local accounts.json to the database channel."""
    if not DATABASE_CHANNEL_ID: return
    channel = bot.get_channel(DATABASE_CHANNEL_ID)
    if channel:
        try:
            await channel.send(f"Database Backup - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", file=discord.File(ACCOUNTS_FILE, "accounts.json"))
        except Exception as e:
            print(f"Failed to backup database: {e}")

async def load_data_from_discord():
    """Downloads the latest accounts.json from the database channel."""
    if not DATABASE_CHANNEL_ID: return
    channel = bot.get_channel(DATABASE_CHANNEL_ID)
    if channel:
        try:
            async for msg in channel.history(limit=20):
                if msg.attachments and msg.attachments[0].filename == "accounts.json":
                    await msg.attachments[0].save(ACCOUNTS_FILE)
                    print("✅ Database successfully loaded from Discord System Channel!")
                    return
            print("⚠️ No previous database found in Discord. Starting fresh.")
        except Exception as e:
            print(f"Failed to load database from Discord: {e}")

class ConfirmView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=30)
        self.user_id = user_id
        self.value = None

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your interaction.", ephemeral=True)
            return
        self.value = True
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Not your interaction.", ephemeral=True)
            return
        self.value = False
        self.stop()

# ================= COOLDOWN HANDLER =================
cooldowns = {}

def check_cooldown(user_id, tier="normal"):
    config = load_json(CONFIG_FILE)
    cooldown_seconds = config.get("cooldown", DEFAULT_COOLDOWN)
    if tier == "exotic":
        cooldown_seconds = 50  # 50 seconds
    elif tier == "premium":
        cooldown_seconds = 60   # 1 minute
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
    if tier == "premium":
        return accounts.get("premium", [])
    elif tier == "exotic":
        return accounts.get("exotic", [])
    else:
        return accounts.get("normal", [])

async def generate_account(tier):
    pool = get_accounts_by_tier(tier)
    if not pool:
        return None
    # simulate "better quality" for premium/exotic: pick from top 30%
    if tier == "premium" and len(pool) > 3:
        pool = pool[:max(3, len(pool)//3)]
    elif tier == "exotic" and len(pool) > 2:
        pool = pool[:max(2, len(pool)//2)]
    if not pool:
        return None
    account = random.choice(pool)
    
    # remove used account safely
    all_accs = load_json(ACCOUNTS_FILE)
    if tier in all_accs and account in all_accs[tier]:
        all_accs[tier].remove(account)
        save_json(ACCOUNTS_FILE, all_accs)
        await backup_data()
        return account
    else:
        # If the account was somehow already removed, return None to avoid crashing
        return None

# ================= COMMANDS =================
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    await load_data_from_discord()
    try:
        synced = await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(e)

# ---- Admin: /restock ----
@bot.tree.command(name="restock", description="Restock accounts via .txt file (Owner/Reseller only)")
@app_commands.default_permissions(administrator=False)
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
    await backup_data()
    await interaction.response.send_message(f"{EMOJI_CHECK} Restocked `{len(new_accounts)}` accounts into **{tier}** tier.", ephemeral=False)

# ---- /generate (for members) ----
@bot.tree.command(name="generate", description="Generate a Rainbow Six Siege account")
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
    
    # Set cooldown immediately to prevent double-click spam
    set_cooldown(user.id)
    
    account = await generate_account(tier)
    if not account:
        # Refund the cooldown if out of stock
        cooldowns[user.id] = 0
        await interaction.response.send_message(f"{EMOJI_CROSS} No {tier} accounts left! Ask an admin to `/restock`.", ephemeral=True)
        return
        
    embed = discord.Embed(title=f"{EMOJI_KEY} Account Generated ({tier.upper()})", color=0x00ff00)
    embed.add_field(name="Account", value=f"`{account}`", inline=False)
    embed.set_footer(text=f"Requested by {user.display_name}")
    await interaction.response.send_message(embed=embed, ephemeral=False)

# ---- /exoticpanel ----
@bot.tree.command(name="exoticpanel", description="Post the Exotic Generator panel (Owner/Reseller only)")
@app_commands.default_permissions(administrator=False)
async def exoticpanel(interaction: discord.Interaction):
    if not (discord.utils.get(interaction.user.roles, id=OWNER_ROLE_ID) or discord.utils.get(interaction.user.roles, id=RESELLER_ROLE_ID)):
        await interaction.response.send_message(f"{EMOJI_CROSS} No permission.", ephemeral=True)
        return
    channel = bot.get_channel(EXOTIC_PANEL_CHANNEL_ID)
    if not channel:
        await interaction.response.send_message(f"{EMOJI_CROSS} Exotic panel channel not found.", ephemeral=True)
        return
    embed = discord.Embed(title=f"{EMOJI_EXOTIC} **EXOTIC GENERATOR** {EMOJI_EXOTIC}", description="Generate high-quality R6 accounts every **50 seconds**. Click below!", color=0xff6600)
    view = discord.ui.View()
    view.add_item(discord.ui.Button(label="Generate Exotic Account", style=discord.ButtonStyle.primary, custom_id="generate_exotic"))
    await channel.send(embed=embed, view=view)
    await interaction.response.send_message(f"{EMOJI_CHECK} Exotic panel posted in <#{EXOTIC_PANEL_CHANNEL_ID}>.", ephemeral=True)

# ---- /premium generate panel ----
@bot.tree.command(name="premium_generate_panel", description="Post the Premium Generator panel (Owner/Reseller only)")
async def premium_generate_panel(interaction: discord.Interaction):
    if not (discord.utils.get(interaction.user.roles, id=OWNER_ROLE_ID) or discord.utils.get(interaction.user.roles, id=RESELLER_ROLE_ID)):
        await interaction.response.send_message(f"{EMOJI_CROSS} No permission.", ephemeral=True)
        return
    channel = bot.get_channel(PREMIUM_PANEL_CHANNEL_ID)
    if not channel:
        await interaction.response.send_message(f"{EMOJI_CROSS} Premium panel channel not found.", ephemeral=True)
        return
    embed = discord.Embed(title=f"{EMOJI_PREMIUM} **PREMIUM GENERATOR** {EMOJI_PREMIUM}", description="Generate **elite** R6 accounts every **1 minute**. Ultra-fast & best quality.", color=0xffaa00)
    view = discord.ui.View()
    view.add_item(discord.ui.Button(label="Generate Premium Account", style=discord.ButtonStyle.success, custom_id="generate_premium"))
    await channel.send(embed=embed, view=view)
    await interaction.response.send_message(f"{EMOJI_CHECK} Premium panel posted in <#{PREMIUM_PANEL_CHANNEL_ID}>.", ephemeral=True)

# ---- /livestock ----
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

# ---- /setcooldown ----
@bot.tree.command(name="setcooldown", description="Set global cooldown for normal tier (seconds)")
async def setcooldown(interaction: discord.Interaction, seconds: int):
    if not discord.utils.get(interaction.user.roles, id=OWNER_ROLE_ID):
        await interaction.response.send_message(f"{EMOJI_CROSS} Owner only.", ephemeral=True)
        return
    if seconds < 5:
        await interaction.response.send_message(f"{EMOJI_CROSS} Cooldown must be at least 5 seconds.", ephemeral=True)
        return
    config = load_json(CONFIG_FILE)
    config["cooldown"] = seconds
    save_json(CONFIG_FILE, config)
    await interaction.response.send_message(f"{EMOJI_CHECK} Global cooldown set to `{seconds}` seconds for normal tier.", ephemeral=False)

# ---- /addowner & /addreseller ----
@bot.tree.command(name="addowner", description="Give Owner role to a user")
async def addowner(interaction: discord.Interaction, member: discord.Member):
    if not discord.utils.get(interaction.user.roles, id=OWNER_ROLE_ID):
        await interaction.response.send_message(f"{EMOJI_CROSS} Only current Owners can add new Owners.", ephemeral=True)
        return
    role = interaction.guild.get_role(OWNER_ROLE_ID)
    if not role:
        await interaction.response.send_message(f"{EMOJI_CROSS} Owner role not found.", ephemeral=True)
        return
    await member.add_roles(role)
    await interaction.response.send_message(f"{EMOJI_CHECK} Added `{member.name}` as Owner.", ephemeral=False)

@bot.tree.command(name="addreseller", description="Give Reseller role to a user")
async def addreseller(interaction: discord.Interaction, member: discord.Member):
    if not discord.utils.get(interaction.user.roles, id=OWNER_ROLE_ID):
        await interaction.response.send_message(f"{EMOJI_CROSS} Owner only.", ephemeral=True)
        return
    role = interaction.guild.get_role(RESELLER_ROLE_ID)
    if not role:
        await interaction.response.send_message(f"{EMOJI_CROSS} Reseller role not found.", ephemeral=True)
        return
    await member.add_roles(role)
    await interaction.response.send_message(f"{EMOJI_CHECK} Added `{member.name}` as Reseller.", ephemeral=False)

# ---- Extra: /generate keys (alias for /generate with extra embed style) ----
@bot.tree.command(name="generate_keys", description="Alias for /generate")
async def generate_keys(interaction: discord.Interaction):
    await generate(interaction)

# ================= BUTTON HANDLERS =================
@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.component:
        custom_id = interaction.data.get("custom_id")
        if custom_id == "generate_exotic":
            if not discord.utils.get(interaction.user.roles, id=EXOTIC_ROLE_ID):
                await interaction.response.send_message(f"{EMOJI_CROSS} You need the `Exotic Member` role to use this panel.", ephemeral=True)
                return
            can_gen, remaining = check_cooldown(interaction.user.id, "exotic")
            if not can_gen:
                await interaction.response.send_message(f"{EMOJI_TIMER} Exotic cooldown: {remaining} seconds left.", ephemeral=True)
                return
            
            # Set cooldown immediately to prevent double-click spam
            set_cooldown(interaction.user.id)
            
            acc = await generate_account("exotic")
            if not acc:
                cooldowns[interaction.user.id] = 0 # Refund cooldown
                await interaction.response.send_message(f"{EMOJI_CROSS} No exotic accounts left. Contact staff.", ephemeral=True)
                return
            
            embed = discord.Embed(title=f"{EMOJI_EXOTIC} Exotic Account", description=f"`{acc}`", color=0xff6600)
            await interaction.response.send_message(embed=embed, ephemeral=False)
            
        elif custom_id == "generate_premium":
            if not discord.utils.get(interaction.user.roles, id=PREMIUM_ROLE_ID):
                await interaction.response.send_message(f"{EMOJI_CROSS} You need the `Premium Member` role to use this panel.", ephemeral=True)
                return
                
            can_gen, remaining = check_cooldown(interaction.user.id, "premium")
            if not can_gen:
                await interaction.response.send_message(f"{EMOJI_TIMER} Premium cooldown: {remaining} seconds left.", ephemeral=True)
                return
            
            # Set cooldown immediately to prevent double-click spam
            set_cooldown(interaction.user.id)
            
            acc = await generate_account("premium")
            if not acc:
                cooldowns[interaction.user.id] = 0 # Refund cooldown
                await interaction.response.send_message(f"{EMOJI_CROSS} No premium accounts left.", ephemeral=True)
                return
            
            embed = discord.Embed(title=f"{EMOJI_PREMIUM} Premium Account", description=f"`{acc}`", color=0xffaa00)
            await interaction.response.send_message(embed=embed, ephemeral=False)

# ================= RUN BOT =================
if __name__ == "__main__":
    bot.run(TOKEN)