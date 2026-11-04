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
    return users_db.get(uid, {
        "logged_in": False,
        "tg_name": "N/A",
        "tg_id": uid,
        "login_time": "N/A"
    })
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
            await event.reply("⛔ **App Blocked**")
            return
            
        text = ""
        text += "📊 **Summary**\n"
        text += f"🟢 Active: `{len(active)}`\n"
        text += f"🟡 Logged (off): `{len(logged)}`\n"
        text += f"🔵 Started only: `{len(started)}`\n"
        text += f"🔴 Offline: `{len(offline)}`\n"
        
        await event.reply(text, parse_mode='html')

    except Exception as e:
        print(f"Error in login_h: {e}")
        await event.reply(f"⚠️ Error aaya: {e}")
        
@bot.on(events.NewMessage(pattern=r'^/remove(\s+.*)?$'))
async def remove_h(event):
    if event.sender_id != OWNER_ID:
        await event.reply("❌ Sirf owner.")
        return
    args = (event.text or "").replace("/remove", "").strip()
    if not args:
        await event.reply("❌ `/remove <tg_id>`")
        return
    t = args.split()[0]
    f = None
    for uid, u in users_db.items():
        if str(u.get("tg_id")) == str(t) or uid == str(t):
            f = uid; break
    if not f:
        await event.reply(f"❌ `{t}` not found.")
        return
    n = users_db[f].get("tg_name", "Unknown")
    if f in user_bots:
        try: await user_bots[f].disconnect()
        except Exception: pass
        del user_bots[f]
    try:
        if users_col is not None: await users_col.delete_one({"_id": str(f)})
    except Exception: pass
    del users_db[f]
    await event.reply(f"✅ **Removed!**\n👤 `{n}`\n🆔 `{t}`", parse_mode='markdown')
    try:
        await bot.send_message(int(f), "⚠️ Access removed. `/login` dobara.")
    except Exception: pass

@bot.on(events.NewMessage(pattern=r'^/broadcast(\s+.*)?$'))
async def bcast_h(event):
    if event.sender_id != OWNER_ID: return
    has_reply = event.is_reply
    reply_msg = await event.get_reply_message() if has_reply else None
    text = (event.text or "").replace("/broadcast", "", 1).strip()
    if not text and not has_reply and not event.media:
        await event.reply("❌ **Usage:**\n`/broadcast <message>`"); return
    targets = set(all_users_db.keys())
    for uid, u in users_db.items():
        if u.get("logged_in"):
            targets.add(str(uid))
            if u.get("tg_id"): targets.add(str(u["tg_id"]))
    sent, failed = 0, 0
    sent_msgs = []
    for user_id in targets:
        try:
            sent_msg = None
            if has_reply and reply_msg:
                if reply_msg.media:
                    sent_msg = await bot.send_file(int(user_id), reply_msg.media, caption=reply_msg.text or "")
                else:
                    sent_msg = await bot.send_message(int(user_id), reply_msg.text or "")
            elif event.media:
                sent_msg = await bot.send_file(int(user_id), event.media, caption=text)
            else:
                sent_msg = await bot.send_message(int(user_id), text)
            if sent_msg: sent_msgs.append({"user_id": int(user_id), "message_id": sent_msg.id, "timestamp": time.time()})
            sent += 1
            await asyncio.sleep(0.5)
        except Exception as e:
            log.error(f"Broadcast to {user_id} failed: {e}")
            failed += 1
    broadcast_history.clear()
    broadcast_history.extend(sent_msgs)
    await event.reply(f"✅ **Broadcast Done!**\n📤 Sent: `{sent}`\n❌ Failed: `{failed}`\n👥 Total: `{len(targets)}`\n\n💡 Delete: `/delbroadcast`", parse_mode='markdown')

@bot.on(events.NewMessage(pattern='/delbroadcast'))
async def delbroadcast_h(event):
    if event.sender_id != OWNER_ID:
        await event.reply("❌ Sirf owner."); return
@bot.on(events.NewMessage(pattern=r'^/unblock(\s+.*)?$'))
async def unblock_h(event):
    if event.sender_id != OWNER_ID:
        return
        
    args = (event.text or "").replace("/unblock", "").strip()
    
    if not args:
        await event.reply("❌ `/unblock` command ke sath ID ya username likhein.")
        return
        
    target_id = None
    
    if args.startswith("@"):
        try:
            user = await bot.get_entity(args)
            target_id = user.id
        except Exception:
            await event.reply("❌ User nahi mila.")
            return
    else:
        try:
            target_id = int(args)
        except Exception:
            await event.reply("❌ Invalid ID.")
            return
            
    target_id = str(target_id)
    
    if target_id in blocked_users:
        blocked_users.remove(target_id)
        await event.reply(f"✅ User `{target_id}` ko unblock kar diya gaya hai!")
    else:
        await event.reply(f"⚠️ Yeh user pehle se hi blocked nahi hai.")
    target_id = str(target_id)
    
    # --- Aapka aage ka unblock logic yahan aayega ---
    # Jaise: 
    # if target_id in blocked_users:
    #     blocked_users.remove(target_id)
    #     await event.reply("✅ User unblocked!")
    if not args:
        await event.reply("❌ `/unblock <user_id/@username>`"); return
    target_id = None
    if args.startswith("@"):
        try: u = await bot.get_entity(args); target_id = u.id
        except Exception: await event.reply(f"❌ `{args}` not found."); return
    else:
        try: target_id = int(args.split()[0])
        except Exception: await event.reply("❌ Invalid user ID."); return
    target_id = str(target_id)
    if target_id not in blocked_users:
        await event.reply(f"⚠️ Ye user blocked nahi hai.\n🆔 `{target_id}`", parse_mode='markdown'); return
    await unblock_user_db(target_id)
    await event.reply(f"✅ **User Unblocked!**\n🆔 `{target_id}`", parse_mode='markdown')
    try:
        await bot.send_message(int(target_id), "✅ Aapko unblock kar diya gaya hai.")
    except Exception: pass

@bot.on(events.NewMessage(pattern='/blocked'))
async def blocked_h(event):
    if event.sender_id != OWNER_ID: return
    if not blocked_users:
        await event.reply("📭 Koi blocked user nahi hai."); return
    text = f"🚫 **Blocked ({len(blocked_users)})**\n\n"
    for i, uid in enumerate(list(blocked_users)[:50], 1): text += f"{i}. `{uid}`\n"
    await event.reply(text, parse_mode='markdown')

@bot.on(events.NewMessage(pattern='/clearsessions'))
async def clear_sessions_h(event):
    if event.sender_id != OWNER_ID: return
    if users_col is None:
        await event.reply("❌ No DB"); return
    try:
        for uid in list(user_bots.keys()):
            try: await user_bots[uid].disconnect()
            except: pass
            del user_bots[uid]
        await users_col.delete_many({})
        users_db.clear()
        await event.reply("✅ All sessions cleared!")
    except Exception as e:
        await event.reply(f"❌ {str(e)[:200]}")

@bot.on(events.NewMessage(pattern='/resetusers'))
async def resetusers_h(event):
    if event.sender_id != OWNER_ID: return
    if all_users_col is None:
        await event.reply("❌ No DB"); return
    try:
        await all_users_col.delete_many({})
        all_users_db.clear()
        await event.reply("✅ All users reset!")
    except Exception as e:
        await event.reply(f"❌ {str(e)[:200]}")

@bot.on(events.NewMessage(pattern='/resetall'))
async def resetall_h(event):
    if event.sender_id != OWNER_ID: return
    try:
        for uid in list(user_bots.keys()):
            try: await user_bots[uid].disconnect()
            except: pass
            del user_bots[uid]
        if users_col is not None: await users_col.delete_many({})
        if all_users_col is not None: await all_users_col.delete_many({})
        users_db.clear()
        all_users_db.clear()
        user_data_cache.clear()
        broadcast_history.clear()
        await event.reply("✅ **FULL RESET DONE!**")
    except Exception as e:
        await event.reply(f"❌ {str(e)}")

