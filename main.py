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
EMOJI_PREMIUM = "<a:globe:1504764717451710484>"
EMOJI_EXOTIC = "<a:Monster52:1504766603122966609>"

# File paths
ACCOUNTS_FILE = "accounts.json"
KEYS_FILE = "keys.json"
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
        user = interaction.user
        channel = interaction.channel
        
        # Enforce Channel Lock
        if self.tier == "exotic" and "exotic-gen" not in channel.name:
            await interaction.response.send_message(f"{EMOJI_CROSS} This button only works in the **exotic-gen** channel!", ephemeral=True)
            return
        if self.tier == "premium" and "premium-gen" not in channel.name:
            await interaction.response.send_message(f"{EMOJI_CROSS} This button only works in the **premium-gen** channel!", ephemeral=True)
            return

        # Enforce Role Lock
        role_id = EXOTIC_ROLE_ID if self.tier == "exotic" else PREMIUM_ROLE_ID
        if not discord.utils.get(user.roles, id=role_id):
            await interaction.response.send_message(f"{EMOJI_CROSS} You must have **{self.tier.capitalize()} Gen** role to use this!", ephemeral=True)
            return
            
        can_gen, remaining = await check_cooldown_async(user.id, self.tier)
        if not can_gen:
            await interaction.response.send_message(f"{EMOJI_TIMER} Wait {remaining}s.", ephemeral=True)
            return
            
        # Stock Check
        pool = await get_accounts_by_tier(self.tier)
        if not pool:
            await interaction.response.send_message(f"Restock needed.", ephemeral=True)
            return

        acc = await generate_account(self.tier)
        set_cooldown(user.id)
        
        emoji = EMOJI_EXOTIC if self.tier == "exotic" else EMOJI_PREMIUM
        enjoy_msg = f"Enjoy Exotic gen" if self.tier == "exotic" else "Enjoy Premium gen"
        
        embed = discord.Embed(title=f"{emoji} {self.tier.capitalize()} Gen", description=f"`{acc}`", color=0x00ff00)
        embed.set_footer(text=enjoy_msg)
        
        try:
            await user.send(embed=embed)
            await interaction.response.send_message("Account sent to DMs!", ephemeral=True)
        except:
            await interaction.response.send_message(f"Your account: `{acc}`\n{enjoy_msg}", ephemeral=True)

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

# ================= TASKS =================
@tasks.loop(minutes=30)
async def check_expirations():
    data = await load_json(KEYS_FILE)
    users = data.get("users", {})
    changed = False
    
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        return

    now = datetime.now().timestamp()
    to_remove = []
    
    for user_id, info in users.items():
        expires = info.get("expires")
        if expires == "lifetime":
            continue
            
        if now > expires:
            to_remove.append(user_id)
            
    for user_id in to_remove:
        member = guild.get_member(int(user_id))
        tier = users[user_id]["tier"]
        role_id = EXOTIC_ROLE_ID if tier == "exotic" else PREMIUM_ROLE_ID
        role = guild.get_role(role_id)
        
        if member and role:
            try:
                await member.remove_roles(role)
                print(f"Removed {tier} role from {member.name} (Expired)")
                # Notify user
                try:
                    await member.send(f"Your **{tier.capitalize()} Gen** membership has expired. Visit the server to renew!")
                except:
                    pass
            except:
                pass
        
        del users[user_id]
        changed = True
        
    if changed:
        data["users"] = users
        await save_json(KEYS_FILE, data)

