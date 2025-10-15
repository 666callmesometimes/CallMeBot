import os
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
import asyncio
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# === ŁADOWANIE TOKENA ===
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# === KONFIGURACJA ===
GUILD_ID = 1283847799154413609
MARKETPLACE_CATEGORY_ID = 1283892372635127818
VERIFY_MESSAGE_ID = 1423987710430806016
VERIFY_EMOJI = "✅"

ADMIN_ROLE_ID = 1424068271954595870
MOD_ROLE_ID = 1424068385292947576
VERIFIED_ROLE_ID = 1283848145066790933
MEMBER_COUNT_CHANNEL_ID = 1425907738428440789
WELCOME_CHANNEL_ID = 1331993023772364879
RULES_CHANNEL_ID = 1283847799154413611

# === INTENTS ===
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True
intents.presences = True

# === DEFINICJA BOTA ===
class MyBot(commands.Bot):
    async def setup_hook(self):
        self.loop.create_task(self.keep_alive())
        self.loop.create_task(self.watchdog())
        self.loop.create_task(member_count_loop())
        self.loop.create_task(self.smart_reconnect())

    async def keep_alive(self):
        """Loguje status co 10 minut."""
        await self.wait_until_ready()
        while not self.is_closed():
            try:
                print(f"✅ Bot aktywny jako {self.user} (ping: {round(self.latency*1000)} ms)")
            except Exception as e:
                print(f"⚠️ Keep-alive error: {e}")
            await asyncio.sleep(600)

    async def watchdog(self):
        """Restartuje proces, jeśli bot przestaje odpowiadać."""
        await self.wait_until_ready()
        while not self.is_closed():
            await asyncio.sleep(300)
            if self.latency > 10 or not self.is_ws_ratelimited():
                continue
            print("⚠️ Watchdog wykrył utratę połączenia — restart...")
            os._exit(1)

    async def smart_reconnect(self):
        """Monitoruje błędy połączenia z Discordem i próbuje reconnect."""
        await self.wait_until_ready()
        while not self.is_closed():
            try:
                await asyncio.sleep(120)
                # Testowe pingnięcie API
                _ = await self.application_info()
            except discord.HTTPException as e:
                if e.status in (429, 500, 502, 503):
                    print(f"🚨 SmartReconnect: wykryto błąd {e.status}, ponawiam połączenie...")
                    try:
                        await self.close()
                        await asyncio.sleep(5)
                        await self.start(TOKEN)
                    except Exception as err:
                        print(f"❌ SmartReconnect nie powiódł się: {err}")
                        os._exit(1)
            except Exception as e:
                print(f"⚠️ SmartReconnect błąd: {e}")

bot = MyBot(command_prefix="!", intents=intents)

# === DEKORATOR ADMIN/MOD ===
def is_admin_or_mod():
    async def predicate(interaction: discord.Interaction):
        member = interaction.user
        admin = discord.utils.get(member.roles, id=ADMIN_ROLE_ID)
        mod = discord.utils.get(member.roles, id=MOD_ROLE_ID)
        return admin or mod
    return app_commands.check(predicate)

# === KOMENDY ===
@bot.tree.command(name="mp-block", description="Zablokuj użytkownikowi dostęp do Marketplace")
@is_admin_or_mod()
@app_commands.describe(uzytkownik="Użytkownik, który ma być zablokowany")
async def mp_block(interaction: discord.Interaction, uzytkownik: discord.Member):
    category = interaction.guild.get_channel(MARKETPLACE_CATEGORY_ID)
    if not category:
        await interaction.response.send_message("❌ Nie znaleziono kategorii Marketplace.", ephemeral=True)
        return
    overwrite = discord.PermissionOverwrite(view_channel=False, send_messages=False)
    await category.set_permissions(uzytkownik, overwrite=overwrite)
    for ch in category.channels:
        await ch.set_permissions(uzytkownik, overwrite=overwrite)
    await interaction.response.send_message(
        f"🔒 {uzytkownik.mention} został zablokowany w {category.name}.", ephemeral=False
    )

@bot.tree.command(name="mp-unblock", description="Odblokuj użytkownikowi dostęp do Marketplace")
@is_admin_or_mod()
@app_commands.describe(uzytkownik="Użytkownik, który ma zostać odblokowany")
async def mp_unblock(interaction: discord.Interaction, uzytkownik: discord.Member):
    category = interaction.guild.get_channel(MARKETPLACE_CATEGORY_ID)
    if not category:
        await interaction.response.send_message("❌ Nie znaleziono kategorii Marketplace.", ephemeral=True)
        return
    await category.set_permissions(uzytkownik, overwrite=None)
    for ch in category.channels:
        await ch.set_permissions(uzytkownik, overwrite=None)
    await interaction.response.send_message(
        f"✅ {uzytkownik.mention} został odblokowany w {category.name}.", ephemeral=False
    )

