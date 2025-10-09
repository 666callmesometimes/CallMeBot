import os
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
import asyncio
import threading

# === ŁADOWANIE TOKENA Z .ENV ===
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# === KONFIGURACJA ===
GUILD_ID = 1283847799154413609
MARKETPLACE_CATEGORY_ID = 1283892372635127818

# ID ról
ADMIN_ROLE_ID = 1424068271954595870
MOD_ROLE_ID = 1424068385292947576

# === INTENTS ===
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True
intents.presences = True


# === DEFINICJA BOTA ===
class MyBot(commands.Bot):
    async def setup_hook(self):
        # Uruchom keep_alive po starcie
        self.loop.create_task(self.keep_alive())

    async def keep_alive(self):
        await self.wait_until_ready()
        while not self.is_closed():
            print("✅ Bot jest online i aktywny (keep-alive).")
            await asyncio.sleep(600)  # 10 minut


bot = MyBot(command_prefix="!", intents=intents)


# ===== DEKORATOR DLA ADMIN + MOD =====
def is_admin_or_mod():
    async def predicate(interaction: discord.Interaction):
        member = interaction.user
        admin_role = discord.utils.get(member.roles, id=ADMIN_ROLE_ID)
        mod_role = discord.utils.get(member.roles, id=MOD_ROLE_ID)
        return admin_role or mod_role
    return app_commands.check(predicate)


# ===== USUWANIE STARYCH KOMEND =====
async def clear_guild_commands():
    guild = discord.Object(id=GUILD_ID)
    await bot.tree.sync(guild=guild)
    current_commands = await bot.tree.fetch_commands(guild=guild)
    for cmd in current_commands:
        await bot.tree.remove_command(cmd.name, guild=guild)
    print("✅ Wszystkie stare komendy w guildzie zostały usunięte.")


# ===== KOMENDA BLOKUJĄCA =====
@bot.tree.command(name="mp-block", description="Zablokuj użytkownikowi dostęp do Marketplace")
@app_commands.describe(uzytkownik="Użytkownik, który ma być zablokowany")
@is_admin_or_mod()
async def mp_block(interaction: discord.Interaction, uzytkownik: discord.Member):
    guild = interaction.guild
    category = guild.get_channel(MARKETPLACE_CATEGORY_ID)

    if not category:
        await interaction.response.send_message("❌ Nie znaleziono kategorii Marketplace.", ephemeral=True)
        return

    overwrite = discord.PermissionOverwrite(view_channel=False, send_messages=False)

    await category.set_permissions(uzytkownik, overwrite=overwrite)
    for channel in category.channels:
        await channel.set_permissions(uzytkownik, overwrite=overwrite)

    await interaction.response.send_message(
        f"🔒 Użytkownik {uzytkownik.mention} został **zablokowany** w sekcji {category.name}.",
        ephemeral=False
    )


# ===== KOMENDA ODBLOKOWUJĄCA =====
@bot.tree.command(name="mp-unblock", description="Odblokuj użytkownikowi dostęp do Marketplace")
@app_commands.describe(uzytkownik="Użytkownik, który ma zostać odblokowany")
@is_admin_or_mod()
async def mp_unblock(interaction: discord.Interaction, uzytkownik: discord.Member):
    guild = interaction.guild
    category = guild.get_channel(MARKETPLACE_CATEGORY_ID)

    if not category:
        await interaction.response.send_message("❌ Nie znaleziono kategorii Marketplace.", ephemeral=True)
        return

    await category.set_permissions(uzytkownik, overwrite=None)
    for channel in category.channels:
        await channel.set_permissions(uzytkownik, overwrite=None)

    await interaction.response.send_message(
        f"✅ Użytkownik {uzytkownik.mention} został **odblokowany** w sekcji {category.name}.",
        ephemeral=False
    )


# ===== KOMENDA POKAZUJĄCA ZABLOKOWANYCH =====
@bot.tree.command(name="mp-blocked-list", description="Pokaż listę użytkowników zablokowanych w Marketplace")
@is_admin_or_mod()
async def mp_blocked(interaction: discord.Interaction):
    guild = interaction.guild
    category = guild.get_channel(MARKETPLACE_CATEGORY_ID)

    if not category:
        await interaction.response.send_message("❌ Nie znaleziono kategorii Marketplace.", ephemeral=True)
        return

    blocked_members = []
    for target, overwrite in category.overwrites.items():
        if isinstance(target, discord.Member) and overwrite.view_channel is False:
            blocked_members.append(target.mention)

    if blocked_members:
        msg = "🔒 Zablokowani użytkownicy w Marketplace:\n" + "\n".join(blocked_members)
    else:
        msg = "✅ Brak zablokowanych użytkowników w Marketplace."

    await interaction.response.send_message(msg, ephemeral=False)


# ===== KOMENDA SAY =====
@bot.tree.command(name="say", description="Bot wysyła wiadomość o podanej treści.")
@app_commands.describe(tresc="Treść wiadomości, którą bot ma wysłać.")
@is_admin_or_mod()
async def say(interaction: discord.Interaction, tresc: str):
    try:
        await interaction.response.send_message(
            f"✅ Wiadomość została wysłana: `{tresc}`", ephemeral=True
        )
        await interaction.channel.send(tresc)
    except Exception as e:
        await interaction.response.send_message(f"❌ Błąd przy wysyłaniu wiadomości: {e}", ephemeral=True)


# ===== GLOBALNA OBSŁUGA BŁĘDÓW =====
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.CheckFailure):
        await interaction.response.send_message("🚫 Nie masz uprawnień do użycia tej komendy.", ephemeral=True)
    else:
        await interaction.response.send_message(f"❌ Wystąpił błąd: {error}", ephemeral=True)


# ===== START BOTA =====
@bot.event
async def on_ready():
    print(f"✅ Bot zalogowany jako {bot.user}")

    await clear_guild_commands()
    await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
    await bot.tree.sync()

    print("✅ Komendy zsynchronizowane i gotowe do użycia w guildzie.")


# ===== SERWER KEEP-ALIVE =====
def run_http_server():
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class KeepAliveHandler(BaseHTTPRequestHandler):
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
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))

        def log_message(self, format, *args):
            return  # Wyłączenie logów

    PORT = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("", PORT), KeepAliveHandler)
    print(f"🌐 HTTP server działa na porcie {PORT}")
    server.serve_forever()



# ===== START SERWERA I BOTA =====
threading.Thread(target=run_http_server, daemon=True).start()
bot.run(TOKEN)



