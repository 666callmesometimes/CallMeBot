import os
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
import asyncio
import threading
from discord.ui import View, Button
from http.server import BaseHTTPRequestHandler, HTTPServer

# === ŁADOWANIE TOKENA Z .ENV ===
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
        # Keep-alive + watchdog
        self.loop.create_task(self.keep_alive())
        self.loop.create_task(self.watchdog())
        # licznik członków
        self.loop.create_task(member_count_loop())

    async def keep_alive(self):
        """Task utrzymujący aktywność i logujący stan bota."""
        await self.wait_until_ready()
        while not self.is_closed():
            try:
                print(f"✅ Bot aktywny jako {self.user} (ping: {round(self.latency*1000)} ms)")
            except Exception as e:
                print(f"⚠️ Błąd keep-alive: {e}")
            await asyncio.sleep(600)

    async def watchdog(self):
        """Restartuje proces, jeśli bot utraci połączenie z Discordem."""
        await self.wait_until_ready()
        while not self.is_closed():
            await asyncio.sleep(300)  # co 5 minut
            if not self.is_ws_ratelimited() and self.latency < 10:
                continue
            print("⚠️ Watchdog wykrył problem z połączeniem. Restart procesu...")
            os._exit(1)  # Render automatycznie wznowi proces

bot = MyBot(command_prefix="!", intents=intents)

# ===== DEKORATOR DLA ADMIN + MOD =====
def is_admin_or_mod():
    async def predicate(interaction: discord.Interaction):
        member = interaction.user
        admin_role = discord.utils.get(member.roles, id=ADMIN_ROLE_ID)
        mod_role = discord.utils.get(member.roles, id=MOD_ROLE_ID)
        return admin_role or mod_role
    return app_commands.check(predicate)

# ===== KOMENDY =====
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

@bot.tree.command(name="say", description="Bot wysyła wiadomość o podanej treści na wybrany kanał.")
@app_commands.describe(
    kanal="Kanał, na który bot ma wysłać wiadomość",
    treść="Treść wiadomości, którą bot ma wysłać"
)
@is_admin_or_mod()
async def say(interaction: discord.Interaction, kanal: discord.TextChannel, treść: str):
    try:
        await kanal.send(treść)
        await interaction.response.send_message(
            f"✅ Wysłano wiadomość na {kanal.mention}:\n> {treść}",
            ephemeral=True
        )
    except Exception as e:
        await interaction.response.send_message(
            f"❌ Wystąpił błąd przy wysyłaniu wiadomości: {e}",
            ephemeral=True
        )

@bot.tree.command(name="clear", description="Usuń określoną liczbę wiadomości z kanału lub wszystkie (parametr 'all').")
@app_commands.describe(ilosc="Liczba wiadomości do usunięcia lub 'all'")
@is_admin_or_mod()
async def clear(interaction: discord.Interaction, ilosc: str):
    await interaction.response.defer(ephemeral=True)
    channel = interaction.channel
    if ilosc.lower() == "all":
        try:
            while True:
                deleted = await channel.purge(limit=100)
                if len(deleted) < 100:
                    break
            await interaction.followup.send(f"✅ Usunięto wszystkie wiadomości w kanale {channel.mention}.")
        except Exception as e:
            await interaction.followup.send(f"❌ Błąd: {e}")
    else:
        try:
            count = int(ilosc)
            if count < 1 or count > 1000:
                await interaction.followup.send("❌ Liczba musi być 1-1000.")
                return
            deleted = await channel.purge(limit=count + 1)
            await interaction.followup.send(f"✅ Usunięto {len(deleted)-1} wiadomości z {channel.mention}.")
        except Exception as e:
            await interaction.followup.send(f"❌ Błąd: {e}")

# ===== POWITANIE NOWEGO UŻYTKOWNIKA =====
@bot.event
async def on_member_join(member):
    guild = member.guild
    welcome_channel = bot.get_channel(WELCOME_CHANNEL_ID)
    if not welcome_channel:
        print("⚠️ Nie znaleziono kanału powitalnego!")
        return
    await welcome_channel.send(f"Witaj {member.mention}! 🎉")
    embed = discord.Embed(
        title=f"👋 Cieszymy się, że dołączyłeś {member.name}!",
        description=("Aby w pełni korzystać z serwera, przeczytaj **regulamin** klikając w przycisk poniżej. "
                     "Po zaakceptowaniu, Carl-bot nada Ci odpowiednią rolę i odblokuje wszystkie kanały."),
        color=discord.Color.purple()
    )
    rules_channel = bot.get_channel(RULES_CHANNEL_ID)
    if rules_channel:
        view = View()
        button = Button(
            label="📜 Przejdź do regulaminu",
            style=discord.ButtonStyle.link,
            url=f"https://discord.com/channels/{guild.id}/{rules_channel.id}"
        )
        view.add_item(button)
        await welcome_channel.send(embed=embed, view=view)
    else:
        await welcome_channel.send(embed=embed)
    print(f"📨 Wysłano powitanie dla {member}.")

# ===== LICZNIK CZŁONKÓW =====
async def member_count_loop():
    await bot.wait_until_ready()
    guild = bot.get_guild(GUILD_ID)
    channel = bot.get_channel(MEMBER_COUNT_CHANNEL_ID)
    if not guild or not channel:
        print("⚠️ Nie znaleziono guildy lub kanału licznika!")
        return
    while not bot.is_closed():
        try:
            await channel.edit(name=f"Członkowie: {guild.member_count}")
        except Exception as e:
            print(f"⚠️ Błąd aktualizacji licznika: {e}")
        await asyncio.sleep(3600)

# ===== SYSTEM WERYFIKACJI =====
@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    if payload.message_id != VERIFY_MESSAGE_ID or str(payload.emoji) != VERIFY_EMOJI:
        return
    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return
    member = guild.get_member(payload.user_id)
    if not member or member.bot:
        return
    role = guild.get_role(VERIFIED_ROLE_ID)
    if not role:
        print("⚠️ Brak roli 'Zweryfikowany'")
        return
    if role in member.roles:
        return
    await member.add_roles(role, reason="Weryfikacja przez reakcję")
    welcome_channel = guild.get_channel(WELCOME_CHANNEL_ID)
    if welcome_channel:
        embed = discord.Embed(
            title="✅ Weryfikacja zakończona!",
            description="Twoje konto zostało pomyślnie zweryfikowane 🎉",
            color=discord.Color.orange()
        )
        await welcome_channel.send(content=f"{member.mention}", embed=embed)

@bot.event
async def on_ready():
    print(f"✅ Bot zalogowany jako {bot.user}")
    try:
        synced = await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        print(f"✅ Zsynchronizowano {len(synced)} komend dla guildy.")
    except Exception as e:
        print(f"⚠️ Błąd synchronizacji komend: {e}")

# ===== PROSTY HTTP KEEP-ALIVE =====
def run_http_server():
    class KeepAliveHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"<h1>Bot is alive and running 🚀</h1>")
        def log_message(self, format, *args):
            return
    PORT = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("", PORT), KeepAliveHandler)
    print(f"🌐 HTTP server dziala na porcie {PORT}")
    server.serve_forever()

threading.Thread(target=run_http_server, daemon=True).start()
bot.run(TOKEN)
