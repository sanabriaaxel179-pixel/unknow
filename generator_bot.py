import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import random
import time
from datetime import datetime

# ================= CONFIGURATION =================
CONFIG_FILE = "config.json"
ACCOUNTS_FILE = "accounts.json"
TOKEN = os.getenv("GEN_BOT_TOKEN")

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
def is_co_owner_plus(user):
    roles = [config["ROLES"]["OWNER"], config["ROLES"]["CO_OWNER"]]
    return any(discord.utils.get(user.roles, id=r) for r in roles)

def black_embed(title=None, description=None):
    return discord.Embed(title=title, description=description, color=config.get("THEME_COLOR", 0))

# ================= COOLDOWN HANDLER =================
cooldowns = {}

def check_cooldown(user_id, tier="normal"):
    cooldown_seconds = config.get("DEFAULT_COOLDOWN", 0)
    if tier == "exotic":
        cooldown_seconds = 50
    elif tier == "premium":
        cooldown_seconds = 60
        
    last_gen = cooldowns.get(user_id, 0)
    now = time.time()
    if now - last_gen < cooldown_seconds:
        remaining = int(cooldown_seconds - (now - last_gen))
        return False, remaining
    return True, 0

def set_cooldown(user_id):
    cooldowns[user_id] = time.time()