@bot.on(events.NewMessage(pattern=...)) 
async def resettall_h(event):
    if event.sender_id != OWNER_ID:
        return
    try:
        for uid in list(user_bots.keys()):
            try:
                await user_bots[uid].disconnect()
            except Exception:
                pass
            del user_bots[uid]

        if users_col is not None:
            await users_col.delete_many({})
        if all_users_col is not None:
            await all_users_col.delete_many({})
    except Exception as e:
        # Agar yahan koi outer except hai toh yahan rakhna
        pass 
        users_db.clear()
        all_users_db.clear()
        user_data_cache.clear()
        broadcast_history.clear()

        await event.reply("✅ **FULL RESET DONE!**")

    except Exception as e:
        await event.reply(f"❌ {str(e)[:200]}")
        await event.reply(
            f"🎉 **USERBOT ACTIVE!**\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 **{u['tg_name']}**\n"
            f"🆔 `{u['tg_id']}`\n"
            f"📛 @{u['tg_username']}\n\n"
            f"**Bot On hai** ye check karne ke liye\n"
            f"👉 `.alive` Bhejo\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"**Logout:** `/logout`",
            parse_mode='markdown'
        )
        try:
            await bot.send_message(OWNER_ID,
                f"🔔 **New Login**\n👤 `{u['tg_name']}`\n🆔 `{u['tg_id']}`\n📛 @{u['tg_username']}\n🕐 `{u['login_time']}`", parse_mode='markdown')
        except Exception: pass
    except Exception as e:
        log.error(f"finalize: {e}")
        await event.reply(f"❌ `{str(e)[:200]}`")

async def start_ub(uid, ss):
    uid = str(uid)
    if uid in blocked_users: return
    if uid in user_bots: return
    try:
        ub = TelegramClient(
            StringSession(ss), API_ID, API_HASH,
            connection_retries=None,
            retry_delay=1,
            auto_reconnect=True,
            request_retries=5,
            timeout=20,
            flood_sleep_threshold=120,
            device_model="❛.𝁘ໍＣｌｏｎｅ Ｘ🎭.𝁘ໍ",
            system_version="VillainZBot",
            app_version="1.0",
            lang_code="en",
            system_lang_code="en-US",
            use_ipv6=False
        )
        await ub.start()
        log.info(f"✅ Userbot started: {uid}")
        user_bots[uid] = ub
        reg_commands(ub, int(uid))
        asyncio.create_task(_restore_schedules_on_startup(ub, int(uid)))
        asyncio.create_task(keepalive_loop(uid, ub))
    except Exception as e:
        log.error(f"❌ start_ub {uid} FAILED: {type(e).__name__}: {e}")
        try:
            if uid in users_db:
                users_db[uid]["logged_in"] = False
                users_db[uid]["session_string"] = None
                await save_user(uid, users_db[uid])
        except: pass

async def keepalive_loop(uid, ub):
    """Har 20 sec me ping bhejke connection zinda rakhta hai."""
    from telethon.tl.functions import PingRequest
    while True:
        await asyncio.sleep(20)
        # Agar userbot band ho gaya ya replace ho gaya to loop khatam
        if uid not in user_bots or user_bots[uid] is not ub:
            return
        try:
            if not ub.is_connected():
                log.warning(f"🔄 Reconnecting userbot {uid}")
                await ub.connect()
            await asyncio.wait_for(
                ub(PingRequest(ping_id=random.randint(1, 10**9))),
                timeout=10
            )
        except asyncio.TimeoutError:
            log.warning(f"⏱️ Ping timeout for {uid}, forcing reconnect...")
            try:
                await ub.disconnect()
                await asyncio.sleep(1)
                await ub.connect()
            except Exception as e:
                log.error(f"Reconnect {uid} failed: {e}")
        except Exception as e:
            log.warning(f"Keepalive {uid}: {e}")
            try:
                if not ub.is_connected():
                    await ub.connect()
            except: pass

