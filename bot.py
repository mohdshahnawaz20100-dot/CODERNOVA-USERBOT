#!/usr/bin/env python3
# CODERNOVA USERBOT - Multi-User Version (COMPLETE FINAL - PERFECT TIMING)

import os, sys, json, asyncio, random, re, time, logging, shutil
from datetime import datetime
from pathlib import Path
from urllib.parse import quote as url_quote

from aiohttp import web
import aiohttp

from motor.motor_asyncio import AsyncIOMotorClient

from telethon import TelegramClient, events, functions
from telethon.tl.types import (
    ChatBannedRights, User, ChannelParticipantsAdmins, ChatAdminRights,
    MessageMediaWebPage, MessageMediaUnsupported
)
from telethon.errors import (
    FloodWaitError, SessionPasswordNeededError, PhoneCodeInvalidError,
    PhoneCodeExpiredError, PasswordHashInvalidError
)
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest, DeletePhotosRequest
from telethon.tl.functions.contacts import BlockRequest, UnblockRequest
from telethon.tl.functions.messages import EditChatDefaultBannedRightsRequest
from telethon.tl.functions.channels import EditBannedRequest, GetParticipantRequest, EditAdminRequest, EditTitleRequest
from telethon.tl.functions.messages import EditChatTitleRequest
from telethon.tl.functions.messages import SendReactionRequest
from telethon.tl.types import ReactionEmoji
from telethon.sessions import StringSession

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

# ═══════════════ CONFIG ═══════════════
API_ID       = int(os.getenv("API_ID", "39662504"))
API_HASH     = os.getenv("API_HASH", "efa25173b3be311d4573cc534c56c893")
BOT_TOKEN    = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
OWNER_ID     = int(os.getenv("OWNER_ID", "8678930384"))
MONGO_URI    = os.getenv("MONGO_URI", "")

WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "1e74d518ef89c703e791594f953df2a4")
NEWS_API_KEY    = os.getenv("NEWS_API_KEY", "c25f877f4c654be7980fee363be93302")
GROQ_API_KEY    = os.getenv("GROQ_API_KEY", "")

DATA_DIR = Path(os.getenv("DATA_DIR", "/tmp/clonex_data"))
DATA_DIR.mkdir(exist_ok=True, parents=True)
TEMP_DIR = DATA_DIR / "temp"
TEMP_DIR.mkdir(exist_ok=True, parents=True)

GHOST_IMG_LOCAL = DATA_DIR / "ghost_cached.jpg"
GHOST_IMG_URL = "https://i.ibb.co/MDZVcWjh/IMG-20260921-203641-296.jpg"

CLEANUP_DAYS = 45
IST_TZ = ZoneInfo("Asia/Kolkata")

# ═══════════════ SMART TIMING ═══════════════
# 🎯 PERFECT OFFSET: 10 Millisecond (Singapore server ke liye perfect)
PING_OFFSET = 0.090

logging.basicConfig(format='%(asctime)s [%(levelname)s] %(message)s',
                    level=logging.INFO, datefmt='%H:%M:%S')
log = logging.getLogger("CN_USERBOT")

# ═══════════════ MONGODB ═══════════════
mongo_client = None
users_col = None
all_users_col = None
user_data_col = None
blocked_col = None
cmd_usage_col = None
cmd_blocked_col = None
sched_col = None

async def init_mongo():
    global mongo_client, users_col, all_users_col, user_data_col, blocked_col, cmd_usage_col, cmd_blocked_col, sched_col
    if not MONGO_URI:
        log.warning("⚠️ MONGO_URI not set")
        return False
    try:
        mongo_client = AsyncIOMotorClient(
            MONGO_URI,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=10000,
            socketTimeoutMS=45000,
            maxPoolSize=25
        )
        db = mongo_client["clonex_db"]
        users_col = db["logged_users"]
        all_users_col = db["all_users"]
        user_data_col = db["user_data"]
        blocked_col = db["blocked_users"]
        cmd_usage_col = db["command_usage"]
        cmd_blocked_col = db["command_blocked"]
        sched_col = db["scheduled_messages"]
        await mongo_client.admin.command('ping')
        log.info("✅ MongoDB connected")
        return True
    except Exception as e:
        log.error(f"❌ MongoDB: {e}")
        return False

users_db = {}
all_users_db = {}
user_data_cache = {}
blocked_users = set()
command_usage_db = {}
command_blocked_db = {}