# ================= ACCOUNT GENERATION =================
def generate_account(tier):
    accounts = load_json(ACCOUNTS_FILE)
    pool = accounts.get(tier, [])
    if not pool: return None
    
    if tier == "premium" and len(pool) > 3:
        pool = pool[:max(3, len(pool)//3)]
    elif tier == "exotic" and len(pool) > 2:
        pool = pool[:max(2, len(pool)//2)]
        
    account = random.choice(pool)
    accounts[tier].remove(account)
    save_json(ACCOUNTS_FILE, accounts)
    return account

# ================= COMMANDS =================
@bot.event
async def on_ready():
    print(f"✅ Generator Bot logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands globally")
    except Exception as e:
        print(f"Sync error: {e}")

# ---- Admin: /restock ----
@bot.tree.command(name="restock", description="Restock accounts via .txt file")
async def restock(interaction: discord.Interaction, tier: str, file: discord.Attachment):
    if not (is_co_owner_plus(interaction.user) or discord.utils.get(interaction.user.roles, id=config["ROLES"]["RESELLER"])):
        await interaction.response.send_message(f"{config['EMOJIS']['CROSS']} No permission.", ephemeral=True)
        return
    if tier not in ["normal", "exotic", "premium"]:
        await interaction.response.send_message(f"{config['EMOJIS']['CROSS']} Invalid tier.", ephemeral=True)
        return
    content = await file.read()
    lines = content.decode("utf-8").splitlines()
    new_accounts = [line.strip() for line in lines if line.strip()]
    accounts = load_json(ACCOUNTS_FILE)
    accounts.setdefault(tier, []).extend(new_accounts)
    save_json(ACCOUNTS_FILE, accounts)
    await interaction.response.send_message(f"{config['EMOJIS']['CHECK']} Restocked `{len(new_accounts)}` accounts into **{tier}** tier.")

# ---- /generate ----
@bot.tree.command(name="generate", description="Generate a Rainbow Six Siege account")
async def generate(interaction: discord.Interaction):
    if not is_co_owner_plus(interaction.user):
        await interaction.response.send_message(f"{config['EMOJIS']['CROSS']} Only **Co-Owner+** can generate accounts.", ephemeral=True)
        return
    user = interaction.user
    tier = "normal"
    if discord.utils.get(user.roles, id=config["ROLES"]["PREMIUM"]): tier = "premium"
    elif discord.utils.get(user.roles, id=config["ROLES"]["EXOTIC"]): tier = "exotic"
    
    can_gen, remaining = check_cooldown(user.id, tier)
    if not can_gen:
        await interaction.response.send_message(f"{config['EMOJIS']['TIMER']} Cooldown: {remaining}s.", ephemeral=True)
        return
    account = generate_account(tier)
    if not account:
        await interaction.response.send_message(f"{config['EMOJIS']['CROSS']} No {tier} accounts left!", ephemeral=True)
        return
    set_cooldown(user.id)
    embed = black_embed(title=f"{config['EMOJIS']['KEY']} Account Generated ({tier.upper()})", description=f"`{account}`")
    embed.set_footer(text=f"Requested by {user.display_name} | {config['BOT_NAME']}")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="generate_keys", description="Generate a specific tier account")
@app_commands.choices(tier=[
    app_commands.Choice(name="Exotic", value="exotic"),
    app_commands.Choice(name="Premium", value="premium")
])
async def generate_keys(interaction: discord.Interaction, tier: app_commands.Choice[str]):
    if not is_co_owner_plus(interaction.user):
        await interaction.response.send_message(f"{config['EMOJIS']['CROSS']} Only **Co-Owner+** can use this.", ephemeral=True)
        return
    
    tier_val = tier.value
    role_id = config["ROLES"].get(tier_val.upper())
    
    if not discord.utils.get(interaction.user.roles, id=role_id):
        await interaction.response.send_message(f"You don't have the {tier_val.capitalize()} role.", ephemeral=True)
        return

    can_gen, remaining = check_cooldown(interaction.user.id, tier_val)
    if not can_gen:
        await interaction.response.send_message(f"Cooldown: {remaining}s.", ephemeral=True)
        return

    account = generate_account(tier_val)
    if not account:
        await interaction.response.send_message(f"Out of stock for {tier_val}.", ephemeral=True)
        return

    set_cooldown(interaction.user.id)
    embed = black_embed(title=f"Account Generated ({tier_val.upper()})", description=f"`{account}`")
    await interaction.response.send_message(embed=embed)

# Rest of the commands...
@bot.tree.command(name="exoticpanel", description="Post the Exotic Generator panel")
async def exoticpanel(interaction: discord.Interaction):
    if not (is_co_owner_plus(interaction.user) or discord.utils.get(interaction.user.roles, id=config["ROLES"]["RESELLER"])):
        await interaction.response.send_message("No permission.", ephemeral=True)
        return
    channel = bot.get_channel(config["CHANNELS"]["EXOTIC_PANEL"])
    embed = black_embed(title=f"{config['EMOJIS']['EXOTIC']} **EXOTIC GENERATOR** {config['EMOJIS']['EXOTIC']}", description="Generate high-quality R6 accounts every **50 seconds**.")
    view = discord.ui.View()
    view.add_item(discord.ui.Button(label="Generate Exotic Account", style=discord.ButtonStyle.primary, custom_id="generate_exotic"))
    await channel.send(embed=embed, view=view)
    await interaction.response.send_message("Exotic panel posted.", ephemeral=True)

@bot.tree.command(name="premium_generate_panel", description="Post the Premium Generator panel")
async def premium_generate_panel(interaction: discord.Interaction):
    if not (is_co_owner_plus(interaction.user) or discord.utils.get(interaction.user.roles, id=config["ROLES"]["RESELLER"])):
        await interaction.response.send_message("No permission.", ephemeral=True)
        return
    channel = bot.get_channel(config["CHANNELS"]["PREMIUM_PANEL"])
    embed = black_embed(title=f"{config['EMOJIS']['PREMIUM']} **PREMIUM GENERATOR** {config['EMOJIS']['PREMIUM']}", description="Generate **elite** R6 accounts every **1 minute**.")
    view = discord.ui.View()
    view.add_item(discord.ui.Button(label="Generate Premium Account", style=discord.ButtonStyle.success, custom_id="generate_premium"))
    await channel.send(embed=embed, view=view)
    await interaction.response.send_message("Premium panel posted.", ephemeral=True)

@bot.tree.command(name="livestock", description="Show available account counts")
async def livestock(interaction: discord.Interaction):
    accounts = load_json(ACCOUNTS_FILE)
    normal = len(accounts.get("normal", []))
    exotic = len(accounts.get("exotic", []))
    premium = len(accounts.get("premium", []))
    embed = black_embed(title=f"{config['EMOJIS']['LIVESTOCK']} **Livestock Report**")
    embed.add_field(name="Normal", value=f"`{normal}`", inline=True)
    embed.add_field(name="Exotic", value=f"`{exotic}`", inline=True)
    embed.add_field(name="Premium", value=f"`{premium}`", inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="setcooldown", description="Set global cooldown for normal tier")
async def setcooldown(interaction: discord.Interaction, seconds: int):
    if not discord.utils.get(interaction.user.roles, id=config["ROLES"]["OWNER"]):
        await interaction.response.send_message("Owner only.", ephemeral=True)
        return
    conf = load_json(CONFIG_FILE)
    conf["DEFAULT_COOLDOWN"] = seconds
    save_json(CONFIG_FILE, conf)
    await interaction.response.send_message(f"Cooldown set to `{seconds}`s.")

@bot.tree.command(name="addowner", description="Give Owner role to a user")
async def addowner(interaction: discord.Interaction, member: discord.Member):
    if not discord.utils.get(interaction.user.roles, id=config["ROLES"]["OWNER"]):
        await interaction.response.send_message("Owner only.", ephemeral=True)
        return
    role = interaction.guild.get_role(config["ROLES"]["OWNER"])
    await member.add_roles(role)
    await interaction.response.send_message(f"Added `{member.name}` as Owner.")

@bot.tree.command(name="addreseller", description="Give Reseller role to a user")
async def addreseller(interaction: discord.Interaction, member: discord.Member):
    if not discord.utils.get(interaction.user.roles, id=config["ROLES"]["OWNER"]):
        await interaction.response.send_message("Owner only.", ephemeral=True)
        return
    role = interaction.guild.get_role(config["ROLES"]["RESELLER"])
    await member.add_roles(role)
    await interaction.response.send_message(f"Added `{member.name}` as Reseller.")

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.component:
        custom_id = interaction.data.get("custom_id")
        if not is_co_owner_plus(interaction.user):
            await interaction.response.send_message(f"{config['EMOJIS']['CROSS']} Only **Co-Owner+** can generate accounts.", ephemeral=True)
            return
        if custom_id == "generate_exotic":
            if interaction.channel_id != config["CHANNELS"]["EXOTIC_PANEL"]:
                await interaction.response.send_message("♱ Works in exotic-gen channel only!", ephemeral=True)
                return
            if not discord.utils.get(interaction.user.roles, id=config["ROLES"]["EXOTIC"]):
                await interaction.response.send_message("Need Exotic role.", ephemeral=True)
                return
            can_gen, rem = check_cooldown(interaction.user.id, "exotic")
            if not can_gen:
                await interaction.response.send_message(f"Cooldown: {rem}s.", ephemeral=True)
                return
            acc = generate_account("exotic")
            if not acc:
                await interaction.response.send_message("Out of stock.", ephemeral=True)
                return
            set_cooldown(interaction.user.id)
            await interaction.response.send_message(embed=black_embed(title="Exotic Account", description=f"`{acc}`"))
        elif custom_id == "generate_premium":
            if interaction.channel_id != config["CHANNELS"]["PREMIUM_PANEL"]:
                await interaction.response.send_message("♱ Works in premium-gen channel only!", ephemeral=True)
                return
            if not discord.utils.get(interaction.user.roles, id=config["ROLES"]["PREMIUM"]):
                await interaction.response.send_message("Need Premium role.", ephemeral=True)
                return
            can_gen, rem = check_cooldown(interaction.user.id, "premium")
            if not can_gen:
                await interaction.response.send_message(f"Cooldown: {rem}s.", ephemeral=True)
                return
            acc = generate_account("premium")
            if not acc:
                await interaction.response.send_message("Out of stock.", ephemeral=True)
                return
            set_cooldown(interaction.user.id)
            await interaction.response.send_message(embed=black_embed(title="Premium Account", description=f"`{acc}`"))

if __name__ == "__main__":
    if TOKEN: bot.run(TOKEN)
    else: print("Please set the GEN_BOT_TOKEN environment variable.")