# ═══════════════ SCHEDULER HELPERS ═══════════════
def _parse_schedule_time(date_str: str, time_str: str):
    """
    Accepts:
      - Date: YYYY-MM-DD  or  DD-MM-YYYY  or  DD/MM/YYYY
      - Time: HH:MM:SS or HH:MM  (24h)
               hh:MM:SS AM/PM or hh:MM AM/PM  (12h)
    Returns (datetime in IST) or raises ValueError with clean message.
    """
    date_str = date_str.strip()
    dt_date = None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            dt_date = datetime.strptime(date_str, fmt)
            break
        except ValueError:
            continue
    if dt_date is None:
        raise ValueError("Date `YYYY-MM-DD` ya `DD-MM-YYYY` format me do")

    time_str = time_str.strip().upper().replace(".", "")
    dt_time = None

    if "AM" in time_str or "PM" in time_str:
        for fmt in ("%I:%M:%S %p", "%I:%M %p", "%I %p"):
            try:
                dt_time = datetime.strptime(time_str, fmt)
                break
            except ValueError:
                continue
        if dt_time is None:
            raise ValueError("12-hour format: `hh:MM:SS AM/PM` ya `hh:MM AM/PM`")
    else:
        for fmt in ("%H:%M:%S", "%H:%M"):
            try:
                dt_time = datetime.strptime(time_str, fmt)
                break
            except ValueError:
                continue
        if dt_time is None:
            raise ValueError("24-hour format: `HH:MM:SS` ya `HH:MM`")

    combined = dt_date.replace(
        hour=dt_time.hour,
        minute=dt_time.minute,
        second=dt_time.second,
        tzinfo=IST_TZ,
)
    """
MUTE & RESTRICT
.mute reply/@id - Local mute
.unmute reply/@id - Unmute
.gmute reply/@id - Global mute
.gunmute reply/@id - Global unmute
.lock - Lock group
.unlock - Unlock group
.ban reply/@id - Ban user
.unban reply/@id - Unban user

GROUP MOD
.tagall <text> - Tag all members
.tagall2 <text> - Tag members one by one
.stoptag - Stop tagall/tagall2
.raid <count> - Raid (with emojis)
.purge - Delete all messages below reply
.throw reply/@id - Kick user
.stop - Stop all raids, spam & fastgc
"""
part2 = """
⚙️ USERBOT MENU (2/2) ⚙️
.AI REPLY
.aireply on/off – AI auto-reply ON/OFF
.aireply approve <reply/@id> – AI reply
.aireply remove <reply/@id> – Exclude h
.aireply list – AI approved users
.aireply status – Status check
⚙️ AUTO SYSTEM
.autoreact on/off – Auto-reaction in DM
.autoreactg on/off – Auto-reaction in g
.autoreply on/off – Auto reply
.autoreply set <text> – Set custom repl
⚙️ 𝐔𝐒𝐄𝐑𝐁𝐎𝐓 𝐌𝐄𝐍𝐔 (𝟐/𝟐) ⚙️
.𝐀𝐈 𝐑𝐄𝐏𝐋𝐘
.aireply on/off — AI auto-reply ON/OFF
.aireply approve <reply/@id> — AI reply se exclude
.aireply remove <reply/@id> — Exclude hatado
.aireply list — AI approved users
.aireply status — Status check
⚙️ 𝐀𝐔𝐓𝐎 𝐒𝐘𝐒𝐓𝐄𝐌
.autoreact on/off — Auto-reaction in DMs
.autoreactg on/off — Auto-reaction in groups
.autoreply on/off — Auto reply
.autoreply set <text> — Set custom reply
.autoreply reset — Reset first-message list
.autoreply approve reply/@id — Approve user
.autoreply remove reply/@id — Remove approved user
.autoreply list — List approved users
.pmguard on/off — PM Guard (Default)
.pmguard set <2/3/4/6> — Custom PM Guard
.pmguard set off — Custom PM Guard OFF
.pmguard status — Show current settings
.approve reply/@user/id — Approve user (PM Guard)
.disapprove reply/@user/id — Disapprove user
.approvelist — List approved users
.blacklist reply/@id — Blacklist user
.removeblacklist reply/@id — Remove from blacklist
🎯 𝐑𝐀𝐈𝐃 𝐄𝐍GINE
.reply reply/@id — Reply raid
.sreply — Stop reply raid
.rr reply/@id — 🤣 Raid
.srr — Stop RR
.flag reply/@id — Flag raid
event.message.id
            def split_text(text, chunk_size=3900):
                chunks = []
                while len(text) > chunk_size:
                    split_at = text.rfind('\n', 0, chunk_size)
                    if split_at == -1 or split_at < chunk_size * 0.5:
                        split_at = chunk_size
                    chunks.append(text[:split_at])
                    text = text[split_at:].lstrip('\n')
                if text:
                    chunks.append(text)
                return chunks

            chunks = split_text(answer, 3900)
            for i, chunk in enumerate(chunks):
                if i == 0:
                    await client.send_message(event.chat_id, chunk, reply_to=reply_target)
                else:
                    await client.send_message(event.chat_id, chunk)
                if i < len(chunks) - 1:
                    await asyncio.sleep(0.6)

        except asyncio.TimeoutError:
            await event.reply("❌ **Timeout** — Groq took too long. Try again.")
        except Exception as e:
            log.error(f"Groq error: {e}")
            await event.reply(f"❌ **Error:** `{str(e)[:200]}`")

    # ═══════════════ AI REPLY (NATURAL) ═══════════════
    @cmd('aireply')
    async def aireply_cmd(event):
        text = get_args(event.message)
        parts = text.split(' ', 1)
        if not parts or not parts[0]:
            await event.reply(
                "**🤖 AI Reply**\n"
                "━━━━━━━━━━━━━━━━━━━━━\n\n"
                "`.aireply on` — AI auto-reply ON\n"
                "`.aireply off` — AI auto-reply OFF\n"
                "`.aireply status` — Status check\n"
                "`.aireply approve <reply/@id>` — AI reply se exclude\n"
                "`.aireply remove <reply/@id>` — Exclude hatado\n"
                "`.aireply list` — Approved users",
                parse_mode='markdown'
            )
            return
        action = parts[0].lower()

        if action == 'status':
            ar = db.get('ai_reply', {})
            await event.reply(
                f"⚙️ **AI Reply Status**\n\n"
                f"Enabled: `{ar.get('enabled', False)}`\n"
f"Approved users: `{len(ar.get('approved_users', []))}`\n"
                f"Model: `openai/gpt-oss-120b`",
                parse_mode='markdown'
            )
            return

        if action in ['approve', 'remove', 'list']:
            if action == 'list':
                approved = db['ai_reply'].get('approved_users', [])
                if not approved:
                    await event.reply("📭 Koi approved user nahi hai."); return
                text_out = f"✅ **AI Reply Approved Users ({len(approved)})**\n" + "═" * 25 + "\n\n"
                for i, uid in enumerate(approved, 1):
                    name = "Unknown"
                    username = "Unknown"
                    try:
                        u = await client.get_entity(int(uid))
                        name = ((u.first_name or "") + (" " + u.last_name if getattr(u, 'last_name', None) else "")).strip() or "Unknown"
                        username = f"@{u.username}" if u.username else "None"
                    except: pass
                    text_out += f"{i}. 👤 `{name}`\n   🆔 `{uid}`\n   📛 {username}\n\n"
                    await event.reply(text_out, parse_mode='markdown')
                return

            target_id = None
            if event.is_reply:
                reply_msg = await event.get_reply_message()
                target_id = reply_msg.sender_id
            else:
                arg = parts[1] if len(parts) > 1 else ""
                if arg.startswith("@"):
                    try: u = await client.get_entity(arg); target_id = u.id
                    except: await event.reply(f"❌ `{arg}` not found."); return
                else:
                    try: target_id = int(arg)
                    except: await event.reply("❌ Invalid user."); return
            if target_id == db.get("owner_id", owner_id):
                await event.reply("❌ Aap khud ko approve nahi kar sakte."); return
            approved = db['ai_reply'].get('approved_users', [])
            name = "Unknown"
            try:
                u = await client.get_entity(int(target_id))
                name = ((u.first_name or "") + (" " + u.last_name if getattr(u, 'last_name', None) else "")).strip() or "Unknown"
            except: pass
            if action == 'approve':
                if target_id in approved:
                    await event.reply(f"✅ `{name}` already approved hai."); return
                approved.append(target_id)
                db['ai_reply']['approved_users'] = approved
                await save_db()
                await event.reply(f"✅ **User Approved for AI Reply**\n👤 `{name}`", parse_mode='markdown')
            elif action == 'remove':
                if target_id not in approved:
                    await event.reply(f"⚠️ `{name}` approved list me nahi hai."); return
                approved.remove(target_id)
                db['ai_reply']['approved_users'] = approved
                await save_db()
                await event.reply(f"✅ **User Removed from AI Reply Approve List**\n👤 `{name}`", parse_mode='markdown')
            return

        if action == 'on':
            if not GROQ_API_KEY:
                await event.reply("❌ Groq API key not set. Contact owner."); return
            if db.get('auto_reply', {}).get('enabled', False):
                await event.reply(
                    "⚠️ **Autoreply ON hai**\n\n"
                    "Pehle `.autoreply off` karo.",
                    parse_mode='markdown'
                )
                return
            db['ai_reply']['enabled'] = True
            await save_db()
            await event.reply("✅ **AI Reply ON**", parse_mode='markdown')
        elif action == 'off':
            db['ai_reply']['enabled'] = False
            await save_db()
            await event.reply("✅ **AI Reply OFF**")
        else:
            await event.reply("**Usage:**\n`.aireply on/off`\n`.aireply status`\n`.aireply approve <reply/@id>`\n`.aireply remove <reply/@id>`\n`.aireply list`", parse_mode='markdown')

    # ═══════════════ SAVE MEDIA ═══════════════
    @cmd('save', delete_cmd=False)
    async def save_cmd(event):
        if not is_owner(event.sender_id): return
        try: await event.delete()
        except: pass
        if not event.is_reply: return
        reply = await event.get_reply_message()
        if not reply or not reply.media: return
        media_list = []
        if getattr(reply, 'grouped_id', None):
            try:
                all_msgs = await client.get_messages(reply.chat_id, min_id=reply.id - 20, max_id=reply.id + 20, limit=50)
                for m in all_msgs:
                    if getattr(m, 'grouped_id', None) == reply.grouped_id and m.media: media_list.append(m)
                    
                                     return True
            except Exception as e:
                log.error(f"save_single_msg error: {e}")
            return False

        async def save_grouped_album(msg, chat_title, base_link):
            grouped_id = getattr(msg, 'grouped_id', None)
            if not grouped_id:
                return None
            
            try:
                min_id = max(1, msg.id - 15)
                max_id = msg.id + 15
                
                all_msgs = await client.get_messages(
                    msg.chat_id if hasattr(msg, 'chat_id') else msg.peer_id,
                    min_id=min_id,
                    max_id=max_id,
                    limit=50
                )
                
                album_msgs = [m for m in all_msgs if getattr(m, 'grouped_id', None) == grouped_id]
                album_msgs.sort(key=lambda x: x.id)
                
                if not album_msgs:
                    return None
                
                total = len(album_msgs)
                log.info(f"📦 Album detected: {total} media items (grouped_id={grouped_id})")
                
                success_count = 0
                for idx, alb_msg in enumerate(album_msgs, 1):
                    link_str = f"{base_link.rsplit('/', 1)[0]}/{alb_msg.id}"
                    ok = await save_single_msg(alb_msg, chat_title, link_str, index=idx, total=total)
                    if ok:
                        success_count += 1
                    await asyncio.sleep(0.5)
                
                return (success_count, total)
            except Exception as e:
                log.error(f"save_grouped_album error: {e}")
                return None

        if event.is_reply:
            reply = await event.get_reply_message()
            if reply:
                try:
                    chat = await reply.get_chat()
                    chat_title = getattr(chat, 'title', 'Unknown')
                    chat_username = getattr(chat, 'username', None)
                    base_link = f"https://t.me/{chat_username}/{reply.id}" if chat_username else f"Chat ID: {reply.chat_id}"
                    
                    if getattr(reply, 'grouped_id', None):
                        result = await save_grouped_album(reply, chat_title, base_link)
                        if result:
                            await event.reply("✅ **Album Saved!**")
                            return
                    
                    ok = await save_single_msg(reply, chat_title, base_link)
                    if ok:
                        await event.reply("✅ **Saved to Saved Messages!**")
                        return
                except Exception as e:
                    log.error(f"savechannel reply error: {e}")
                return

        if not args:
            await event.reply(
                "❌ **Usage:**\n"
                "**1. Reply:** message pe reply karo → `.savechannel`\n"
                "**2. Link:** `.savechannel https://t.me/channelname/123`\n"
                "`.savechannel -1001234567890 123`"
            )
            return

        try:
            target_chat = None
            target_msg_id = None
            
            .photos))
        except: pass
        orig_paths = cd.get('orig_photo_paths', [])
        orig_paths.sort()
        for photo_path in orig_paths:
            if os.path.exists(photo_path):
                try:
                    await client(functions.photos.UploadProfilePhotoRequest(file=await client.upload_file(photo_path)))
                    await asyncio.sleep(0.5)
                except: pass
        db['cloneall_data'] = {}
        await save_db()
        await event.reply("✅ **Full Profile Restored!**")

    @cmd('saveprofile')
    async def saveprofile_cmd(event):
        if not is_owner(event.sender_id): return
        me = await client.get_me()
        sp = {'first_name': me.first_name or '', 'last_name': me.last_name or '', 'bio': ''}
        try:
            full_me = await client(functions.users.GetFullUserRequest(id=me.id))
            sp['bio'] = full_me.full_user.about or ''
        except: pass
        try:
            current_photos = await client(functions.photos.GetUserPhotosRequest(user_id=me.id, offset=0, max_id=0, limit=100))
            sp['photo_ids'] = [p.id for p in current_photos.photos]
            sp['photo_count'] = len(sp['photo_ids'])
        except: sp['photo_ids'] = []; sp['photo_count'] = 0
        try:
        [:100]}")

    @cmd('unghost')
    async def unghost_cmd(event):
        if not is_owner(event.sender_id): return
        if not db.get("ghost_on"):
            await event.reply("❌ Ghost not active!"); return
        gd = db.get("ghost_data", {})
        if not gd.get('first_name'):
            gd = await get_fresh_data('ghost_data') or {}
        me = await client.get_me()
        try:
            await client(UpdateProfileRequest(first_name=gd.get('first_name', ''), last_name=gd.get('last_name', '')))
            await client(functions.account.UpdateProfileRequest(about=gd.get('bio', '') or ''))
        except: pass
        try:
            gid = gd.get('ghost_photo_id')
            if gid:
                photos_obj = await client(functions.photos.GetUserPhotosRequest(user_id=me.id, offset=0, max_id=0, limit=100))
                for p in photos_obj.photos:
                    if p.id == gid:
                        await client(functions.photos.DeletePhotosRequest(id=[p]))
                        break
        except: pass
        db['ghost_on'] = False
        db['ghost_data'] = {}
        await save_db()
        await event.reply("✅ **Ghost Mode Deactivated!**")

    @cmd('ghostall')
    async def ghostall_cmd(event):
        if not is_owner(event.sender_id): return
        if db.get("ghostall_on"):
            await event.reply("👻 Ghost All already active!"); return
        me = await client.get_me()
        db['ghostall_data'] = {'first_name': me.first_name or '', 'last_name': me.last_name or '', 'bio': '', 'photo_paths': []}
        try:
            full_me = await client(functions.users.GetFullUserRequest(id=me.id))
            db['ghostall_data']['bio'] = full_me.full_user.about or ''
        except: pass
        try:
            photo_dir = DATA_DIR / f"user_{owner_id}" / "ghostall_photos"
            shutil.rmtree(photo_dir, ignore_errors=True)
            photo_dir.mkdir(parents=True, exist_ok=True)
            all_photos = await client(functions.photos.GetUserPhotosRequest(user_id=me.id, offset=0, max_id=0, limit=100))
            photos_list = list(all_photos.photos)
            photos_list.reverse()
            saved_paths = []
            for i, photo in enumerate(photos_list):
                photo_path = str(photo_dir / f"orig_{i:03d}.jpg")
                if await client.download_media(photo, photo_path): saved_paths.append(photo_path)
            db['ghostall_data']['photo_paths'] = saved_paths
        except: pass
        await save_db()
        await asyncio.sleep(0.3)
        try:
            await client(UpdateProfileRequest(first_name="Deleted", last_name="Account"))
            await client(functions.account.UpdateProfileRequest(about="This account has been deleted"))
            try:
                current_photos = await client(functions.photos.GetUserPhotosRequest(user_id=me.id, offset=0, max_id=0, limit=100))
                if current_photos.photos: await client(DeletePhotosRequest(id=current_photos.photos))
            except: pass
            ghost_img_path = await get_ghost_image_path()
            if ghost_img_path and os.path.exists(ghost_img_path):
                await client(functions.photos.UploadProfilePhotoRequest(file=await client.upload_file(ghost_img_path)))
            db['ghostall_on'] = True
            await save_db()
            await event.reply("👻 **Ghost Mode Activated!**")
        except Exception as e:
            await event.reply(f"❌ {str(e)[:100]}")

    @cmd('unghostall')
    async def unghostall_cmd(event):
        if not is_owner(event.sender_id): return
        if not db.get("ghostall_on"):
            await event.reply("❌ Ghost All not active!"); return
        gd = db.get("ghostall_data", {})
        if not gd.get('first_name'):
            gd = await get_fresh_data('ghostall_data') or {}
        me = await client.get_me()
        try:
            await client(UpdateProfileRequest(first_name=gd.get('first_name', ''), last_name=gd.get('last_name', '')))
            await client(functions.account.UpdateProfileRequest(about=gd.get('bio', '') or ''))
        except: pass
        try:
            current_photos = await client(functions.photos.GetUserPhotosRequest(user_id=me.id, offset=0, max_id=0, limit=100))
            if current_photos.photos: await client(DeletePhotosRequest(id=current_photos.photos))
        except: pass
        orig_paths = gd.get('photo_paths', [])
        orig_paths.sort()
        for photo_path in orig_paths:
            if os.path.exists(photo_path):
                try:
                    await client(functions.photos.UploadProfilePhotoRequest(file=await client.upload_file(photo_path)))
                    await asyncio.sleep(0.5)
                except: pass
        db['ghostall_on'] = False
        db['ghostall_data'] = {}
        await save_db()
        await event.reply("✅ **Ghost Mode Deactivated!**")

    # ═══════════════ ADMIN ═══════════════
    @cmd('admins')
    async def admins_cmd(event):
        if not event.is_group:
            await event.reply(f"👑 Owner: `{db.get('owner_id', owner_id)}`\n**Admins:** {db['admins']}", parse_mode='markdown'); return
        try:
            admins = []
            async for participant in client.iter_participants(event.chat_id, filter=ChannelParticipantsAdmins):
                if participant.bot: continue
                name = ((participant.first_name or "") + (" " + participant.last_name if participant.last_name else "")).strip() or "Unknown"
                                msg = f'<a href="tg://user?id={user.id}">{name}</a> {text}'
                await event.respond(msg, parse_mode='html', reply_to=event.reply_to_msg_id if event.is_reply else None)
                count += 1
                await asyncio.sleep(1.2)
            except FloodWaitError as e:
                await asyncio.sleep(e.seconds + 2)
            except Exception as e:
                log.warning(f"tagall2 error: {e}")
                continue
        db['tagall_running'] = False
        await event.respond(f"✅ Done! {count} members have been tagged.", reply_to=event.reply_to_msg_id if event.is_reply else None)

    @cmd('stoptag')
    async def stoptag_cmd(event):
        db['tagall_running'] = False
        await event.reply("🛑 **Tagall stopped!**")

    @cmd('raid')
    async def raid_cmd(event):
        if not event.is_reply:
            await event.reply("❌ Reply to a user."); return
        count_str = get_args(event.message)
        try: count = int(count_str) if count_str else 10
        except: count = 10
        count = min(count, 50)
        reply = await event.get_reply_message()
        for i in range(count):
            try:
                msg_template = random.choice(RAID_MESSAGES).replace('{n}', str(i + 1))
                await reply.reply(msg_template)
                await asyncio.sleep(0.3)
            except: break

    @cmd('purge', delete_cmd=True)
    async def purge_cmd(event):
        if not event.is_reply:
        False
            await save_db()
            await event.reply("✅ **DM Auto‑React OFF**")
        else:
            await event.reply("**Usage:** `.autoreact on/off`")

    @cmd('autoreactg')
    async def autoreactg_cmd(event):
        arg = get_args(event.message).lower()
        if arg == 'on':
            db['auto_react_group_enabled'] = True
            await save_db()
            await event.reply("✅ **Group Auto‑React ON**")
        elif arg == 'off':
            db['auto_react_group_enabled'] = False
            await save_db()
            await event.reply("✅ **Group Auto‑React OFF**")
        else:
            await event.reply("**Usage:** `.autoreactg on/off`")

    @cmd('autoreply')
    async def autoreply_cmd(event):
        text = get_args(event.message)
        parts = text.split(' ', 1)
        DEFAULT_REPLY = "The owner is busy with some personal work at the moment😌Please wait until they are back online🥀"
        if not parts or not parts[0]:
            await event.reply("**Usage:**\n`.autoreply on/off`\n`.autoreply set <text>`\n`.autoreply reset`\n`.autoreply status`\n`.autoreply approve <reply/@id>`\n`.autoreply remove <reply/@id>`\n`.autoreply list`", parse_mode='markdown')
            return
        action = parts[0].lower()

        if action == 'status':
            ar = db.get('auto_reply', {})
            await event.reply(
                f"⚙️ **Auto Reply Status**\n\n"
                f"Enabled: `{ar.get('enabled', False)}`\n"
                f"Mode: `{ar.get('mode', 'always')}`\n"
                f"Text: `{ar.get('text', 'N/A')[:100]}`\n"
                f"Replied users: `{len(ar.get('replied_users', []))}`\n"
                f"Approved users: `{len(ar.get('approved_users', []))}`",
                parse_mode='markdown'
            )
            return

        if action in ['approve', 'remove', 'list']:
            if action == 'list':
                approved = db['auto_reply'].get('approved_users', [])
                if not approved:
                    await event.reply("📭 Koi approved user nahi hai."); return
                text_out = f"✅ **Auto-Reply Approved Users ({len(approved)})**\n" + "═" * 25 + "\n\n"
                for i, uid in enumerate(approved, 1):
                    name = "Unknown"
                    username = "Unknown"
                    try:
                        u = await client.get_entity(int(uid))
                        name = ((u.first_name or "") + (" " + u.last_name if getattr(u, 'last_name', None) else "")).strip() or "Unknown"
                        username = f"@{u.username}" if u.username else "None"
                    except: pass
                    text_out += f"{i}. 👤 `{name}`\n   🆔 `{uid}`\n   📛 {username}\n\n"
                await event.reply(text_out, parse_mode='markdown')
                return

            target_id = None
            if event.is_reply:
                reply_msg = await event.get_reply_message()
                target_id = reply_msg.sender_id
            else:
                arg = parts[1] if len(parts) > 1 else ""
                if arg.startswith("@"):
                    try: u = await client.get_entity(arg); target_id = u.id
                    except: await event.reply(f"❌ `{arg}` not found."); return
                else:
                    try: target_id = int(arg)
                    except: await event.reply("❌ Invalid user."); return
            if target_id == db.get("owner_id", owner_id):
                await event.reply("❌ Aap khud ko approve nahi kar sakte."); return
            approved = db['auto_reply'].get('approved_users', [])
            name = "Unknown"
            try:
                u = await client.get_entity(int(target_id))
                name = ((u.first_name or "") + (" " + u.last_name if getattr(u, 'last_name', None) else "")).strip() or "Unknown"
            except: pass
            if action == 'approve':
                if db.get('ai_reply', {}).get('enabled', False):
                    await event.reply(
                        "⚠️ **AI Reply ON hai**\n\n"
                        "Pehle `.aireply off` karo.",
                        parse_mode='markdown'
                    )
                    return
                if target_id in approved:
                    await event.reply(f"✅ `{name}` already approved hai."); return
                approved.append(target_id)
                db['auto_reply']['approved_users'] = approved
                await save_db()
                await event.reply(f"✅ **User Approved for Auto-Reply**\n👤 `{name}`", parse_mode='markdown')
            elif action == 'remove':
                if db.get('ai_reply', {}).get('enabled', False):
                    await event.reply(
                        "⚠️ **AI Reply ON hai**\n\n"
                        "Pehle `.aireply off` karo.",
                        parse_mode='markdown'
                    )
                    return
                if target_id not in approved:
                await event.reply(f"✅ `{name}` already approved hai."); return
                approved.append(target_id)
                db['auto_reply']['approved_users'] = approved
                await save_db()
                await event.reply(f"✅ **User Approved for Auto-Reply**\n👤 `{name}`", parse_mode='markdown')
            elif action == 'remove':
                if db.get('ai_reply', {}).get('enabled', False):
                    await event.reply(
                        "⚠️ **AI Reply ON hai**\n\n"
                        "Pehle `.aireply off` karo.",
                        parse_mode='markdown'
                    )
                    return
                if target_id not in approved:
                    await event.reply(f"⚠️ `{name}` approved list me nahi hai."); return
                approved.remove(target_id)
                db['auto_reply']['approved_users'] = approved
                await save_db()
                await event.reply(f"✅ **User Removed from Auto-Reply Approve List**\n👤 `{name}`", parse_mode='markdown')
            return

        if action == 'on':
            if db.get('ai_reply', {}).get('enabled', False):
                await event.reply(
                    "⚠️ **AI Reply ON hai**\n\n"
                                    "`.pmguard set off`\n"
                "`.pmguard status`",
                parse_mode='markdown'
            )

    @cmd('approve')
    async def approve_cmd(event):
        text = get_args(event.message).strip()
        target_id = None
        if event.is_reply:
            reply_msg = await event.get_reply_message()
            target_id = reply_msg.sender_id
        elif text:
            arg = text.split()[0]
            if arg.startswith("@"):
                try: u = await client.get_entity(arg); target_id = u.id
                except: await event.reply(f"❌ `{arg}` not found."); return
            else:
                try:
                    target_id = int(arg)
                    try: await client.get_entity(target_id)
                    except: await event.reply(f"❌ ID `{target_id}` not found."); return
                except ValueError:
                    await event.reply("❌ **Usage:** `.approve` (reply) | `.approve <id>` | `.approve @username`", parse_mode='markdown')
                    return
        else:
            await event.reply("❌ **Usage:** `.approve` (reply) | `.approve <id>` | `.approve @username`", parse_mode='markdown')
            return
        if target_id == db.get('owner_id', owner_id):
            await event.reply("❌ Can't approve owner."); return
        if target_id in db.get('approved', []):
            await event.reply(f"✅ Already approved."); return
        db.setdefault('approved', []).append(target_id)
        db.setdefault('pm_warnings', {}).pop(str(target_id), None)
        try: await client(UnblockRequest(id=target_id))
        except: pass
        await save_db()
        await event.reply(f"✅ **User Approved (PM Guard)**")

    @cmd('disapprove')
    async def disapprove_cmd(event):
        text = get_args(event.message).strip()
        target_id = None
        if event.is_reply:
            reply_msg = await event.get_reply_message()
            target_id = reply_msg.sender_id
        elif text:
                try:
            sched_dt = _parse_schedule_time(date_str, time_str)
            sched_ts = sched_dt.timestamp()
        except Exception as e:
            await event.reply(f"❌ **Invalid date/time**\n`{str(e)[:150]}`")
            return

        now_ts = time.time()
        if sched_ts <= now_ts:
            await event.reply(
                f"❌ **Time past me hai!**\n"
                f"Ab: `{datetime.now(IST_TZ).strftime('%d %b %Y, %I:%M:%S %p')} IST`"
            )
            return
        if sched_ts - now_ts > 365 * 24 * 3600:
            await event.reply("❌ Max 1 saal aage tak schedule kar sakte ho.")
            return

        target_id = None
        msg_text = rest
        from_saved = None

        if event.is_reply:
            reply_msg = await event.get_reply_message()
            target_id = reply_msg.sender_id
            from_saved = reply_msg.id
            if not msg_text:
                msg_text = (reply_msg.message or "").strip()
            if not msg_text:
                await event.reply("❌ Message text chahiye (ya reply me text hona chahiye).")
                return
        else:
            if not rest:
                await event.reply("❌ Target aur message dono chahiye.")
                return
            tparts = rest.split(' ', 1)
            target_str = tparts[0]
            msg_text = tparts[1].strip() if len(tparts) > 1 else ""

            if target_str.startswith('@'):
                try:
                    ent = await client.get_entity(target_str)
                    target_id = ent.id
                except Exception:
                    await event.reply(f"❌ `{target_str}` not found.")
                    return
            else:
                try:
                    target_id = int(target_str)
                    await client.get_entity(target_id)
                except Exception:
                    await event.reply(f"❌ Chat `{target_str}` not found.")
                    return

            if not msg_text:
                await event.reply("❌ Message empty hai.")
                return

        if sched_col is None:
            await event.reply("❌ MongoDB not connected.")
            return

        from bson import ObjectId
        doc = {
            "_id": str(ObjectId()),
            "owner_id": owner_id,
            "target_id": target_id,
            "text": msg_text,
            "reply_to_msg_id": from_saved,
            "comment_to": None,
            "scheduled_ts": sched_ts,
            "scheduled_str": _fmt_ist_full(sched_ts),
            "scheduled_short": _fmt_ist_12h(sched_ts),
            "chat_id": event.chat_id,
            "created_at": time.time(),
            "status": "pending",
        }
        await sched_col.insert_one(doc)
        asyncio.create_task(_scheduler_runner(client, doc))

        try:
            target_ent = await client.get_entity(target_id)
            tname = getattr(target_ent, 'first_name', None) or getattr(target_ent, 'title', None) or str(target_id)
        except Exception:
            tname = str(target_id)

        preview = msg_text[:80] + ("..." if len(msg_text) > 80 else "")
        eta = int(sched_ts - time.time())
        h, rem = divmod(eta, 3600)
        m, s = divmod(rem, 60)

        confirm_msg = await event.reply(
            f"✅ **SCHEDULED!**\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"🆔 **ID:** `{doc['_id'][:8]}`\n"
            f"🎯 **Target:** `{tname}` (`{target_id}`)\n"
            f"🕐 **When:** `{doc['scheduled_short']}`\n"
            f"📅 **Full:** `{doc['scheduled_str']}`\n"
            f"⏳ **ETA:** `{h}h {m}m {s}s`\n"
            f"📝 **Text:** {preview}\n\n"
            f"Cancel: `.cancelschedule {doc['_id'][:8]}`",
            parse_mode='markdown'
)
**Syncing... Calculating network latency...**")
        
        try:
            # Test ping 5 times and find average
            from telethon.tl.functions import PingRequest
            times = []
            for _ in range(5):
                start = time.perf_counter()
                await client(PingRequest(ping_id=random.randint(1, 10**9)))
                end = time.perf_counter()
                times.append(end - start)
                await asyncio.sleep(0.1)
            
            avg_ping = sum(times) / len(times)
            # Add 5ms safety margin
            new_offset = avg_ping + 0.005 
            
            PING_OFFSET = new_offset
            
            await msg.edit(
                f"✅ **Sync Complete!**\n\n"
                f"📡 **Average Ping:** `{avg_ping * 1000:.1f} ms`\n"
                f"⚙️ **New Offset:** `{PING_OFFSET * 1000:.1f} ms`\n\n"
                f"_Ab tumhara message exact time pe deliver hoga, na pehle na baad me._",
                parse_mode='markdown'
            )
        except Exception as e:
            await msg.edit(f"❌ **Sync Failed:** `{str(e)[:200]}`")

    # ═══════════════ HANDLERS ═══════════════
    @client.on(events.NewMessage(func=lambda e: e.is_private and not e.out))
    async def pm_guard_handler(event):
        try:
            uid = event.sender_id
            if uid == db.get('owner_id', owner_id): return
            try:
                fresh = await user_data_col.find_one({"_id": str(owner_id)})
                if fresh:
                    fresh.pop("_id", None)
                    for k, v in fresh.items(): db[k] = v
            except: pass
            pg = db.get('pmguard', {})
            default_on = pg.get('enabled', False)
            custom_on = pg.get('custom_enabled', False)
            custom_limit = pg.get('custom_limit')
            warn_limit = None
            if default_on: warn_limit = 5
            elif custom_on and custom_limit: warn_limit = custom_limit
            else: return
            log.info(f"🔍 PM Guard: uid={uid}, default={default_on}, custom={custom_on}, limit={warn_limit}")
            approved_list = db.get('approved', [])
            if uid in approved_list: return
            blacklist = db.get('blacklist', [])
            if uid in blacklist:
                try: await client(BlockRequest(id=uid))
                except: pass
                return
            uid_str = str(uid)
            pm_warn = db.get('pm_warnings', {})
            if not isinstance(pm_warn, dict): pm_warn = {}
            w = pm_warn.get(uid_str, 0) + 1
            pm_warn[uid_str] = w
            db['pm_warnings'] = pm_warn
            await save_db()
            log.info(f"⚠️ PM Guard warning: uid={uid}, count={w}/{warn_limit}")
            if w < warn_limit:
                await event.reply(
                    f"**🔒 SECURITY ALERT**\n\n"
                    f"Owner is currently busy/offline😌\n"
                    f"Please wait and don't spam!\n\n"
                    f"⚠️ Warning: {w}/{warn_limit}\n\n"
                    f"🚫 {warn_limit}th warning = Automatic Block"
                                await event.reply("❌ User not found."); return
        chat_id = event.chat_id
        hearts = ['❤️', '🧡', '💛', '💚', '💙', '💜', '🖤', '🤍', '🤎', '💗']
        async def send_heart():
            await client.send_message(chat_id, f"{random.choice(hearts)} {user_link(uid)}", parse_mode='markdown')
        asyncio.create_task(raid_loop(event, uid, "hrr", send_heart, 1))
        await event.reply(f"💖 **Heart raid started!**")

    @cmd('shrr')
    async def sheart_raid_cmd(event):
        chat_id = str(event.chat_id)
        if chat_id in raid_state['hrr']:
            raid_state['hrr'][chat_id].clear()
            await event.reply("🛑 **Heart raid stopped!**")

    # ═══════════════ SPAM ═══════════════
    @cmd('spray')
    async def spray_cmd(event):
        args = get_args(event.message).strip()
        if not args:
            return
        parts = args.split()
        count = 10
        text = args
        if parts[0].isdigit():
            count = int(parts[0])
            text = ' '.join(parts[1:]).strip()
        elif parts[-1].isdigit():
            count = int(parts[-1])
            text = ' '.join(parts[:-1]).strip()
        if not text:
            return
        count = min(max(count, 1), 100)
        chat_id = event.chat_id
        db['spam_running'] = True

        async def spray_loop():
            for _ in range(count):
                if not db.get('spam_running', False):
                    break
                try:
                    await client.send_message(chat_id, text)
                    await asyncio.sleep(0.4)
                except FloodWaitError as e:
                    await asyncio.sleep(e.seconds + 2)
                except Exception:
                    break
            db['spam_running'] = False

        asyncio.create_task(spray_loop())

    @cmd('dspray')
    async def dspray_cmd(event):
        db['spam_running'] = False
        await event.reply("🛑 **Spam stopped!**")

    # ═══════════════ FUN ═══════════════
    @cmd('ping', delete_cmd=False)
    async def ping_cmd(event):
        start = time.time()
        msg = await event.reply("🏓 Pong!")
        await msg.edit(f"🏓 **Pong!** `{round((time.time() - start) * 1000, 2)}ms`", parse_mode='markdown')

    @cmd('flip', delete_cmd=False)
    async def flip_cmd(event):
        await event.reply(f"{random.choice(['**Heads** 🪙', '**Tails** 🪙'])}", parse_mode='markdown')

    @cmd('dice', delete_cmd=False)
    async def dice_cmd(event):
        await event.reply(f"🎲 **Dice:** `{random.randint(1, 6)}`", parse_mode='markdown')

    # ═══════════════ STALK ═══════════════
    @cmd('stalk', delete_cmd=False)
    async def stalk_cmd(event):
        reply = await event.get_reply_message()
        if not reply:
            await event.reply("❌ Reply to a user's message!"); return
        try:
            user = await reply.get_sender()
            full = await client(functions.users.GetFullUserRequest(user.id))
            fu = full.full_user
            name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "Unknown"
            username = f"@{user.username}" if user.username else "Hidden"
            bio = fu.about or "No bio"
            photos = await client.get_profile_photos(user)
            status = "Unknown"
            if hasattr(user, 'status') and user.status:
                sn = type(user.status).__name__
                if 'Online' in sn: status = "🟢 Online NOW"
                elif 'Recently' in sn: status = "🟡 Recently"
                elif 'LastWeek' in sn: status = "🟠 Last week"
                elif 'LastMonth' in sn: status = "🔴 Last month"
                else: status = "⚫ Long time ago"
            premium = "⭐ Yes" if getattr(user, 'premium', False) else "No"
            verified = "✅ Yes" if getattr(user, 'verified', False) else "No"
            scam = "⚠️ YES!" if getattr(user, 'scam', False) else "No"
            fake = "⚠️ YES!" if getattr(user, 'fake', False) else "No"
            await event.reply(
            for:** `{query}`\n\n{lyr[:3900]}")
                return
            await msg.edit("❌ Lyrics not found. Try: `.lyrics artist - song`")
        except Exception as e:
            await msg.edit(f"❌ Error: `{str(e)[:150]}`")

    @cmd('songinfo', delete_cmd=False)
    async def songinfo_cmd(event):
        query = get_args(event.message)
        if not query:
            await event.reply("❌ Usage: `.songinfo <song>`"); return
        msg = await event.reply("🎵 Fetching details...")
        try:
            search = await deezer_search(query, 1)
            if not search or not search.get("data"):
                await msg.edit("❌ Song not found."); return
            track_id = search["data"][0]["id"]
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
                async with session.get(f"https://api.deezer.com/track/{track_id}") as resp:
                    track = await resp.json()
            dur = f"{track['duration'] // 60}:{track['duration'] % 60:02d}"
            explicit = "🔞 Yes" if track.get("explicit_lyrics") else "✅ No"
            await msg.edit(f"🎵 **Detailed Song Info**\n\n🎤 **Title:** `{track.get('title', 'N/A')}`\n👤 **Artist:** `{track['artist']['name']}`\n💿 **Album:** `{track['album']['title']}`\n📅 **Released:** `{track.get('release_date', 'N/A')}`\n⏱ **Duration:** `{dur}`\n🎛 **BPM:** `{track.get('bpm', 'N/A')}`\n🔞 **Explicit:** {explicit}\n🔗 [Listen]({track.get('link', '')})", parse_mode='markdown')
        except Exception as e:
            await msg.edit(f"❌ Error: `{str(e)[:150]}`")

    @cmd('spotify', delete_cmd=False)
    async def spotify_cmd(event):
        query = get_args(event.message)
        if not query:
            await event.reply("❌ Usage: `.spotify <query>`"); return
        msg = await event.reply("🎵 Searching...")
        try:
            data = await deezer_search(query, 5)
            if not data or not data.get("data"):
                await msg.edit("❌ No results found."); return
            text = f"🎵 **Search results:** `{query}`\n\n"
            for i, track in enumerate(data["data"], 1):
                dur = f"{track['duration'] // 60}:{track['duration'] % 60:02d}"
                preview = f"[▶️]({track['preview']})" if track.get("preview") else ""
                text += (f"**{i}.** `{track['title']}` – {track['artist']['name']}\n   ⏱ {dur} {preview} 🔗 [Listen]({track['link']})\n\n")
            await msg.edit(text, parse_mode='markdown')
        except Exception as e:
            await msg.edit(f"❌ Error: `{str(e)[:150]}`")

    @cmd('trending', delete_cmd=False)
    async def trending_cmd(event):
        msg = await event.reply("📊 Loading trending...")
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
                async with session.get("https://api.deezer.com/chart/0/tracks?limit=10") as resp:
                    data = await resp.json()
            if not data or not data.get("data"):
                await msg.edit("❌ Failed to load charts."); return
            text = "🔥 **Global Trending Songs**\n\n"
            for i, track in enumerate(data["data"], 1):
                dur = f"{track['duration'] // 60}:{track['duration'] % 60:02d}"
                medal = ["🥇", "🥈", "🥉"][i - 1] if i <= 3 else f"**{i}.**"
                text += f"{medal} `{track['title']}` – {track['artist']['name']} (⏱ {dur})\n"
            await msg.edit(text, parse_mode='markdown')
        except Exception as e:
            await msg.edit(f"❌ Error: `{str(e)[:150]}`")

    @cmd('ringtone', delete_cmd=False)
    async def ringtone_cmd(event):
        query = get_args(event.message)
        if not query:
            await event.reply("❌ Usage: `.ringtone <song>`"); return
        msg = await event.reply("🔔 Searching ringtones...")
        try:
            data = await deezer_search(query, 5)
            if not data or not data.get("data"):
                await msg.edit("❌ No ringtones found."); return
            text = f"🔔 **Ringtone Search:** `{query}`\n\n"
            found = False
            for i, track in enumerate(data["data"], 1):
                if track.get("preview"):
                    found = True
                    text += f"**{i}.** `{track['title']}` – {track['artist']['name']}\n   📥 [Download 30s]({track['preview']})\n\n"
            if not found:
                await msg.edit("❌ No previews available."); return
            await msg.edit(text, parse_mode='markdown')
                    final_box = ("╭═════════💗═╮\n❤ 𝐈 𝐋𝐎𝐕𝐄 𝐘𝐎𝐔 𝐓𝐎𝐎 ❤\n╰═💗═════════╯")
        try:
            if msg:
                await msg.edit(final_box)
            else:
                if target:
                    await client.send_message(event.chat_id, final_box, reply_to=target)
                else:
                    await event.reply(final_box)
        except:
            if target:
                await client.send_message(event.chat_id, final_box, reply_to=target)
            else:
                await event.reply(final_box)

    @cmd('matrix', delete_cmd=True)
    async def matrix_cmd(event):
        args = get_args(event.message)
        try: secs = int(args) if args else 8
        except: secs = 8
        secs = min(max(secs, 3), 20)
        chars = "01アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホ"
        msg = await send_anim(event, "`01001000`")
        try:
            total = secs * 2
            for i in range(total):
                line = "".join(random.choice(chars) for _ in range(14))
                await msg.edit(f"🟢 `{line}`" if i % 4 == 0 else f"`{line}`")
                await asyncio.sleep(0.5)
            for _ in range(2):
                await msg.edit("`Wake up, Neo...`"); await asyncio.sleep(0.9)
                await msg.edit("`Follow the white rabbit 🐇`"); await asyncio.sleep(0.9)
            await msg.edit("🎭 **Welcome to the Villain World** 🎭")
        except: pass

    @cmd('hearts', delete_cmd=True)
    async def hearts_cmd(event):
        text = get_args(event.message) or "CipherElite"
        hearts = ["💖", "💗", "💓", "💞", "💕", "❤️", "🧡", "💛", "💚", "💙", "💜"]
        msg = await send_anim(event, f"💖 {text} 💖")
        try:
            for _ in range(15):
                h1, h2, h3 = random.choice(hearts), random.choice(hearts), random.choice(hearts)
                await msg.edit(f"{h1} {text} {h2}")
                await asyncio.sleep(0.4)
            positions = ["💕", "  💕", "    💕", "      💕", "    💕", "  💕"]
            for i in range(12):
                pos = positions[i % len(positions)]
                await msg.edit(f"{pos}\n  {text}\n{pos}")
                await asyncio.sleep(0.3)
            await msg.edit(f"💖💗💓 **{text}** 💓💗💖")
        except: pass

    @cmd('countdown', delete_cmd=True)
    async def countdown_cmd(event):
        args = get_args(event.message)
        try: n = int(args) if args else 5
        except: n = 5
        n = min(max(n, 1), 30)
        msg = await send_anim(event, f"⏱️ Starting countdown from {n}...")
        try:
            for i in range(n, 0, -1):
                await msg.edit(f"⏱️ **{i}**")
                await asyncio.sleep(1.2)
            await msg.edit("🎉 **GO!** 🎉")
        except: pass

    @cmd('wave', delete_cmd=True)
    async def wave_cmd(event):
        text = get_args(event.message)
        if not text:
            await event.reply("❌ Usage: `.wave <text>`"); return
        waves = ["🌊", "〰️", "🌸", "🦋", "🤍", "💖", "✨", "💫", "🌟", "💝", "🎼", "🎵"]
        msg = await send_anim(event, f"🌊 {text} 🌊")
        try:
            for _ in range(2):
                for i in range(len(text)):
                    wave_text = "".join(f"**{ch}**" if j == i else ch for j, ch in enumerate(text))
                    await msg.edit(f"🌊 {wave_text} 🌊", parse_mode='markdown')
                    await asyncio.sleep(0.15)
            for i in range(10):
                pad = "  " * (i % 4)
                w1 = waves[i % len(waves)]
                w2 = waves[(i + 5) % len(waves)]
                await msg.edit(f"{w1} {pad}{text}{pad} {w2}")
                await asyncio.sleep(0.4)
            for i in range(12):
                w1, w2, w3 = waves[i % len(waves)], waves[(i + 3) % len(waves)], waves[(i + 6) % len(waves)]
                await msg.edit(f"{w1} {w2} {text} {w3} {w1}")
                await asyncio.sleep(0.35)
            effects = [f"✨✨✨\n✨ **{text}** ✨\n✨✨✨", f"🌊〰️🌊\n〰️ **{text}** 〰️\n🌊〰️🌊", f"💖🌸💖\n🌸 **{text}** 🌸\n💖🌸💖", f"🦋✨🦋\n✨ **{text}** ✨\n🦋✨🦋"]
            for _ in range(3):
                for eff in effects:
                    await msg.edit(eff, parse_mode='markdown')
                    await asyncio.sleep(0.6)
            await msg.edit(f"╔═══════════════╗\n   ✨ **{text}** ✨\n╚═══════════════╝", parse_mode='markdown')
            await asyncio.sleep(1)
            await msg.edit(f"🦋🌸✨\n💫 **{text}** 💫\n✨🌸🦋", parse_mode='markdown')
                    except: pass
            
                        # Safe and Simple ASCII Art
                            # Safe ASCII Art Dictionary
    ascii_art = {
        "art1": "CODER NOVA"
    }

# Art register karne ka function
def _register_art(key, art):
    @cmd(key, delete_cmd=True)
    async def art_handler(event):
        await reply_to_target(event, art)
    return art_handler

for _key, _art in ascii_art.items():
    _register_art(_key, _art)

    # ═══════════════ PUBLIC FEATURES ═══════════════
    @cmd('weather', owner_only=True, delete_cmd=False)
    async def weather_cmd(event):
        city = get_args(event.message)
        if not city:
            await event.reply("❌ **Usage:** `.weather city`"); return
        try:
            city = city.strip().lower()
            if city == 'bihar': city = 'patna'
            url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        city_name = data.get('name', city.title())
                        country = data.get('sys', {}).get('country', '')
                        temp = data['main']['temp']
                        feels_like = data['main']['feels_like']
                        desc = data['weather'][0]['description'].title()
                        humidity = data['main']['humidity']
                        wind = data['wind']['speed']
                        pressure = data['main']['pressure']
                        emoji_map = {'clear': '☀️', 'clouds': '☁️', 'rain': '🌧️', 'snow': '❄️', 'thunderstorm': '⛈️', 'drizzle': '🌦️', 'mist': '🌫️', 'smoke': '💨', 'haze': '🌫️'}
                        emoji = '🌤️'
                        for key, em in emoji_map.items():
                            if key in desc.lower(): emoji = em; break
                        msg = (f"**{emoji} Weather Report: {city_name}, {country}**\n📅 {datetime.now().strftime('%d %b %Y, %I:%M %p')}\n\n🌡️ **Temperature:** {temp}°C\n🌡️ **Feels Like:** {feels_like}°C\n📝 **Condition:** {desc}\n💧 **Humidity:** {humidity}%\n🌬️ **Wind Speed:** {wind} m/s\n📊 **Pressure:** {pressure} hPa")
                        await event.reply(msg)
                    else:
                        await event.reply(f"❌ City '{city}' not found.")
        except Exception as e:
            await event.reply(f"❌ Error: {str(e)[:100]}")

    @cmd('news', owner_only=True, delete_cmd=False)
    async def news_cmd(event):
        query = get_args(event.message)
        try:
            if query:
                url = f"https://newsapi.org/v2/everything?q={query}&apiKey={NEWS_API_KEY}&language=en&sortBy=publishedAt&pageSize=5"
            else:
                url = f"https://newsapi.org/v2/top-headlines?country=in&apiKey={NEWS_API_KEY}&pageSize=5"
            async with 
                        async with aiohttp.ClientSession() as s:
                async with s.get(url) as r:
                    if r.status != 200:
                        await msg.edit("❌ City not found"); return
                    data = await r.json()
            text = f"🌤️ **5-Day Forecast: {data['city']['name']}**\n\n"
            daily = {}
            for item in data['list']:
                date = item['dt_txt'].split()[0]
                if date not in daily: daily[date] = item
            for date, item in list(daily.items())[:5]:
                temp = item['main']['temp']
                desc = item['weather'][0]['description'].title()
                emoji_map = {'clear': '☀️', 'clouds': '☁️', 'rain': '🌧️', 'snow': '❄️', 'thunderstorm': '⛈️', 'drizzle': '🌦️', 'mist': '🌫️'}
                em = '🌤️'
                for k, v in emoji_map.items():
                    if k in desc.lower(): em = v; break
                text += f"**{date}** {em} {temp}°C — {desc}\n"
            await msg.edit(text, parse_mode='markdown')
        except Exception as e:
            await msg.edit(f"❌ Error: `{str(e)[:200]}`")

    @cmd('aqi', owner_only=True, delete_cmd=False)
    async def aqi_cmd(event):
        city = get_args(event.message)
        if not city:
            await event.reply("❌ Usage: `.aqi <city>`"); return
        msg = await event.reply("🌫️ Loading AQI...")
        try:
            geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={city}&limit=1&appid={WEATHER_API_KEY}"
            async with aiohttp.ClientSession() as s:
                async with s.get(geo_url) as r:
                    geo = await r.json()
            if not geo:
                await msg.edit("❌ City not found"); return
            lat, lon = geo[0]['lat'], geo[0]['lon']
            aqi_url = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={WEATHER_API_KEY}"
            async with aiohttp.ClientSession() as s:
                async with s.get(aqi_url) as r:
                    data = await r.json()
            aqi = data['list'][0]['main']['aqi']
            components = data['list'][0]['components']
            levels = {1: "🟢 Good", 2: "🟡 Fair", 3: "🟠 Moderate", 4: "🔴 Poor", 5: "⚫ Very Poor"}
            text = (f"🌫️ **AQI: 
            {city.title()}**\n\n**Air Quality:** {levels.get(aqi, 'Unknown')} ({aqi}/5)\n\n**Pollutants:**\n• PM2.5: {components.get('pm2_5', 0)} µg/m³\n• PM10: {components.get('pm10', 0)} µg/m³\n• NO₂: {components.get('no2', 0)} µg/m³\n• O₃: {components.get('o3', 0)} µg/m³\n• CO: {components.get('co', 0)} µg/m³")
            await msg.edit(text, parse_mode='markdown')
        except Exception as e:
            await msg.edit(f"❌ Error: `{str(e)[:200]}`")


# ═══════════════ STARTUP ═══════════════
async def main():
    asyncio.create_task(health_server())
    asyncio.create_task(cleanup_temp_loop())
    mongo_ok = await init_mongo()
    if mongo_ok:
        await load_all()
        async def delayed_cleanup():
            await asyncio.sleep(5)
            await cleanup_old_command_logs()
        asyncio.create_task(delayed_cleanup())
        asyncio.create_task(auto_cleanup_loop())
    else:
        log.warning("⚠️ No MongoDB — data will be lost")

    asyncio.create_task(get_ghost_image_path())

    me = await bot.get_me()
    log.info(f"✅ Bot: @{me.username}")
    log.info(f"👑 Owner: {OWNER_ID}")

    restored = 0
    failed = 0
    for uid, u in list(users_db.items()):
        if u.get("logged_in") and u.get("session_string"):
            if uid in blocked_users:
                continue
            try:
                await start_ub(uid, u["session_string"])
                restored += 1
            except Exception as e:
                failed += 1
                log.error(f"Restore {uid}: {e}")

    log.info(f"✅ Restored {restored} userbot(s)")
    if failed:
        log.warning(f"⚠️ Failed to restore: {failed} userbot(s)")
    log.info(f"🚫 Blocked users: {len(blocked_users)}")
    log.info(f"📊 Command usage tracked: {len(command_usage_db)} users")
    log.info("⚙️ Type .help in Telegram.")
    await bot.run_until_disconnected()


if __name__ == '__main__':
    print("=" * 45)
    print("  CODERNOVA MULTI-USER USERBOT")
    print("=" * 45)
    try:
        bot.loop.run_until_complete(main())
    except KeyboardInterrupt:
        log.info("🛑 Stopped.")
    except Exception as e:
        log.error(f"Fatal: {e}")

     """