async def load_all():
    global users_db, all_users_db, user_data_cache, blocked_users, command_usage_db, command_blocked_db
    if users_col is None:
        return
    try:
        users_db = {}
        async for d in users_col.find({}):
            uid = d.get("_id"); d.pop("_id", None); users_db[str(uid)] = d
        all_users_db = {}
        async for d in all_users_col.find({}):
            uid = d.get("_id"); d.pop("_id", None); all_users_db[str(uid)] = d
        user_data_cache = {}
        async for d in user_data_col.find({}):
            uid = d.get("_id"); d.pop("_id", None); user_data_cache[str(uid)] = d
        blocked_users = set()
        if blocked_col is not None:
            async for d in blocked_col.find({}):
                blocked_users.add(str(d.get("_id")))
        command_usage_db = {}
        if cmd_usage_col is not None:
            async for d in cmd_usage_col.find({}):
                uid = str(d.get("_id"))
                d.pop("_id", None)
                if "commands" in d:
                    command_usage_db[uid] = {"commands": d.get("commands", {}), "last_update": d.get("last_update", time.time())}
                else:
                    last_update = d.pop("last_update", time.time())
                    command_usage_db[uid] = {"commands": d, "last_update": last_update}
        command_blocked_db = {}
        if cmd_blocked_col is not None:
            async for d in cmd_blocked_col.find({}):
                uid = str(d.get("_id"))
                command_blocked_db[uid] = d.get("commands", [])
        log.info(f"✅ Loaded {len(users_db)} logged, {len(all_users_db)} all, {len(user_data_cache)} user_data, {len(blocked_users)} blocked")
    except Exception as e:
        log.error(f"load_all: {e}")

async def save_user(uid, data):
    if users_col is None: return
    try:
        d = dict(data); d["_id"] = str(uid)
        await users_col.update_one({"_id": str(uid)}, {"$set": d}, upsert=True)
    except Exception as e:
        log.error(f"save_user: {e}")

async def save_all_user(uid, data):
    if all_users_col is None: return
    try:
        d = dict(data); d["_id"] = str(uid)
        await all_users_col.update_one({"_id": str(uid)}, {"$set": d}, upsert=True)
    except Exception as e:
        log.error(f"save_all_user: {e}")

async def save_user_data(uid, data):
    if user_data_col is None: return
    try:
        d = dict(data); d["_id"] = str(uid)
        await user_data_col.update_one({"_id": str(uid)}, {"$set": d}, upsert=True)
    except Exception as e:
        log.error(f"save_user_data: {e}")

async def block_user_db(uid):
    uid = str(uid)
    blocked_users.add(uid)
    if blocked_col is not None:
        try:
            await blocked_col.update_one({"_id": uid}, {"$set": {"blocked_at": datetime.now().strftime("%d %b %Y, %I:%M %p")}}, upsert=True)
        except Exception as e:
            log.error(f"block_user_db: {e}")

async def unblock_user_db(uid):
    uid = str(uid)
    blocked_users.discard(uid)
    if blocked_col is not None:
        try:
            await blocked_col.delete_one({"_id": uid})
        except Exception as e:
            log.error(f"unblock_user_db: {e}")

async def log_command_usage(uid, command):
    uid = str(uid)
    try:
        if uid not in command_usage_db:
            command_usage_db[uid] = {"commands": {}, "last_update": time.time()}
        if "commands" not in command_usage_db[uid] or not isinstance(command_usage_db[uid].get("commands"), dict):
            command_usage_db[uid] = {"commands": command_usage_db[uid] if isinstance(command_usage_db[uid], dict) else {}, "last_update": time.time()}
        command_usage_db[uid]["commands"][command] = command_usage_db[uid]["commands"].get(command, 0) + 1
        command_usage_db[uid]["last_update"] = time.time()
        if cmd_usage_col is not None:
            await cmd_usage_col.update_one({"_id": uid}, {"$inc": {f"commands.{command}": 1}, "$set": {"last_update": time.time()}}, upsert=True)
    except Exception as e:
        log.error(f"log_command_usage: {e}")

async def cleanup_old_command_logs():
    global command_usage_db
    if cmd_usage_col is None: return
    try:
        cutoff_time = time.time() - (CLEANUP_DAYS * 24 * 60 * 60)
        result = await cmd_usage_col.delete_many({"last_update": {"$lt": cutoff_time}})
        if result.deleted_count > 0:
            log.info(f"🧹 Cleaned {result.deleted_count} old command logs")
            to_remove = []
            for uid, data in command_usage_db.items():
                last_update = data.get("last_update", 0) if isinstance(data, dict) else 0
                if not last_update or last_update < cutoff_time:
                    to_remove.append(uid)
            for uid in to_remove:
                command_usage_db.pop(uid, None)
    except Exception as e:
        log.error(f"cleanup_old_command_logs: {e}")

