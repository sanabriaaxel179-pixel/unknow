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
    embed = discord.Embed(title=title, description=description, color=config.get("THEME_COLOR", 0x000000))
    return embed

# ================= COOLDOWN HANDLER =================
cooldowns = {}

def check_cooldown(user_id, tier="normal"):
    cooldown_seconds = config.get("DEFAULT_COOLDOWN", 60)
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
    
    if not pool:
        return None
        
    # Pick account
    account = random.choice(pool)
    
    # Remove used account
    accounts[tier].remove(account)
    save_json(ACCOUNTS_FILE, accounts)
    
    return account

# ================= COMMANDS =================
@bot.event
async def on_ready():
    print(f"✅ Generator Bot logged in as {bot.user}")
    try:
        await bot.tree.sync()
    except Exception as e:
        print(f"Sync error: {e}")

# ---- Admin: /restock ----
@bot.tree.command(name="restock", description="Restock accounts via .txt file")
async def restock(interaction: discord.Interaction, tier: str, file: discord.Attachment):
    if not is_co_owner_plus(interaction.user):
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
@bot.tree.command(name="generate", description="Generate a R6 account")
async def generate(interaction: discord.Interaction):
    if not is_co_owner_plus(interaction.user):
        await interaction.response.send_message(f"{config['EMOJIS']['CROSS']} Only **Co-Owner+** can use this command.", ephemeral=True)
        return

    user = interaction.user
    tier = "normal"
    if discord.utils.get(user.roles, id=config["ROLES"]["PREMIUM"]):
        tier = "premium"
    elif discord.utils.get(user.roles, id=config["ROLES"]["EXOTIC"]):
        tier = "exotic"
        
    can_gen, remaining = check_cooldown(user.id, tier)
    if not can_gen:
        await interaction.response.send_message(f"{config['EMOJIS']['TIMER']} Cooldown! Try again in {remaining} seconds.", ephemeral=True)
        return
        
    account = generate_account(tier)
    if not account:
        await interaction.response.send_message(f"{config['EMOJIS']['CROSS']} No {tier} accounts left!", ephemeral=True)
        return
        
    set_cooldown(user.id)
    embed = black_embed(title=f"{config['EMOJIS']['KEY']} Account Generated ({tier.upper()})", description=f"`{account}`")
    embed.set_footer(text=f"Requested by {user.display_name} | {config['BOT_NAME']}")
    await interaction.response.send_message(embed=embed)

# ---- Panels ----
@bot.tree.command(name="exoticpanel", description="Post the Exotic Generator panel")
async def exoticpanel(interaction: discord.Interaction):
    if not is_co_owner_plus(interaction.user):
        await interaction.response.send_message("No permission.", ephemeral=True)
        return
        
    channel = bot.get_channel(config["CHANNELS"]["EXOTIC_PANEL"])
    if not channel:
        await interaction.response.send_message("Panel channel not found.", ephemeral=True)
        return
        
    embed = black_embed(
        title=f"{config['EMOJIS']['EXOTIC']} **EXOTIC GENERATOR** {config['EMOJIS']['EXOTIC']}",
        description="Generate high-quality R6 accounts every **50 seconds**. Click below!"
    )
    view = discord.ui.View()
    view.add_item(discord.ui.Button(label="Generate Account", style=discord.ButtonStyle.primary, custom_id="gen_exotic"))
    await channel.send(embed=embed, view=view)
    await interaction.response.send_message("Panel posted.", ephemeral=True)

@bot.tree.command(name="premiumpanel", description="Post the Premium Generator panel")
async def premiumpanel(interaction: discord.Interaction):
    if not is_co_owner_plus(interaction.user):
        await interaction.response.send_message("No permission.", ephemeral=True)
        return
        
    channel = bot.get_channel(config["CHANNELS"]["PREMIUM_PANEL"])
    if not channel:
        await interaction.response.send_message("Panel channel not found.", ephemeral=True)
        return
        
    embed = black_embed(
        title=f"{config['EMOJIS']['PREMIUM']} **PREMIUM GENERATOR** {config['EMOJIS']['PREMIUM']}",
        description="Generate **elite** R6 accounts every **1 minute**. Click below!"
    )
    view = discord.ui.View()
    view.add_item(discord.ui.Button(label="Generate Account", style=discord.ButtonStyle.success, custom_id="gen_premium"))
    await channel.send(embed=embed, view=view)
    await interaction.response.send_message("Panel posted.", ephemeral=True)

# ---- Button Interactions ----
@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.component:
        custom_id = interaction.data.get("custom_id")
        
        # Role/Permission Check for Co-Owner+
        if not is_co_owner_plus(interaction.user):
            await interaction.response.send_message(f"{config['EMOJIS']['CROSS']} Only **Co-Owner+** can generate accounts.", ephemeral=True)
            return

        if custom_id == "gen_exotic":
            if interaction.channel_id != config["CHANNELS"]["EXOTIC_PANEL"]:
                await interaction.response.send_message("♱ This button only works in the **exotic-gen** channel!", ephemeral=True)
                return
            
            if not discord.utils.get(interaction.user.roles, id=config["ROLES"]["EXOTIC"]):
                await interaction.response.send_message(f"{config['EMOJIS']['CROSS']} You need the Exotic role.", ephemeral=True)
                return
                
            can_gen, rem = check_cooldown(interaction.user.id, "exotic")
            if not can_gen:
                await interaction.response.send_message(f"{config['EMOJIS']['TIMER']} Cooldown: {rem}s left.", ephemeral=True)
                return
                
            acc = generate_account("exotic")
            if not acc:
                await interaction.response.send_message("Out of stock.", ephemeral=True)
                return
                
            set_cooldown(interaction.user.id)
            embed = black_embed(title="Exotic Account", description=f"`{acc}`")
            await interaction.response.send_message(embed=embed)

        elif custom_id == "gen_premium":
            if interaction.channel_id != config["CHANNELS"]["PREMIUM_PANEL"]:
                await interaction.response.send_message("♱ This button only works in the **premium-gen** channel!", ephemeral=True)
                return

            if not discord.utils.get(interaction.user.roles, id=config["ROLES"]["PREMIUM"]):
                await interaction.response.send_message(f"{config['EMOJIS']['CROSS']} You need the Premium role.", ephemeral=True)
                return
                
            can_gen, rem = check_cooldown(interaction.user.id, "premium")
            if not can_gen:
                await interaction.response.send_message(f"{config['EMOJIS']['TIMER']} Cooldown: {rem}s left.", ephemeral=True)
                return
                
            acc = generate_account("premium")
            if not acc:
                await interaction.response.send_message("Out of stock.", ephemeral=True)
                return
                
            set_cooldown(interaction.user.id)
            embed = black_embed(title="Premium Account", description=f"`{acc}`")
            await interaction.response.send_message(embed=embed)

# ================= RUN BOT =================
if __name__ == "__main__":
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("Please set the GEN_BOT_TOKEN environment variable.")