# ================= COMMANDS =================
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    if not check_expirations.is_running():
        check_expirations.start()
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
    channel = interaction.channel
    
    # Identify tier based on channel or role
    tier = None
    if "exotic-gen" in channel.name:
        tier = "exotic"
    elif "premium-gen" in channel.name:
        tier = "premium"
    else:
        await interaction.response.send_message(f"{EMOJI_CROSS} You can only use this command in the generator channels!", ephemeral=True)
        return

    # Check for correct role
    role_id = EXOTIC_ROLE_ID if tier == "exotic" else PREMIUM_ROLE_ID
    if not discord.utils.get(user.roles, id=role_id):
        await interaction.response.send_message(f"{EMOJI_CROSS} You must have **{tier.capitalize()} Gen** to use this channel!", ephemeral=True)
        return
    
    can_gen, remaining = await check_cooldown_async(user.id, tier)
    if not can_gen:
        await interaction.response.send_message(f"{EMOJI_TIMER} Cooldown! Try again in {remaining} seconds.", ephemeral=True)
        return
    
    # Stock Check
    pool = await get_accounts_by_tier(tier)
    if not pool:
        await interaction.response.send_message(f"Restock needed.", ephemeral=True)
        return
        
    account = await generate_account(tier)
    set_cooldown(user.id)
    
    emoji = EMOJI_EXOTIC if tier == "exotic" else EMOJI_PREMIUM
    enjoy_msg = f"Enjoy Exotic gen" if tier == "exotic" else "Enjoy Premium gen"
    
    embed = discord.Embed(title=f"{emoji} {tier.capitalize()} Gen", description=f"`{account}`", color=0x00ff00)
    embed.set_footer(text=enjoy_msg)
    
    try:
        await user.send(embed=embed)
        await interaction.response.send_message(f"{EMOJI_CHECK} Account sent to your DMs!", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message(f"Your account: `{account}`\n{enjoy_msg}", ephemeral=True)

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
    
    channel = interaction.channel
    embed = discord.Embed(title=f"{EMOJI_EXOTIC} **EXOTIC GENERATOR** {EMOJI_EXOTIC}", description="Generate high-quality accounts every **1 minute**. Click below!", color=0xff6600)
    view = GeneratorView(tier="exotic")
    await channel.send(embed=embed, view=view)
    await interaction.response.send_message(f"{EMOJI_CHECK} Exotic panel posted in {channel.mention}.", ephemeral=True)

# /premium generate panel
@bot.tree.command(name="premium_generate_panel", description="Post the Premium Generator panel")
async def premium_generate_panel(interaction: discord.Interaction):
    if not (discord.utils.get(interaction.user.roles, id=OWNER_ROLE_ID) or discord.utils.get(interaction.user.roles, id=RESELLER_ROLE_ID)):
        await interaction.response.send_message(f"{EMOJI_CROSS} No permission.", ephemeral=True)
        return
    
    channel = interaction.channel
    embed = discord.Embed(title=f"{EMOJI_PREMIUM} **PREMIUM GENERATOR** {EMOJI_PREMIUM}", description="Generate **elite** accounts every 30 seconds. Click below!", color=0xffaa00)
    view = GeneratorView(tier="premium")
    await channel.send(embed=embed, view=view)
    await interaction.response.send_message(f"{EMOJI_CHECK} Premium panel posted in {channel.mention}.", ephemeral=True)

# /genkey
@bot.tree.command(name="genkey", description="Generate a membership key (Owner/Reseller)")
@app_commands.describe(tier="exotic or premium", duration="1d, 1w, 1m, 1y, or lifetime")
async def genkey(interaction: discord.Interaction, tier: str, duration: str):
    if not (discord.utils.get(interaction.user.roles, id=OWNER_ROLE_ID) or discord.utils.get(interaction.user.roles, id=RESELLER_ROLE_ID)):
        await interaction.response.send_message(f"{EMOJI_CROSS} No permission.", ephemeral=True)
        return
    
    if tier not in ["exotic", "premium"]:
        await interaction.response.send_message(f"{EMOJI_CROSS} Tier must be `exotic` or `premium`.", ephemeral=True)
        return
    
    if duration not in ["1d", "1w", "1m", "1y", "lifetime"]:
        await interaction.response.send_message(f"{EMOJI_CROSS} Invalid duration.", ephemeral=True)
        return
        
    key = f"KXRRIED-{tier.upper()}-" + "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=8))
    
    data = await load_json(KEYS_FILE)
    data.setdefault("keys", {})[key] = {"tier": tier, "duration": duration}
    await save_json(KEYS_FILE, data)
    
    embed = discord.Embed(title=f"{EMOJI_KEY} Key Generated", color=0x00ff00)
    embed.add_field(name="Key", value=f"`{key}`", inline=False)
    embed.add_field(name="Tier", value=tier.capitalize(), inline=True)
    embed.add_field(name="Duration", value=duration, inline=True)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# /redeem
@bot.tree.command(name="redeem", description="Redeem a membership key")
async def redeem(interaction: discord.Interaction, key: str):
    data = await load_json(KEYS_FILE)
    keys = data.get("keys", {})
    
    if key not in keys:
        await interaction.response.send_message(f"{EMOJI_CROSS} Invalid or expired key.", ephemeral=True)
        return
        
    key_info = keys[key]
    tier = key_info["tier"]
    duration = key_info["duration"]
    
    # Calculate expiration
    now = datetime.now()
    if duration == "1d": expires = (now + timedelta(days=1)).timestamp()
    elif duration == "1w": expires = (now + timedelta(weeks=1)).timestamp()
    elif duration == "1m": expires = (now + timedelta(days=30)).timestamp()
    elif duration == "1y": expires = (now + timedelta(days=365)).timestamp()
    else: expires = "lifetime"
    
    # Give Role
    role_id = EXOTIC_ROLE_ID if tier == "exotic" else PREMIUM_ROLE_ID
    role = interaction.guild.get_role(role_id)
    if not role:
        await interaction.response.send_message(f"{EMOJI_CROSS} Role not found on server.", ephemeral=True)
        return
        
    await interaction.user.add_roles(role)
    
    # Save User
    data.setdefault("users", {})[str(interaction.user.id)] = {"tier": tier, "expires": expires}
    del data["keys"][key]
    await save_json(KEYS_FILE, data)
    
    embed = discord.Embed(title=f"{EMOJI_CHECK} Key Redeemed!", description=f"You now have **{tier.capitalize()}** membership.", color=0x00ff00)
    embed.add_field(name="Expires", value="Never" if expires == "lifetime" else f"<t:{int(expires)}:R>", inline=False)
    await interaction.response.send_message(embed=embed)

# /generate keys alias (Fixed to redirect to genkey or generate as needed)
@bot.tree.command(name="generate_keys", description="Generate a membership key (Staff Only)")
async def generate_keys(interaction: discord.Interaction, tier: str, duration: str):
    await genkey(interaction, tier, duration)

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