async def auto_cleanup_loop():
    while True:
        try:
            await cleanup_old_command_logs()
        except Exception as e:
            log.error(f"auto_cleanup_loop: {e}")
        await asyncio.sleep(24 * 60 * 60)

async def cleanup_temp_loop():
    while True:
        try:
            now = time.time()
            for f in TEMP_DIR.glob("*"):
                if f.is_file() and now - f.stat().st_mtime > 3600:
                    try: f.unlink()
                    except: pass
        except Exception as e:
            log.error(f"Temp cleanup: {e}")
        await asyncio.sleep(3600)

def get_user(uid):
    uid = str(uid)
    if uid not in users_db:
        users_db[uid] = {"logged_in": False, "phone": None, "tg_id": None, "tg_name": None, "tg_username": None, "session_string": None, "step": None, "phone_code_hash": None, "login_time": None}
    return users_db[uid]

def get_user_data(uid):
    uid = str(uid)
    if uid not in user_data_cache:
        user_data_cache[uid] = {}
    return user_data_cache[uid]

async def track_start(uid, name, username):
    uid = str(uid)
    if uid not in all_users_db:
        all_users_db[uid] = {"name": name, "username": username, "tg_id": uid, "first_seen": datetime.now().strftime("%d %b %Y, %I:%M %p")}
        await save_all_user(uid, all_users_db[uid])

if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
    log.error("❌ BOT_TOKEN missing"); exit(1)

SESSION_DIR = Path("/tmp/clonex_session")
SESSION_DIR.mkdir(exist_ok=True, parents=True)
bot = TelegramClient(
    str(SESSION_DIR / "clonex_bot"), API_ID, API_HASH,
    device_model="❛.𝁘ໍＣｌｏｎｅ Ｘ🎭.𝁘ໍ",
    system_version="VillainZBot",
    app_version="1.0"
).start(bot_token=BOT_TOKEN)
pending_clients = {}
user_bots = {}
broadcast_history = []
raid_state = {
    "reply": {},
    "rr": {},
    "flag": {},
    "hrr": {},
}

async def health_server():
    async def handle(request):
        return web.Response(text="✅ Codernova Multi-User Userbot Running")
    app = web.Application()
    app.router.add_get('/', handle)
    app.router.add_get('/health', handle)
    port = int(os.getenv('PORT', 8080))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    log.info(f"✅ Health on port {port}")
    await asyncio.Event().wait()

async def get_ghost_image_path():
    if GHOST_IMG_LOCAL.exists() and GHOST_IMG_LOCAL.stat().st_size > 1000:
        return str(GHOST_IMG_LOCAL)
    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(GHOST_IMG_URL) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    if len(data) > 1000:
                        with open(GHOST_IMG_LOCAL, "wb") as f:
                            f.write(data)
                        return str(GHOST_IMG_LOCAL)
    except Exception as e:
        log.warning(f"Ghost image download failed: {e}")
    return None

