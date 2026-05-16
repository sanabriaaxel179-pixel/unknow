import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import os
import random
import time
import string
from datetime import datetime, timedelta

# ================= CONFIGURATION =================
CONFIG_FILE = "config.json"
ACCOUNTS_FILE = "accounts.json"
KEYS_FILE = "keys.json"
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

def generate_key_string():
    return "av0id-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=12))

# ================= COOLDOWN HANDLER =================
cooldowns = {}
def check_cooldown(user_id, tier="normal"):
    cd = config.get("DEFAULT_COOLDOWN", 0)
    if tier == "exotic": cd = 50
    elif tier == "premium": cd = 60
    last = cooldowns.get(user_id, 0)
    now = time.time()
    if now - last < cd: return False, int(cd - (now - last))
    return True, 0

def set_cooldown(user_id):
    cooldowns[user_id] = time.time()

# ================= ACCOUNT GEN =================
def generate_account(tier):
    accounts = load_json(ACCOUNTS_FILE)
    pool = accounts.get(tier, [])
    if not pool: return None
    if tier == "premium" and len(pool) > 3: pool = pool[:max(3, len(pool)//3)]
    elif tier == "exotic" and len(pool) > 2: pool = pool[:max(2, len(pool)//2)]
    account = random.choice(pool)
    accounts[tier].remove(account)
    save_json(ACCOUNTS_FILE, accounts)
    return account

# ================= COMMANDS =================
@bot.event
async def on_ready():
    print(f"✅ Generator Bot logged in as {bot.user}")
    try:
        await bot.tree.sync()
        print("Synced commands globally")
    except Exception as e:
        print(f"Sync error: {e}")

# ---- License Key System ----

@bot.tree.command(name="genkey", description="Generate a license key (Owner/Co-Owner only)")
@app_commands.choices(tier=[
    app_commands.Choice(name="Exotic", value="exotic"),
    app_commands.Choice(name="Premium", value="premium")
], duration=[
    app_commands.Choice(name="1 Day", value="1d"),
    app_commands.Choice(name="1 Week", value="7d"),
    app_commands.Choice(name="1 Month", value="30d"),
    app_commands.Choice(name="1 Year", value="365d"),
    app_commands.Choice(name="Lifetime", value="lifetime")
])
async def genkey(interaction: discord.Interaction, tier: app_commands.Choice[str], duration: app_commands.Choice[str]):
    if not is_co_owner_plus(interaction.user):
        await interaction.response.send_message("No permission.", ephemeral=True)
        return

    key = generate_key_string()
    keys = load_json(KEYS_FILE)
    keys[key] = {"tier": tier.value, "duration": duration.value, "redeemed": False}
    save_json(KEYS_FILE, keys)

    embed = black_embed(title="License Key Generated", description=f"**Key:** `{key}`\n**Tier:** {tier.name}\n**Duration:** {duration.name}")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="redeem", description="Redeem a license key")
async def redeem(interaction: discord.Interaction, key: str):
    keys = load_json(KEYS_FILE)
    if key not in keys or keys[key]["redeemed"]:
        await interaction.response.send_message("Invalid or already redeemed key.", ephemeral=True)
        return

    data = keys[key]
    tier = data["tier"]
    duration_str = data["duration"]
    
    role_id = config["ROLES"].get(tier.upper())
    role = interaction.guild.get_role(role_id)
    
    if not role:
        await interaction.response.send_message("Role not found in server.", ephemeral=True)
        return

    await interaction.user.add_roles(role)
    keys[key]["redeemed"] = True
    keys[key]["redeemed_by"] = interaction.user.id
    keys[key]["redeem_time"] = time.time()
    save_json(KEYS_FILE, keys)

    embed = black_embed(title="Key Redeemed!", description=f"You have been given the **{tier.capitalize()}** role.\n**Duration:** {duration_str}")
    await interaction.response.send_message(embed=embed)

# ---- Restored Commands ----

@bot.tree.command(name="generate", description="Generate a R6 account")
async def generate(interaction: discord.Interaction):
    if not is_co_owner_plus(interaction.user):
        await interaction.response.send_message("Only Co-Owner+ can use this.", ephemeral=True)
        return
    tier = "normal"
    if discord.utils.get(interaction.user.roles, id=config["ROLES"]["PREMIUM"]): tier = "premium"
    elif discord.utils.get(interaction.user.roles, id=config["ROLES"]["EXOTIC"]): tier = "exotic"
    
    can_gen, rem = check_cooldown(interaction.user.id, tier)
    if not can_gen:
        await interaction.response.send_message(f"Cooldown: {rem}s.", ephemeral=True)
        return
    acc = generate_account(tier)
    if not acc:
        await interaction.response.send_message(f"No {tier} accounts left!", ephemeral=True)
        return
    set_cooldown(interaction.user.id)
    await interaction.response.send_message(embed=black_embed(title=f"Account Generated ({tier.upper()})", description=f"`{acc}`"))

@bot.tree.command(name="restock", description="Restock accounts")
async def restock(interaction: discord.Interaction, tier: str, file: discord.Attachment):
    if not (is_co_owner_plus(interaction.user) or discord.utils.get(interaction.user.roles, id=config["ROLES"]["RESELLER"])):
        await interaction.response.send_message("No permission.", ephemeral=True)
        return
    content = await file.read()
    lines = content.decode("utf-8").splitlines()
    accs = [l.strip() for l in lines if l.strip()]
    data = load_json(ACCOUNTS_FILE)
    data.setdefault(tier, []).extend(accs)
    save_json(ACCOUNTS_FILE, data)
    await interaction.response.send_message(f"Restocked {len(accs)} accounts to {tier}.")

@bot.tree.command(name="livestock", description="Show stock")
async def livestock(interaction: discord.Interaction):
    data = load_json(ACCOUNTS_FILE)
    embed = black_embed(title="Livestock Report")
    for t in ["normal", "exotic", "premium"]:
        embed.add_field(name=t.capitalize(), value=f"`{len(data.get(t, []))}`", inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="exoticpanel", description="Post Exotic panel")
async def exoticpanel(interaction: discord.Interaction):
    if not is_co_owner_plus(interaction.user): return
    channel = bot.get_channel(config["CHANNELS"]["EXOTIC_PANEL"])
    view = discord.ui.View()
    view.add_item(discord.ui.Button(label="Generate Exotic", style=discord.ButtonStyle.primary, custom_id="generate_exotic"))
    await channel.send(embed=black_embed(title="Exotic Generator"), view=view)
    await interaction.response.send_message("Posted.", ephemeral=True)

@bot.tree.command(name="premium_generate_panel", description="Post Premium panel")
async def premium_generate_panel(interaction: discord.Interaction):
    if not is_co_owner_plus(interaction.user): return
    channel = bot.get_channel(config["CHANNELS"]["PREMIUM_PANEL"])
    view = discord.ui.View()
    view.add_item(discord.ui.Button(label="Generate Premium", style=discord.ButtonStyle.success, custom_id="generate_premium"))
    await channel.send(embed=black_embed(title="Premium Generator"), view=view)
    await interaction.response.send_message("Posted.", ephemeral=True)

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.component:
        cid = interaction.data.get("custom_id")
        if not is_co_owner_plus(interaction.user): return
        tier = "exotic" if "exotic" in cid else "premium"
        can_gen, rem = check_cooldown(interaction.user.id, tier)
        if not can_gen:
            await interaction.response.send_message(f"Cooldown: {rem}s.", ephemeral=True)
            return
        acc = generate_account(tier)
        if acc:
            set_cooldown(interaction.user.id)
            await interaction.response.send_message(embed=black_embed(title=f"{tier.capitalize()} Account", description=f"`{acc}`"))

if __name__ == "__main__":
    if TOKEN: bot.run(TOKEN)
