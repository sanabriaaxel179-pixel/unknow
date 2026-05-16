import discord
from discord.ext import commands
from discord import app_commands
import os

# ================= CONFIGURATION =================
TOKEN = os.getenv("MESSENGER_BOT_TOKEN")
GUILD_ID = 1504472803137814638
EMBED_COLOR = 0x800080  # Purple
CUSTOM_EMOJI_ID = 1504766603122966609

CO_OWNER_ROLE_ID = 1505164077658406922

# ================= BOT SETUP =================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="m!", intents=intents)

# ================= UTILS =================
def is_authorized(interaction: discord.Interaction):
    # Check for Co owner role or Administrator permission
    has_role = any(role.id == CO_OWNER_ROLE_ID for role in interaction.user.roles)
    return has_role or interaction.user.guild_permissions.administrator

# ================= COMMANDS =================
@bot.event
async def on_ready():
    print(f"✅ Logged in as Messenger Bot: {bot.user}")
    try:
        await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        await bot.tree.sync() # Global sync too
        print("Messenger commands synced!")
    except Exception as e:
        print(f"Sync error: {e}")

@bot.tree.command(name="embed", description="Send a styled purple embed message", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(title="The title of the embed", text="The main message (use \n for new lines)")
async def send_embed(interaction: discord.Interaction, title: str, text: str):
    # Permission check (Admin/Staff)
    if not is_authorized(interaction):
        await interaction.response.send_message("❌ Only **Co owners** or higher can use this command.", ephemeral=True)
        return

    emoji_str = f"<a:Monster52:{CUSTOM_EMOJI_ID}>"
    styled_title = f"{emoji_str} **{title}** {emoji_str}"
    
    # Auto-format the text with the professional arrows
    lines = text.replace("\\n", "\n").split("\n")
    formatted_lines = [f"↪ {line.strip()}" if line.strip() else "" for line in lines]
    formatted_text = "\n".join(formatted_lines)
    
    embed = discord.Embed(
        title=styled_title,
        description=formatted_text,
        color=EMBED_COLOR
    )
    embed.set_footer(text="Brought to Life by !avOid/kxrried")
    
    await interaction.channel.send(embed=embed)
    await interaction.response.send_message("✅ Embed sent!", ephemeral=True)

@bot.tree.command(name="say", description="Make the bot say something", guild=discord.Object(id=GUILD_ID))
async def say(interaction: discord.Interaction, message: str):
    if not is_authorized(interaction):
        await interaction.response.send_message("❌ Only **Co owners** or higher can use this command.", ephemeral=True)
        return
        
    await interaction.channel.send(message)
    await interaction.response.send_message("✅ Message sent!", ephemeral=True)

if __name__ == "__main__":
    bot.run(TOKEN)