# ═══════════════ BOT COMMANDS ═══════════════
@bot.on(events.NewMessage(pattern='/start'))
async def start_h(event):
    uid = event.sender_id
    if str(uid) in blocked_users:
        return
    u = get_user(uid)
    try:
        s = await event.get_sender()
        name = ((s.first_name or "") + (" " + s.last_name if getattr(s, 'last_name', None) else "")).strip() or "Unknown"
        await track_start(uid, name, s.username or "None")
    except Exception:
        pass
    START_MEDIA = "https://files.catbox.moe/35bl05.mp4"
    if u["logged_in"]:
        caption = ("✅ **ᴀʟʀᴇᴀᴅʏ ʟᴏɢɢᴇᴅ ɪɴ!**\n"
                   "━━━━━━━━━━━━━━━━━━━━━\n\n"
                   "**🔹 ᴀᴠᴀɪʟᴀʙʟᴇ ᴄᴏᴍᴍᴀɴᴅs**\n"
                   "• `/help` — ʜᴇʟᴘ ᴍᴇɴᴜ\n"
                   "• `/status` — ʟᴏɢɪɴ sᴛᴀᴛᴜs\n"
                   "• `/logout` — ʟᴏɢᴏᴜᴛ\n\n"
                   "**💡 ɴᴏᴛᴇ:**\n"
                   "Apna userbot use karne ke liye kisi bhi chat me `.help` bhejo.\n\n"
                   "━━━━━━━━━━━━━━━━━━━━━\n"
                   "✨ **ᴘᴏᴡᴇʀᴇᴅ ʙʏ ᴠɪʟʟᴀɪɴ** 😎 ✨")
    else:
        caption = ("🎉 ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ ᴄʟᴏɴᴇx ᴜsᴇʀʙᴏᴛ 🎉\n"
                   "━━━━━━━━━━━━━━━━━━━━━\n\n"
                   "🛑 ʟᴏɢɪɴ sᴛᴇᴘs:\n\n"
                   "🔷  sᴇɴᴅ /ʟᴏɢɪɴ\n\n"
                   "🔷  sᴇɴᴅ ᴘʜᴏɴᴇ ɴᴜᴍʙᴇʀ (ᴡɪᴛʜ ᴄᴏᴜɴᴛʀʏ ᴄᴏᴅᴇ, ᴇ.ɢ. +𝟿𝟷𝟿𝟾𝟽𝟼𝟻𝟺𝟹𝟸𝟷𝟶)\n\n"
                   "🔷  sᴇɴᴅ ᴏᴛᴘ (sᴘᴀᴄᴇ ᴋᴇ sᴀᴀᴛʜ) (ᴇ.ɢ. 𝟷 𝟸 𝟹 𝟺 𝟻)\n\n"
                   "🔷  sᴇɴᴅ 𝟸ғᴀ ᴘᴀssᴡᴏʀᴅ (ɪғ ᴇɴᴀʙʟᴇᴅ)\n\n"
                   "━━━━━━━━━━━━━━━━━━━━━\n"
                   "🔐 ʀᴇᴀᴅʏ? ᴛʏᴘᴇ: /ʟᴏɢɪɴ\n\n"
                   "✨ ᴘᴏᴡᴇʀᴇᴅ ʙʏ ᴠɪʟʟᴀɪɴ 😎 ✨")
    try:
        await bot.send_file(event.chat_id, START_MEDIA, caption=caption, parse_mode='markdown', supports_streaming=True)
    except Exception:
        try:
            await bot.send_file(event.chat_id, START_MEDIA, caption=caption)
        except Exception:
            await event.reply(caption, parse_mode='markdown')

@bot.on(events.NewMessage(pattern='/help'))
async def help_h(event):
    uid = event.sender_id
    if str(uid) in blocked_users:
        return
    base = ("🛑 ❛.𝁘ໍＣｌｏｎｅ Ｘ🎭.𝁘ໍ Bot\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🔹 **Login:**\n• `/start`\n• `/login`\n• `/logout`\n• `/status`\n\n"
            "🔹 **Userbot:**\nLogin ke baad kisi bhi chat me `.alive` bhejo\n\n")
    if uid == OWNER_ID:
        await event.reply(base + "👑 **Owner:**\n• `/users`\n• `/live`\n• `/remove <tg_id>`\n• `/broadcast <msg>`\n• `/delbroadcast`\n• `/stats`\n• `/block <id>`\n• `/unblock <id>`\n• `/blocked`\n• `/cmdstats`\n• `/userstats <id>`\n• `/cmdusage <cmd>`\n• `/blockcmd <id> <cmd>`\n• `/unblockcmd <id> <cmd>`\n• `/blockedcmds <id>`\n• `/cmdcleanup`\n• `/clearsessions`\n• `/resetusers`\n• `/resetall`\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n✨ **ᴘᴏᴡᴇʀᴇᴅ ʙʏ ᴠɪʟʟᴀɪɴ** 😎", parse_mode='markdown')
    else:
        await event.reply(base + "━━━━━━━━━━━━━━━━━━━━━\n✨ **ᴘᴏᴡᴇʀᴇᴅ ʙʏ ᴠɪʟʟᴀɪɴ** 😎", parse_mode='markdown')

@bot.on(events.NewMessage(pattern='/status'))
async def status_h(event):
    if str(event.sender_id) in blocked_users:
        return
    u = get_user(event.sender_id)
    if u["logged_in"]:
        await event.reply(f"✅ **Logged In**\n👤 `{u.get('tg_name','N/A')}`\n🆔 `{u.get('tg_id','N/A')}`\n🕐 `{u.get('login_time','N/A')}`", parse_mode='markdown')
    else:
        await event.reply("❌ Not logged in. `/login`")