@bot.tree.command(name="say", description="Bot wysyła wiadomość na wybrany kanał.")
@is_admin_or_mod()
@app_commands.describe(kanal="Kanał docelowy", treść="Treść wiadomości")
async def say(interaction: discord.Interaction, kanal: discord.TextChannel, treść: str):
    try:
        await kanal.send(treść)
        await interaction.response.send_message(f"✅ Wysłano na {kanal.mention}: {treść}", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Błąd: {e}", ephemeral=True)

# === POWITANIE ===
@bot.event
async def on_member_join(member):
    channel = bot.get_channel(WELCOME_CHANNEL_ID)
    if not channel:
        return
    embed = discord.Embed(
        title="👋 Witaj na serwerze!",
        description="Przeczytaj regulamin i zaakceptuj, by uzyskać dostęp do kanałów.",
        color=discord.Color.purple()
    )
    rules = bot.get_channel(RULES_CHANNEL_ID)
    if rules:
        button = discord.ui.Button(label="📜 Regulamin", style=discord.ButtonStyle.link,
                                   url=f"https://discord.com/channels/{member.guild.id}/{rules.id}")
        view = discord.ui.View()
        view.add_item(button)
        await channel.send(content=f"{member.mention}", embed=embed, view=view)

# === LICZNIK CZŁONKÓW ===
async def member_count_loop():
    await bot.wait_until_ready()
    guild = bot.get_guild(GUILD_ID)
    channel = bot.get_channel(MEMBER_COUNT_CHANNEL_ID)
    while not bot.is_closed():
        try:
            if guild and channel:
                await channel.edit(name=f"Członkowie: {guild.member_count}")
        except Exception as e:
            print(f"⚠️ Błąd aktualizacji licznika: {e}")
        await asyncio.sleep(3600)

# === REAKCJA WERYFIKACYJNA ===
@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    if payload.message_id != VERIFY_MESSAGE_ID or str(payload.emoji) != VERIFY_EMOJI:
        return
    guild = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)
    if not member or member.bot:
        return
    role = guild.get_role(VERIFIED_ROLE_ID)
    if role not in member.roles:
        await member.add_roles(role, reason="Weryfikacja przez reakcję")
        channel = bot.get_channel(WELCOME_CHANNEL_ID)
        if channel:
            embed = discord.Embed(
                title="✅ Weryfikacja zakończona!",
                description="Twoje konto zostało pomyślnie zweryfikowane 🎉",
                color=discord.Color.orange()
            )
            await channel.send(content=f"{member.mention}", embed=embed)

# === SYNC KOMEND ===
@bot.event
async def on_ready():
    print(f"✅ Zalogowano jako {bot.user}")
    try:
        synced = await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        print(f"✅ Zsynchronizowano {len(synced)} komend.")
    except Exception as e:
        print(f"⚠️ Błąd synchronizacji komend: {e}")

# === HTTP KEEP-ALIVE ===
def run_http_server():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
                html = """
                <!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CallMeBot - Status page</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r121/three.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/vanta@latest/dist/vanta.net.min.js"></script>
<style>
    body {
         margin: 0; 
         padding: 0;
         overflow: hidden;
         display: flex;
         justify-content: center;
         align-items: center;
         font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;

    }
    h1 {
        color: white;
        font-size: 4rem;
        margin: 0;
    }
    p {
        color: #777;
        font-size: 1rem;
        font-weight: 500;
    }
    #text {
        text-align: center;
        height: 100%;
        display: flex;
        justify-content: center;
        align-items: center;
        flex-direction: column;

    }
</style>
</head>
<body>
    <div id="my-background" style="width: 100vw; height: 100vh;">
        <div id="text">
            <h1>Bot is alive and running</h1>
            <p>Everything looks good — your Discord bot is online 🚀</p>
        </div>

    </div>
<script>
  VANTA.NET({
    el: "#my-background",
    backgroundAlpha: 1,
    backgroundColor: 0xe0318,
    color: 0x4a1a32,
    gyroControls: false,
    maxDistance: 24,
    minHeight: 200,
    minWidth: 200,
    mouseControls: true,
    points: 18,
    scale: 1,
    scaleMobile: 1,
    showDots: true,
    spacing: 16,
    touchControls: false
  });
</script>
</body>
</html>
            """
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
        def log_message(self, *args):
            return
    PORT = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("", PORT), Handler)
    print(f"🌐 Keep-alive HTTP server on port {PORT}")
    server.serve_forever()

threading.Thread(target=run_http_server, daemon=True).start()
bot.run(TOKEN)




