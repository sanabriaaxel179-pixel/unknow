import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
import time
import random
import sqlite3
import datetime
import string
from aiohttp import web
import asyncio

# ================= CONFIGURATION =================
TOKEN = os.getenv("BOOST_BOT_TOKEN")
GUILD_ID = 1504472803137814638
CUSTOM_EMOJI_ID = 1504766603122966609
EMOJI_STR = f"<a:Monster52:{CUSTOM_EMOJI_ID}>"

# Role IDs for permissions
OWNER_ROLE_ID = 1504474785906950346
CO_OWNER_ROLE_ID = 1505164077658406922
RESELLER_ROLE_ID = 1504763361169244211

# ================= DATABASE SETUP =================
def init_db():
    conn = sqlite3.connect("boostbot.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS licenses (
            key TEXT PRIMARY KEY,
            duration TEXT DEFAULT 'lifetime',
            redeemed INTEGER DEFAULT 0,
            redeemed_by TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            expiry TIMESTAMP
        )
    ''')
    conn.commit()
    return conn

db_conn = init_db()

def get_stats():
    cursor = db_conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM licenses")
    total_keys = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM licenses WHERE redeemed = 0")
    active_keys = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    
    cursor.execute("SELECT user_id, expiry FROM users")
    users = cursor.fetchall()
    return total_keys, active_keys, total_users, users

# ================= WEB DASHBOARD =================
app = web.Application()

async def dashboard_handler(request):
    total_keys, active_keys, total_users, users = get_stats()
    
    user_rows = ""
    for u in users:
        u_id, expiry = u
        user_rows += f"""
        <tr>
            <td>{u_id}</td>
            <td>{expiry if expiry else 'Lifetime'}</td>
            <td>
                <form action="/terminate" method="POST" style="display:inline;">
                    <input type="hidden" name="user_id" value="{u_id}">
                    <button type="submit" style="background-color: #ff4444; color: white; border: none; padding: 5px 10px; cursor: pointer; border-radius: 4px;">Terminate</button>
                </form>
                <form action="/extend" method="POST" style="display:inline;">
                    <input type="hidden" name="user_id" value="{u_id}">
                    <select name="duration" style="padding: 4px;">
                        <option value="1day">1 Day</option>
                        <option value="1week">1 Week</option>
                        <option value="1month">1 Month</option>
                        <option value="1year">1 Year</option>
                        <option value="lifetime">Lifetime</option>
                    </select>
                    <button type="submit" style="background-color: #44ff44; color: black; border: none; padding: 5px 10px; cursor: pointer; border-radius: 4px;">Extend</button>
                </form>
            </td>
        </tr>
        """

    html = f"""
    <html>
    <head>
        <title>Boost Bot Dashboard</title>
        <style>
            body {{ font-family: 'Inter', sans-serif; background-color: #121212; color: #ffffff; padding: 20px; }}
            .container {{ max-width: 800px; margin: auto; background: #1e1e1e; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }}
            h1 {{ border-bottom: 2px solid #6200ea; padding-bottom: 10px; }}
            .stats {{ display: flex; gap: 20px; margin-bottom: 30px; }}
            .stat-box {{ background: #2c2c2c; padding: 15px; border-radius: 8px; flex: 1; text-align: center; }}
            .stat-box h2 {{ margin: 0; font-size: 24px; color: #bb86fc; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
            th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #333; }}
            th {{ background-color: #2c2c2c; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🚀 Boost Bot Dashboard</h1>
            <div class="stats">
                <div class="stat-box"><h3>Total Keys Created</h3><h2>{total_keys}</h2></div>
                <div class="stat-box"><h3>Active (Unused)</h3><h2>{active_keys}</h2></div>
                <div class="stat-box"><h3>Active Users</h3><h2>{total_users}</h2></div>
            </div>
            
            <h3>Registered Users</h3>
            <table>
                <tr>
                    <th>User ID</th>
                    <th>Expiry Date</th>
                    <th>Actions</th>
                </tr>
                {user_rows}
            </table>
        </div>
    </body>
    </html>
    """
    return web.Response(text=html, content_type='text/html')

async def terminate_handler(request):
    data = await request.post()
    user_id = data.get('user_id')
    if user_id:
        cursor = db_conn.cursor()
        cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        db_conn.commit()
        
        try:
            user = await bot.fetch_user(int(user_id))
            await user.send("! av0id/kxrried has terminated your license")
        except:
            pass
            
    return web.HTTPFound('/')

async def extend_handler(request):
    data = await request.post()
    user_id = data.get('user_id')
    duration = data.get('duration')
    
    if user_id and duration:
        cursor = db_conn.cursor()
        cursor.execute("SELECT expiry FROM users WHERE user_id = ?", (user_id,))
        res = cursor.fetchone()
        
        if res:
            current_expiry_str = res[0]
            if current_expiry_str is None or duration == 'lifetime':
                new_expiry = None
            else:
                try:
                    current_expiry = datetime.datetime.strptime(current_expiry_str, '%Y-%m-%d %H:%M:%S')
                except:
                    current_expiry = datetime.datetime.now()
                
                if duration == '1day': new_expiry = current_expiry + datetime.timedelta(days=1)
                elif duration == '1week': new_expiry = current_expiry + datetime.timedelta(weeks=1)
                elif duration == '1month': new_expiry = current_expiry + datetime.timedelta(days=30)
                elif duration == '1year': new_expiry = current_expiry + datetime.timedelta(days=365)
                
            expiry_str = new_expiry.strftime('%Y-%m-%d %H:%M:%S') if new_expiry else None
            cursor.execute("UPDATE users SET expiry = ? WHERE user_id = ?", (expiry_str, user_id))
            db_conn.commit()
            
            try:
                user = await bot.fetch_user(int(user_id))
                await user.send(f"! av0id/kxrried has made your key longer to {duration}")
            except:
                pass

    return web.HTTPFound('/')

app.router.add_get('/', dashboard_handler)
app.router.add_post('/terminate', terminate_handler)
app.router.add_post('/extend', extend_handler)

# ================= BOT SETUP =================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="b!", intents=intents)

# ================= COMMANDS =================
@bot.event
async def on_ready():
    print(f"✅ Logged in as Boost Bot: {bot.user}")
    
    # Start web server for Railway
    port = int(os.environ.get("PORT", 8080))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"🌐 Dashboard running on port {port}")
    
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
    # Check if user has active license
    cursor = db_conn.cursor()
    cursor.execute("SELECT expiry FROM users WHERE user_id = ?", (str(interaction.user.id),))
    res = cursor.fetchone()
    
    is_authorized = False
    if res:
        expiry_str = res[0]
        if expiry_str is None:
            is_authorized = True
        else:
            expiry = datetime.datetime.strptime(expiry_str, '%Y-%m-%d %H:%M:%S')
            if datetime.datetime.now() < expiry:
                is_authorized = True
                
    if not is_authorized and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("🔒 **Access Restricted.** You must redeem a bootbot license key to use this command. Use `/redeem_bootbot_license <key>`.", ephemeral=True)
        return

    await interaction.response.defer()
    
    # Extract invite code
    invite_code = invite_link.split("/")[-1]
    if "?" in invite_code:
        invite_code = invite_code.split("?")[0]
        
    # Read tokens
    if not os.path.exists("tokens.txt"):
        await interaction.followup.send("❌ No tokens loaded. The owner needs to restock tokens first.")
        return
        
    with open("tokens.txt", "r") as f:
        tokens = [line.strip() for line in f if line.strip()]
        
    if len(tokens) < amount:
        await interaction.followup.send(f"❌ Not enough tokens in stock. Requested {amount}, but only have {len(tokens)}.")
        return
        
    # Take the required amount of tokens
    tokens_to_use = tokens[:amount]
    remaining_tokens = tokens[amount:]
    
    # Save remaining tokens
    with open("tokens.txt", "w") as f:
        for t in remaining_tokens:
            f.write(t + "\n")
            
    await interaction.followup.send(f"⏳ Processing {amount} boosts for `{invite_code}` using Scrapeless... Please wait.")
    
    success_count = 0
    import aiohttp
    import json
    
    # The exact Scrapeless API Key provided
    scrapeless_token = "sk_2WEj1nuD1BE62YiBE3P14mCV4A7lt2N87bn4f5PQxQHrHZKCXchANtEgl5QjiJsn"
    scrapeless_url = "https://api.scrapeless.com/api/v1/unlocker/request"
    
    async with aiohttp.ClientSession() as session:
        for discord_token in tokens_to_use:
            # Format proxy token to discord format if it's email:pass:token
            actual_token = discord_token.split(":")[-1] if ":" in discord_token else discord_token
            
            # Step 1: Join Server via Scrapeless Web Unlocker
            join_payload = {
                "actor": "unlocker.webunlocker",
                "proxy": {"country": "ANY"},
                "input": {
                    "url": f"https://discord.com/api/v9/invites/{invite_code}",
                    "method": "POST",
                    "redirect": False,
                    "jsRender": {"enabled": False},
                    "headers": {
                        "Authorization": actual_token,
                        "Content-Type": "application/json"
                    },
                    "body": "{}"
                }
            }
            
            try:
                # 1. Join Server
                async with session.post(scrapeless_url, headers={"x-api-token": scrapeless_token}, json=join_payload) as resp:
                    if resp.status == 200:
                        join_resp = await resp.json()
                        try:
                            # Scrapeless returns the response body as a string inside "body", which is JSON
                            discord_data = json.loads(join_resp.get("body", "{}"))
                            guild_id = discord_data.get("guild", {}).get("id")
                        except:
                            guild_id = None
                            
                        if guild_id:
                            # Step 2: Get Subscription Slots
                            slots_payload = join_payload.copy()
                            slots_payload["input"]["url"] = "https://discord.com/api/v9/users/@me/guilds/premium/subscription-slots"
                            slots_payload["input"]["method"] = "GET"
                            slots_payload["input"]["body"] = ""
                            
                            async with session.post(scrapeless_url, headers={"x-api-token": scrapeless_token}, json=slots_payload) as slots_resp:
                                if slots_resp.status == 200:
                                    slots_data_resp = await slots_resp.json()
                                    try:
                                        slots_data = json.loads(slots_data_resp.get("body", "[]"))
                                        # Get available slots
                                        available_slots = [slot["id"] for slot in slots_data if slot.get("cooldown_ends_at") is None]
                                        
                                        if available_slots:
                                            # Step 3: Apply Boosts
                                            boost_payload = join_payload.copy()
                                            boost_payload["input"]["url"] = f"https://discord.com/api/v9/guilds/{guild_id}/premium/subscriptions"
                                            boost_payload["input"]["method"] = "PUT"
                                            boost_payload["input"]["body"] = json.dumps({"user_premium_guild_subscription_slot_ids": available_slots})
                                            
                                            async with session.post(scrapeless_url, headers={"x-api-token": scrapeless_token}, json=boost_payload) as final_resp:
                                                if final_resp.status == 200:
                                                    success_count += 1
                                    except:
                                        pass
            except Exception as e:
                print(f"Scrapeless Error: {e}")
                
            await asyncio.sleep(1) # Prevent rapid scraping bans
            
    await interaction.followup.send(f"{EMOJI_STR} Boost Process Complete! Successfully used **{success_count}** out of {amount} attempted tokens on {invite_code} {EMOJI_STR}")

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
    stock = 0
    if os.path.exists("tokens.txt"):
        with open("tokens.txt", "r") as f:
            stock = len([line for line in f if line.strip()])
    await interaction.response.send_message(f"📦 **Current Stock:** {stock} Tokens", ephemeral=True)

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
@bot.tree.command(name="gen_license", description="Generate a Bootbot license (Staff Only)", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(duration="The duration of the license")
@app_commands.choices(duration=[
    app_commands.Choice(name="1 Day", value="1day"),
    app_commands.Choice(name="1 Week", value="1week"),
    app_commands.Choice(name="1 Month", value="1month"),
    app_commands.Choice(name="1 Year", value="1year"),
    app_commands.Choice(name="Lifetime", value="lifetime")
])
async def gen_license(interaction: discord.Interaction, duration: str):
    has_permission = False
    if interaction.user.guild_permissions.administrator:
        has_permission = True
    elif hasattr(interaction.user, "roles"):
        role_ids = [role.id for role in interaction.user.roles]
        if OWNER_ROLE_ID in role_ids or CO_OWNER_ROLE_ID in role_ids or RESELLER_ROLE_ID in role_ids:
            has_permission = True

    if not has_permission:
        await interaction.response.send_message("❌ You do not have permission to use this command.", ephemeral=True)
        return

    # Generate key
    key = f"BOOST-{''.join(random.choices(string.ascii_uppercase + string.digits, k=4))}-{''.join(random.choices(string.ascii_uppercase + string.digits, k=4))}-{''.join(random.choices(string.ascii_uppercase + string.digits, k=4))}"
    
    cursor = db_conn.cursor()
    cursor.execute("INSERT INTO licenses (key, duration) VALUES (?, ?)", (key, duration))
    db_conn.commit()
    
    embed = discord.Embed(title="🔑 Key Generated", color=discord.Color.blue())
    embed.add_field(name="Key", value=f"`{key}`", inline=False)
    embed.add_field(name="Duration", value=duration.capitalize(), inline=True)
    embed.set_footer(text=f"Generated by {interaction.user}")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="redeem_bootbot_license", description="Redeem a boost key", guild=discord.Object(id=GUILD_ID))
async def redeem_bootbot_license(interaction: discord.Interaction, key: str):
    cursor = db_conn.cursor()
    cursor.execute("SELECT duration FROM licenses WHERE key = ? AND redeemed = 0", (key,))
    lic = cursor.fetchone()
    
    if lic:
        duration = lic[0]
        expiry = None
        now = datetime.datetime.now()
        
        if duration == '1day': expiry = now + datetime.timedelta(days=1)
        elif duration == '1week': expiry = now + datetime.timedelta(weeks=1)
        elif duration == '1month': expiry = now + datetime.timedelta(days=30)
        elif duration == '1year': expiry = now + datetime.timedelta(days=365)
        
        expiry_str = expiry.strftime('%Y-%m-%d %H:%M:%S') if expiry else None
        
        cursor.execute("UPDATE licenses SET redeemed = 1, redeemed_by = ? WHERE key = ?", (str(interaction.user.id), key))
        cursor.execute("INSERT OR REPLACE INTO users (user_id, expiry) VALUES (?, ?)", (str(interaction.user.id), expiry_str))
        db_conn.commit()
        
        embed = discord.Embed(title="✅ Access Granted", description="Bootbot has been unlocked! You can now use all features.", color=discord.Color.green())
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        await interaction.response.send_message("❌ Invalid or already redeemed key.", ephemeral=True)

@bot.tree.command(name="delete-boost-key", description="Delete an existing boost key", guild=discord.Object(id=GUILD_ID))
async def delete_key(interaction: discord.Interaction, key: str):
    cursor = db_conn.cursor()
    cursor.execute("DELETE FROM licenses WHERE key = ?", (key,))
    db_conn.commit()
    await interaction.response.send_message(f"🗑️ Key `{key}` deleted.", ephemeral=True)

# --- Dashboard & Management ---
@bot.tree.command(name="dashboard", description="View dashboard links", guild=discord.Object(id=GUILD_ID))
async def dashboard(interaction: discord.Interaction):
    has_permission = False
    if interaction.user.guild_permissions.administrator:
        has_permission = True
    elif hasattr(interaction.user, "roles"):
        role_ids = [role.id for role in interaction.user.roles]
        if OWNER_ROLE_ID in role_ids:
            has_permission = True

    if not has_permission:
        await interaction.response.send_message("❌ You do not have permission to view the dashboard.", ephemeral=True)
        return
        
    port = os.environ.get("PORT", "8080")
    domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN")
    if domain:
        url = f"https://{domain}"
    else:
        url = f"http://localhost:{port}"
        
    await interaction.response.send_message(f"🔗 **Dashboard is live at:** {url}", ephemeral=True)

class AutobuyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        
        base_url = "https://av0idkxrried.sell.app"
        
        self.add_item(discord.ui.Button(label="1 Day ($3.50)", url=base_url))
        self.add_item(discord.ui.Button(label="1 Week ($9.00)", url=base_url))
        self.add_item(discord.ui.Button(label="1 Month ($15.00)", url=base_url))
        self.add_item(discord.ui.Button(label="1 Year ($25.00)", url=base_url))
        self.add_item(discord.ui.Button(label="Lifetime ($30.00)", url=base_url))

@bot.tree.command(name="setup-autobuy", description="Setup autobuy integration for your server", guild=discord.Object(id=GUILD_ID))
async def setup_autobuy(interaction: discord.Interaction):
    # Only allow Admin to setup panel
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You do not have permission to use this command.", ephemeral=True)
        return
        
    embed = discord.Embed(
        title="<a:Monster52:1504766603122966609> ! av0id/kxrried <a:Monster52:1504766603122966609>",
        description=(
            "The only payment method we take is:\n"
            "<:PayPal:1505246719187615836> **PayPal**\n\n"
            "If you ask for another payment method we will close the ticket, as it is Stated that these are the ONLY that we accept.\n\n"
            "**Prices:**\n"
            "• 1 Day: $3.50\n"
            "• 1 Week: $9.00\n"
            "• 1 Month: $15.00\n"
            "• 1 Year: $25.00\n"
            "• Lifetime: $30.00\n\n"
            "[Join Support Server](https://discord.gg/w8mH7DPpj)"
        ),
        color=discord.Color.purple()
    )
    
    await interaction.response.send_message("✅ Autobuy panel created!", ephemeral=True)
    await interaction.channel.send(embed=embed, view=AutobuyView())

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
    if not file.filename.endswith(".txt"):
        await interaction.response.send_message("❌ Please upload a `.txt` file.", ephemeral=True)
        return
        
    await interaction.response.defer(ephemeral=True)
    content = await file.read()
    
    mode = "a" if os.path.exists("tokens.txt") else "w"
    with open("tokens.txt", mode) as f:
        f.write("\n" + content.decode("utf-8"))
        
    await interaction.followup.send("📥 Tokens successfully saved to stock!")

@bot.tree.command(name="destock-tokens", description="Remove tokens from stock", guild=discord.Object(id=GUILD_ID))
async def destock_tokens(interaction: discord.Interaction, amount: int):
    await interaction.response.send_message(f"📤 Removed `{amount}` tokens from stock.", ephemeral=True)

@bot.tree.command(name="send-tokens", description="Send tokens to a user", guild=discord.Object(id=GUILD_ID))
async def send_tokens(interaction: discord.Interaction, user: discord.User, amount: int):
    await interaction.response.send_message(f"💸 Sent `{amount}` tokens to {user.mention}.", ephemeral=True)

if __name__ == "__main__":
    bot.run(TOKEN)