@bot.on(events.NewMessage(pattern='/login'))
async def login_h(event):
    log.info(f"🔥 /login from {event.sender_id}")
    try:
        uid = str(event.sender_id)
        if uid in blocked_users:
            await event.reply("🚫 **Aap is bot ko use nahi kar sakte.**")
            return
        u = get_user(event.sender_id)
        if u["logged_in"]:
            await event.reply(f"✅ Already logged in as `{u.get('tg_name', 'N/A')}`\n\nPehle `/logout` karo.", parse_mode='markdown')
            return
        await event.reply("📱 **Phone number bhejo** (country code ke saath)\nExample: `+919876543210`")
        u["step"] = "await_phone"
        asyncio.create_task(save_user(event.sender_id, u))
    except Exception as e:
        log.error(f"❌ /login error: {e}", exc_info=True)

@bot.on(events.NewMessage(pattern='/logout'))
async def logout_h(event):
    log.info(f"🔥 /logout from {event.sender_id}")
    try:
        uid = str(event.sender_id)
        if uid in blocked_users:
            if uid in user_bots:
                try: await user_bots[uid].disconnect()
                except Exception: pass
                del user_bots[uid]
            return
        u = get_user(uid)
        if not u["logged_in"]:
            await event.reply("❌ Aap login nahi ho. `/login`")
            return
        if uid in user_bots:
            try: await user_bots[uid].disconnect()
            except Exception: pass
            del user_bots[uid]
        u["logged_in"] = False
        u["session_string"] = None
        u["step"] = None
        await event.reply("✅ **Logged Out!**")
        asyncio.create_task(save_user(uid, u))
    except Exception as e:
        log.error(f"❌ /logout error: {e}", exc_info=True)

@bot.on(events.NewMessage(pattern='/users'))
async def users_h(event):
    if event.sender_id != OWNER_ID:
        await event.reply("❌ Sirf owner.")
        return
    if not all_users_db:
        await event.reply("📭 Koi user nahi.")
        return
    logged = sum(1 for u in users_db.values() if u.get("logged_in"))
    t = f"👥 **Total: {len(all_users_db)}**\n✅ **Logged In: {logged}**\n🚫 **Blocked: {len(blocked_users)}**\n" + "═" * 25 + "\n\n"
    for i, (uid, info) in enumerate(list(all_users_db.items())[:50], 1):
        is_logged = uid in users_db and users_db[uid].get("logged_in")
        st = "🟢" if is_logged else "🔴"
        if uid in blocked_users:
            st = "🚫"
        t += f"{i}. {st} `{info.get('name','Unknown')}`\n"
        t += f"   🆔 `{uid}`\n"
        t += f"   📛 @{info.get('username','None')}\n"
        t += f"   📅 `{info.get('first_seen','N/A')}`\n\n"
    if len(all_users_db) > 50:
        t += f"\n_...aur {len(all_users_db) - 50}_"
    await event.reply(t, parse_mode='markdown')

@bot.on(events.NewMessage(pattern='/live'))
async def live_h(event):
    if event.sender_id != OWNER_ID:
        await event.reply("❌ Sirf owner.")
        return
    if not all_users_db and not users_db:
        await event.reply("📭 Koi user nahi.")
        return

    all_ids = set(all_users_db.keys()) | set(users_db.keys())
    active, logged_off, started_only, offline = [], [], [], []

    for uid in all_ids:
        u = users_db.get(uid, {})
        info = all_users_db.get(uid, {})
        name = u.get("tg_name") or info.get("name") or "Unknown"
        tg_id = u.get("tg_id") or info.get("tg_id") or uid
        username = u.get("tg_username") or info.get("username") or "None"
        first_seen = info.get("first_seen", "N/A")

        is_logged = u.get("logged_in", False)
        is_running = uid in user_bots
        has_start = uid in all_users_db

        entry = {"name": name, "tg_id": tg_id, "username": username, "first_seen": first_seen}

        if is_running:
            active.append(entry)
        elif is_logged:
            logged_off.append(entry)
        elif has_start and not is_logged:
            started_only.append(entry)
        else:
            offline.append(entry)

    def render_list(title, items, icon):
        if not items:
            return ""
        out = f"{icon} **{title} ({len(items)})**\n\n"
        for i, info in enumerate(items, 1):
            out += f"{i}. 👤 `{info['name']}`\n"
            out += f"   🆔 `{info['tg_id']}`\n"
            out += f"   📛 @{info['username']}\n"
            out += f"   📅 `{info['first_seen']}`\n\n"
        return out + "─" * 25 + "\n\n"

    text = f"📡 **LIVE STATUS**\n" + "═" * 25 + "\n\n"
    text += render_list("ACTIVE (Userbot Running)", active, "🟢")
    text += render_list("LOGGED IN (Userbot Off)", logged_off, "🟡")
    text += render_list("STARTED ONLY (Not Logged In)", started_only, "🔵")
    te
