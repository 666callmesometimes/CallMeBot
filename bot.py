import os
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

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

bot = commands.Bot(command_prefix="!", intents=intents)

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

    # Blokada kategorii
    await category.set_permissions(uzytkownik, overwrite=overwrite)
    # Blokada wszystkich kanałów w kategorii
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

    # Usunięcie ograniczeń z kategorii
    await category.set_permissions(uzytkownik, overwrite=None)
    # Usunięcie ograniczeń ze wszystkich kanałów w kategorii
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

    # Usuń stare komendy
    await clear_guild_commands()

    # Synchronizacja komend lokalnie i globalnie
    await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
    await bot.tree.sync()

    print("✅ Komendy zsynchronizowane i gotowe do użycia w guildzie.")


# ===== URUCHOMIENIE BOTA =====
bot.run(TOKEN)
