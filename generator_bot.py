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
    if config.get("DEFAULT_COOLDOWN", 0) == 0:
        return True, 0
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
        guild = discord.Object(id=config["GUILD_ID"])
        synced = await bot.tree.sync(guild=guild)
        print(f"Synced {len(synced)} commands to Guild {config['GUILD_ID']}")
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
    
    # Send to tier-specific channel
    channel_key = f"{tier.upper()}_PANEL"
    if channel_key in config["CHANNELS"]:
        channel = bot.get_channel(config["CHANNELS"][channel_key])
        if channel:
            embed = black_embed(title=f"Account Generated ({tier.upper()})", description=f"`{acc}`")
            embed.add_field(name="User", value=interaction.user.mention, inline=True)
            embed.timestamp = datetime.now()
            try:
                await channel.send(embed=embed)
            except:
                pass
    
    # Send to DM
    try:
        dm_embed = black_embed(title=f"Account Generated ({tier.upper()})", description=f"`{acc}`")
        dm_embed.set_footer(text=f"Requested from {interaction.channel.name} | {config['BOT_NAME']}")
        dm_embed.timestamp = datetime.now()
        await interaction.user.send(embed=dm_embed)
    except:
        pass
    
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

@bot.tree.command(name="livestock", description="Show available account counts")
async def livestock(interaction: discord.Interaction):
    data = load_json(ACCOUNTS_FILE)
    embed = black_embed(title=f"{config['EMOJIS']['LIVESTOCK']} Livestock Report {config['EMOJIS']['LIVESTOCK']}")
    for t in ["normal", "exotic", "premium"]:
        embed.add_field(name=t.capitalize(), value=f"`{len(data.get(t, []))}`", inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="exoticpanel", description="Post the Exotic Generator panel")
async def exoticpanel(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    if not (discord.utils.get(interaction.user.roles, id=config["ROLES"]["OWNER"]) or discord.utils.get(interaction.user.roles, id=config["ROLES"]["CO_OWNER"])):
        await interaction.followup.send("No permission.", ephemeral=True)
        return
    channel = bot.get_channel(config["CHANNELS"]["EXOTIC_PANEL"])
    if not channel:
        await interaction.followup.send("Channel not found.", ephemeral=True)
        return
    embed = black_embed(title=f"{config['EMOJIS']['EXOTIC']} **EXOTIC GENERATOR** {config['EMOJIS']['EXOTIC']}", description="Generate high-quality R6 accounts every **50 seconds**.")
    view = discord.ui.View()
    view.add_item(discord.ui.Button(label="Generate Exotic Account", style=discord.ButtonStyle.primary, custom_id="generate_exotic"))
    await channel.send(embed=embed, view=view)
    await interaction.followup.send("Exotic panel posted.", ephemeral=True)

@bot.tree.command(name="premium_generate_panel", description="Post the Premium Generator panel")
async def premium_generate_panel(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    if not (discord.utils.get(interaction.user.roles, id=config["ROLES"]["OWNER"]) or discord.utils.get(interaction.user.roles, id=config["ROLES"]["CO_OWNER"])):
        await interaction.followup.send("No permission.", ephemeral=True)
        return
    channel = bot.get_channel(config["CHANNELS"]["PREMIUM_PANEL"])
    if not channel:
        await interaction.followup.send("Channel not found.", ephemeral=True)
        return
    embed = black_embed(title=f"{config['EMOJIS']['PREMIUM']} **PREMIUM GENERATOR** {config['EMOJIS']['PREMIUM']}", description="Generate **elite** R6 accounts every **1 minute**.")
    view = discord.ui.View()
    view.add_item(discord.ui.Button(label="Generate Premium Account", style=discord.ButtonStyle.success, custom_id="generate_premium"))
    await channel.send(embed=embed, view=view)
    await interaction.followup.send("Premium panel posted.", ephemeral=True)

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.component:
        custom_id = interaction.data.get("custom_id")
        
        tier = None
        if "exotic" in custom_id: tier = "exotic"
        elif "premium" in custom_id: tier = "premium"
        
        if not tier: return

        role_id = config["ROLES"].get(tier.upper())
        if not (discord.utils.get(interaction.user.roles, id=role_id) or is_co_owner_plus(interaction.user)):
            msg = "u must have exotic role" if tier == "exotic" else "u must have prem gen"
            await interaction.response.send_message(f"{config['EMOJIS']['CROSS']} {msg}", ephemeral=True)
            return

        panel_channel_id = config["CHANNELS"].get(f"{tier.upper()}_PANEL")
        if interaction.channel_id != panel_channel_id:
            await interaction.response.send_message(f"♱ This button only works in the <#{panel_channel_id}> channel!", ephemeral=True)
            return
            
        can_gen, rem = check_cooldown(interaction.user.id, tier)
        if not can_gen:
            await interaction.response.send_message(f"{config['EMOJIS']['TIMER']} Cooldown: {rem}s left.", ephemeral=True)
            return
            
        acc = generate_account(tier)
        if not acc:
            await interaction.response.send_message(f"{config['EMOJIS']['CROSS']} Out of stock for **{tier}**.", ephemeral=True)
            return
            
        set_cooldown(interaction.user.id)
        
        # Emoji for the tier
        emoji = config['EMOJIS']['EXOTIC'] if tier == "exotic" else config['EMOJIS']['PREMIUM']
        
        # Create embed for DM
        dm_embed = black_embed(
            title=f"{emoji} {tier.capitalize()} Account Generated {emoji}",
            description=f"**Account:** `{acc}`"
        )
        dm_embed.set_footer(text=f"Requested by {interaction.user.display_name} | {config['BOT_NAME']}")
        dm_embed.timestamp = datetime.now()

        # Send to tier-specific channel
        channel_key = f"{tier.upper()}_PANEL"
        if channel_key in config["CHANNELS"]:
            channel = bot.get_channel(config["CHANNELS"][channel_key])
            if channel:
                channel_embed = black_embed(
                    title=f"{emoji} {tier.capitalize()} Account Generated {emoji}",
                    description=f"**Account:** `{acc}`"
                )
                channel_embed.add_field(name="User", value=interaction.user.mention, inline=True)
                channel_embed.set_footer(text=f"{config['BOT_NAME']}")
                channel_embed.timestamp = datetime.now()
                try:
                    await channel.send(embed=channel_embed)
                except:
                    pass

        # Send to DM
        try:
            await interaction.user.send(embed=dm_embed)
            await interaction.response.send_message(f"{config['EMOJIS']['CHECK']} Success! Check your DMs for your **{tier.capitalize()}** account.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(f"{config['EMOJIS']['CROSS']} I couldn't DM you! Please open your DMs and try again.", ephemeral=True)

if __name__ == "__main__":
    if TOKEN: bot.run(TOKEN)
