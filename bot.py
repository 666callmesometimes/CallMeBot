import os
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
import asyncio
import threading
from discord.ui import View, Button

# === ŁADOWANIE TOKENA Z .ENV ===
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# === KONFIGURACJA ===
GUILD_ID = 1283847799154413609
MARKETPLACE_CATEGORY_ID = 1283892372635127818


VERIFY_MESSAGE_ID = 1423987710430806016  # ID wiadomości w kanale #zasady
VERIFY_EMOJI = "✅"

# ID ról
ADMIN_ROLE_ID = 1424068271954595870
MOD_ROLE_ID = 1424068385292947576
VERIFIED_ROLE_ID = 1283848145066790933

# Kanały
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
        # Keep-alive task
        self.loop.create_task(self.keep_alive())
        # Uruchomienie licznika członków co godzinę
        self.loop.create_task(member_count_loop())

    async def keep_alive(self):
        await self.wait_until_ready()
        while not self.is_closed():
            print("✅ Bot jest online i aktywny (keep-alive).")
            await asyncio.sleep(600)

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

# ===== KOMENDY BLOKUJĄCE/ODBLOKOWUJĄCE =====
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

# ===== KOMENDA SAY =====
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

# ===== CZYSZCZENIE WIADOMOŚCI =====
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

# ===== LICZNIK CZŁONKÓW CO GODZINĘ =====
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

# ===== SYSTEM WERYFIKACJI NA EMOTKĘ (DODANA ZMIANA) =====
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

    # ---- DODANE SPRAWDZENIE ----
    if role in member.roles:
        # Użytkownik już jest zweryfikowany, nie wysyłaj powiadomienia i nie dodawaj roli
        return

    await member.add_roles(role, reason="Weryfikacja przez reakcję")

    welcome_channel = guild.get_channel(WELCOME_CHANNEL_ID)
    if welcome_channel:
    embed = discord.Embed(
        title="✅ Weryfikacja zakończona!",
        description="Twoje konto zostało pomyślnie zweryfikowane 🎉",
        color=discord.Color.orange()
    )
    await welcome_channel.send(
        content=f"{member.mention}",  # 🔔 ping użytkownika
        embed=embed
    )


    channel = guild.get_channel(RULES_CHANNEL_ID)
    message = await channel.fetch_message(VERIFY_MESSAGE_ID)
    for reaction in message.reactions:
        if str(reaction.emoji) == VERIFY_EMOJI:
            async for user in reaction.users():
                if user.id == member.id:
                    break
            else:
                await message.add_reaction(VERIFY_EMOJI)

@bot.event
async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent):
    if payload.message_id != VERIFY_MESSAGE_ID or str(payload.emoji) != VERIFY_EMOJI:
        return

    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return

    member = guild.get_member(payload.user_id)
    if not member or member.bot:
        return

    channel = guild.get_channel(RULES_CHANNEL_ID)
    message = await channel.fetch_message(VERIFY_MESSAGE_ID)
    await message.add_reaction(VERIFY_EMOJI)

@bot.event
async def on_member_remove(member: discord.Member):
    guild = member.guild
    channel = guild.get_channel(RULES_CHANNEL_ID)

    try:
        message = await channel.fetch_message(VERIFY_MESSAGE_ID)
        await message.remove_reaction(VERIFY_EMOJI, member)
        print(f"🧹 Usunięto reakcję po wyjściu {member.name}")
    except Exception as e:
        print(f"⚠️ Błąd przy usuwaniu reakcji: {e}")


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
            return
    PORT = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("", PORT), KeepAliveHandler)
    print(f"🌐 HTTP server działa na porcie {PORT}")
    server.serve_forever()

threading.Thread(target=run_http_server, daemon=True).start()
bot.run(TOKEN)



