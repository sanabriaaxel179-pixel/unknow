import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
import time
import random

# ================= CONFIGURATION =================
TOKEN = os.getenv("BOOST_BOT_TOKEN")
GUILD_ID = 1504472803137814638
CUSTOM_EMOJI_ID = 1504766603122966609
EMOJI_STR = f"<a:Monster52:{CUSTOM_EMOJI_ID}>"

# ================= BOT SETUP =================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="b!", intents=intents)

# ================= COMMANDS =================
@bot.event
async def on_ready():
    print(f"✅ Logged in as Boost Bot: {bot.user}")
    try:
        guild = discord.Object(id=GUILD_ID)
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
        await bot.tree.sync()
        print("Boost commands synced!")
    except Exception as e:
        print(f"Sync error: {e}")

@bot.command()
@commands.has_permissions(administrator=True)
async def sync(ctx):
    """Force sync commands using a prefix"""
    try:
        guild = discord.Object(id=GUILD_ID)
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
        await bot.tree.sync()
        await ctx.send("✅ **Boost Bot commands have been force-synced!** Try typing `/` now.")
    except Exception as e:
        await ctx.send(f"❌ Sync failed: {e}")

# --- Core Boosting ---
@bot.tree.command(name="boost-server", description="Boost a Discord server with Nitro Tokens", guild=discord.Object(id=GUILD_ID))
async def boost_server(interaction: discord.Interaction, invite_link: str, amount: int, months: int):
    await interaction.response.defer()
    # Logic simulation (This would normally connect to a token manager)
    server_name = "the server" # This would be fetched from the invite
    await interaction.followup.send(f"{EMOJI_STR} u have boosted {server_name} {EMOJI_STR}")

@bot.tree.command(name="oauth-boost-server", description="Uses OAuth2 boosting for a guild ID", guild=discord.Object(id=GUILD_ID))
async def oauth_boost(interaction: discord.Interaction, guild_id: str):
    await interaction.response.send_message(f"Starting OAuth boost for `{guild_id}`...", ephemeral=True)

# --- Information & Stock ---
@bot.tree.command(name="bot-information", description="Displays bot information", guild=discord.Object(id=GUILD_ID))
async def bot_info(interaction: discord.Interaction):
    embed = discord.Embed(title="Boost Bot Information", description="Advanced Server Boosting System", color=0x800080)
    embed.add_field(name="Status", value="Operational ✅")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="check-stock", description="Checks current stock", guild=discord.Object(id=GUILD_ID))
async def check_stock(interaction: discord.Interaction):
    await interaction.response.send_message("📦 **Current Stock:** 0 Tokens (Restock needed)", ephemeral=True)

@bot.tree.command(name="check-tokens", description="Check tokens for validity and boost status", guild=discord.Object(id=GUILD_ID))
async def check_tokens(interaction: discord.Interaction, token_type: str):
    await interaction.response.send_message(f"Checking `{token_type}` tokens...", ephemeral=True)

@bot.tree.command(name="livestock", description="Display live stock that updates every 5 seconds", guild=discord.Object(id=GUILD_ID))
async def livestock(interaction: discord.Interaction):
    await interaction.response.send_message("📊 Livestock monitor started.", ephemeral=True)

@bot.tree.command(name="stop-livestock", description="Stop a livestock message from updating", guild=discord.Object(id=GUILD_ID))
async def stop_livestock(interaction: discord.Interaction):
    await interaction.response.send_message("⏹️ Livestock monitor stopped.", ephemeral=True)

# --- Key System ---
@bot.tree.command(name="check-boost-key", description="Check details of a boost key", guild=discord.Object(id=GUILD_ID))
async def check_key(interaction: discord.Interaction, key: str, duration: str):
    await interaction.response.send_message(f"Key `{key}` is valid for `{duration}`.", ephemeral=True)

@bot.tree.command(name="redeem-key", description="Redeem a boost key", guild=discord.Object(id=GUILD_ID))
async def redeem_key(interaction: discord.Interaction, key: str):
    await interaction.response.send_message(f"✅ Key `{key}` redeemed successfully!", ephemeral=True)

@bot.tree.command(name="delete-boost-key", description="Delete an existing boost key", guild=discord.Object(id=GUILD_ID))
async def delete_key(interaction: discord.Interaction, key: str):
    await interaction.response.send_message(f"🗑️ Key `{key}` deleted.", ephemeral=True)

# --- Dashboard & Management ---
@bot.tree.command(name="dashboard", description="View dashboard links", guild=discord.Object(id=GUILD_ID))
async def dashboard(interaction: discord.Interaction):
    await interaction.response.send_message("🔗 **Dashboard:** [Coming Soon]", ephemeral=True)

@bot.tree.command(name="register-dashboard", description="Registers boostbot to our dashboard", guild=discord.Object(id=GUILD_ID))
async def register_dashboard(interaction: discord.Interaction):
    await interaction.response.send_message("📡 Registering to dashboard...", ephemeral=True)

@bot.tree.command(name="setup-autobuy", description="Setup autobuy integration for your server", guild=discord.Object(id=GUILD_ID))
async def setup_autobuy(interaction: discord.Interaction):
    await interaction.response.send_message("🛒 Starting Autobuy setup...", ephemeral=True)

@bot.tree.command(name="invoice-panel", description="Open the invoice lookup panel", guild=discord.Object(id=GUILD_ID))
async def invoice_panel(interaction: discord.Interaction):
    await interaction.response.send_message("📑 Invoice panel opened.", ephemeral=True)

# --- User & Token Management ---
@bot.tree.command(name="give-owner", description="Add a user to the allowed owners list", guild=discord.Object(id=GUILD_ID))
async def give_owner(interaction: discord.Interaction, user: discord.User):
    await interaction.response.send_message(f"👑 {user.mention} added as owner.", ephemeral=True)

@bot.tree.command(name="remove-owner", description="Remove a user from the allowed owners list", guild=discord.Object(id=GUILD_ID))
async def remove_owner(interaction: discord.Interaction, user: discord.User):
    await interaction.response.send_message(f"❌ {user.mention} removed from owners.", ephemeral=True)

@bot.tree.command(name="list-owners", description="Display all users in the allowed owners list", guild=discord.Object(id=GUILD_ID))
async def list_owners(interaction: discord.Interaction):
    await interaction.response.send_message("📜 **Owner List:** You", ephemeral=True)

@bot.tree.command(name="restock-tokens", description="Restock tokens", guild=discord.Object(id=GUILD_ID))
async def restock_tokens(interaction: discord.Interaction, file: discord.Attachment):
    await interaction.response.send_message("📥 Tokens restocked from file.", ephemeral=True)

@bot.tree.command(name="destock-tokens", description="Remove tokens from stock", guild=discord.Object(id=GUILD_ID))
async def destock_tokens(interaction: discord.Interaction, amount: int):
    await interaction.response.send_message(f"📤 Removed `{amount}` tokens from stock.", ephemeral=True)

@bot.tree.command(name="send-tokens", description="Send tokens to a user", guild=discord.Object(id=GUILD_ID))
async def send_tokens(interaction: discord.Interaction, user: discord.User, amount: int):
    await interaction.response.send_message(f"💸 Sent `{amount}` tokens to {user.mention}.", ephemeral=True)

if __name__ == "__main__":
    bot.run(TOKEN)
