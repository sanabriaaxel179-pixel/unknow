import discord
from discord.ext import commands
from discord import app_commands
import os
import json
import asyncio
from datetime import datetime

# ================= CONFIGURATION =================
TOKEN = os.getenv("TICKET_BOT_TOKEN")
GUILD_ID = 1504472803137814638
TICKET_CATEGORY_ID = 1505253351846183073
HEAD_OF_SERVER_ROLE_ID = 1504482136667979877
CO_OWNER_ROLE_ID = 1505164077658406922
RESELLER_ROLE_ID = 1504763361169244211
OWNER_ROLE_ID = 1504474785906950346
STAFF_ROLE_ID = 1504475554920009738 # Keeping this for basic staff access

EMBED_COLOR = 0x800080  # Purple

TRANSCRIPTS_DIR = "transcripts"
if not os.path.exists(TRANSCRIPTS_DIR):
    os.makedirs(TRANSCRIPTS_DIR)

# ================= BOT SETUP =================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="t!", intents=intents)

# ================= UI COMPONENTS =================
class TicketDropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Purchase", description="Purchase-related issues and questions", emoji=discord.PartialEmoji(name="globe~1", id=1505246006017789962)),
            discord.SelectOption(label="General", description="General questions and help", emoji=discord.PartialEmoji(name="globe~1", id=1505246006017789962)),
            discord.SelectOption(label="Partnership", description="Partnership inquiries and proposals", emoji=discord.PartialEmoji(name="globe~1", id=1505246006017789962))
        ]
        super().__init__(placeholder="Select support type...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        category = guild.get_channel(TICKET_CATEGORY_ID)
        if not category:
            # Fallback if category ID is wrong
            category = discord.utils.get(guild.categories, name="Tickets")
            if not category:
                category = await guild.create_category("Tickets")

        staff_role = guild.get_role(STAFF_ROLE_ID)
        head_role = guild.get_role(HEAD_OF_SERVER_ROLE_ID)
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
        }
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True)

        ticket_type = self.values[0].lower()
        channel_name = f"ticket-{interaction.user.name}-{ticket_type}"
        
        ticket_channel = await guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites
        )

        embed = discord.Embed(
            title=f"Welcome to your {ticket_type.capitalize()} Ticket",
            description="Staff will be with you shortly.\n**Brought to Life by !avOid/kxrried**",
            color=EMBED_COLOR
        )
        ping_content = f"{interaction.user.mention} <@&{OWNER_ROLE_ID}>"
        await ticket_channel.send(content=ping_content, embed=embed)
        await interaction.followup.send(f"Ticket created: {ticket_channel.mention}", ephemeral=True)


class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketDropdown())

# ================= COMMANDS =================
@bot.event
async def on_ready():
    print(f"✅ Logged in as Ticket Bot: {bot.user}")
    try:
        # Syncing to the specific guild for instant results
        synced_guild = await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        print(f"Synced {len(synced_guild)} guild-specific commands")
        
        # Also syncing globally just in case
        synced_global = await bot.tree.sync()
        print(f"Synced {len(synced_global)} global commands")
    except Exception as e:
        print(f"Sync error: {e}")
    bot.add_view(TicketView())

@bot.tree.command(name="ticketpanel", description="Create a ticket support panel (Components V2)", guild=discord.Object(id=GUILD_ID))
@app_commands.default_permissions(administrator=True)
async def ticketpanel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="!avOid/kxrried Tickets",
        description="Please read the Informations Carefully",
        color=EMBED_COLOR
    )
    
    info_text = (
        "↪ Choose any option to get assistance.\n"
        "↪ We are always here to help you!\n"
        "↪ 24/7 Support.\n"
        "↪ Please state your issue as soon as the ticket opens.\n"
        "↪ Do not ping anyone/any roles unless no response in 24 hours."
    )
    embed.add_field(name="📚 Information", value=info_text, inline=False)
    
    important_text = (
        "↪ All sales are final — no refunds once delivered\n"
        "↪ Do not deal with anyone claiming to be staff outside this ticket\n"
        "↪ If you are unsure about anything, ask before purchasing"
    )
    embed.add_field(name="⚠️ Important", value=important_text, inline=False)
    
    payment_text = "↪ <:PayPal:1505246719187615836> PayPal"
    embed.add_field(name="💳 Payment Methods", value=payment_text, inline=False)
    
    embed.add_field(name="", value="🔔 **By Opening a Ticket you agree to our Terms of Service**\n\n[Join our Community Server](https://discord.gg/6EX8JWbXQ)", inline=False)
    
    # You can set an animated banner here if you upload it somewhere and put the URL.
    # embed.set_image(url="YOUR_GIF_URL_HERE")
    
    view = TicketView()
    await interaction.channel.send(embed=embed, view=view)
    await interaction.response.send_message("Ticket panel posted successfully.", ephemeral=True)

@bot.tree.command(name="close", description="Close the current ticket", guild=discord.Object(id=GUILD_ID))
async def close_ticket(interaction: discord.Interaction):
    await interaction.response.defer()
    if interaction.channel.category_id != TICKET_CATEGORY_ID and not any(x in interaction.channel.name for x in ["ticket-", "paid-", "waiting-", "claimed-"]):
        await interaction.followup.send("This command can only be used in a ticket channel.", ephemeral=True)
        return

    await interaction.followup.send("Closing ticket in 5 seconds...", ephemeral=False)
    
    # Generate transcript
    messages = [msg async for msg in interaction.channel.history(limit=500, oldest_first=True)]
    ticket_id = interaction.channel.name
    transcript_file = os.path.join(TRANSCRIPTS_DIR, f"{ticket_id}.txt")
    
    with open(transcript_file, "w", encoding="utf-8") as f:
        for msg in messages:
            f.write(f"[{msg.created_at.strftime('%Y-%m-%d %H:%M:%S')}] {msg.author.name}: {msg.content}\n")

    await asyncio.sleep(5)
    await interaction.channel.delete(reason="Ticket closed by user.")

@bot.tree.command(name="add_user", description="Add a user to the current ticket", guild=discord.Object(id=GUILD_ID))
async def add_user(interaction: discord.Interaction, user: discord.Member):
    await interaction.response.defer(ephemeral=True)
    if interaction.channel.category_id != TICKET_CATEGORY_ID and not any(x in interaction.channel.name for x in ["ticket-", "paid-", "waiting-", "claimed-"]):
        await interaction.followup.send("This command can only be used in a ticket channel.", ephemeral=True)
        return
        
    await interaction.channel.set_permissions(user, read_messages=True, send_messages=True, attach_files=True)
    await interaction.followup.send(f"Added {user.mention} to the ticket.")

@bot.tree.command(name="remove_user", description="Remove a user from the current ticket", guild=discord.Object(id=GUILD_ID))
async def remove_user(interaction: discord.Interaction, user: discord.Member):
    await interaction.response.defer(ephemeral=True)
    if interaction.channel.category_id != TICKET_CATEGORY_ID and not any(x in interaction.channel.name for x in ["ticket-", "paid-", "waiting-", "claimed-"]):
        await interaction.followup.send("This command can only be used in a ticket channel.", ephemeral=True)
        return
    
    # Permission check for Co owner or Admin
    is_co_owner = any(role.name.lower() == "co owner" for role in interaction.user.roles)
    if not is_co_owner and not interaction.user.guild_permissions.administrator:
        await interaction.followup.send("❌ Only **Co owners** or Administrators can remove users from tickets.", ephemeral=True)
        return
        
    await interaction.channel.set_permissions(user, overwrite=None)
    await interaction.followup.send(f"Removed {user.mention} from the ticket.")

@bot.tree.command(name="rename-ticket", description="Rename the current ticket channel", guild=discord.Object(id=GUILD_ID))
async def rename_ticket(interaction: discord.Interaction, new_name: str):
    await interaction.response.defer(ephemeral=True)
    if interaction.channel.category_id != TICKET_CATEGORY_ID and not any(x in interaction.channel.name for x in ["ticket-", "paid-", "waiting-", "claimed-"]):
        await interaction.followup.send("This command can only be used in a ticket channel.", ephemeral=True)
        return
    
    # Format name
    if not new_name.startswith("ticket-"):
        new_name = f"ticket-{new_name}"
        
    await interaction.channel.edit(name=new_name)
    await interaction.followup.send(f"Ticket renamed to `{new_name}`.")

@bot.tree.command(name="escalate", description="Change ticket status (Paid/Waiting/Claimed)", guild=discord.Object(id=GUILD_ID))
@app_commands.choices(status=[
    app_commands.Choice(name="Paid", value="paid"),
    app_commands.Choice(name="Waiting", value="waiting"),
    app_commands.Choice(name="Claimed", value="claimed")
])
async def escalate(interaction: discord.Interaction, status: str):
    await interaction.response.defer()
    if interaction.channel.category_id != TICKET_CATEGORY_ID and not any(x in interaction.channel.name for x in ["ticket-", "paid-", "waiting-", "claimed-"]):
        await interaction.followup.send("This command can only be used in a ticket channel.", ephemeral=True)
        return
        
    base_name = interaction.channel.name.split("-", 1)[-1]
    if base_name.startswith(("paid-", "waiting-", "claimed-")):
        base_name = base_name.split("-", 1)[-1]
        
    new_name = f"{status}-{base_name}"
    await interaction.channel.edit(name=new_name)
    
    # Special logic for Paid status
    if status == "paid":
        owner_role = interaction.guild.get_role(OWNER_ROLE_ID)
        staff_role = interaction.guild.get_role(STAFF_ROLE_ID)
        
        # Remove normal staff and add owners only
        if staff_role:
            await interaction.channel.set_permissions(staff_role, read_messages=False)
        if owner_role:
            await interaction.channel.set_permissions(owner_role, read_messages=True, send_messages=True, manage_messages=True)
            
        await interaction.followup.send(f"Ticket escalated to **{status.capitalize()}**. Only Owners can now see this channel. <@&{OWNER_ROLE_ID}>")
    else:
        await interaction.followup.send(f"Ticket escalated to **{status.capitalize()}**.")

@bot.tree.command(name="check-ticket-id", description="Retrieve a closed ticket's log and transcript", guild=discord.Object(id=GUILD_ID))
async def check_ticket_id(interaction: discord.Interaction, ticket_id: str):
    # Enforce staff only
    staff_role = interaction.guild.get_role(STAFF_ROLE_ID)
    if staff_role not in interaction.user.roles and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("You do not have permission to view transcripts.", ephemeral=True)
        return
        
    transcript_file = os.path.join(TRANSCRIPTS_DIR, f"{ticket_id}.txt")
    if not os.path.exists(transcript_file):
        await interaction.response.send_message(f"No transcript found for `{ticket_id}`.", ephemeral=True)
        return
        
    await interaction.response.send_message(
        f"Transcript for `{ticket_id}`:", 
        file=discord.File(transcript_file),
        ephemeral=True
    )

if __name__ == "__main__":
    bot.run(TOKEN)
