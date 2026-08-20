import asyncio
import logging
import os
import re
import sys
import time
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import RPCError

# 1. Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("AutoResponder")

# 2. Load environment variables
load_dotenv()

def sanitize_session_string(s: str) -> str:
    """Removes all whitespace, newlines, tabs, and quotes from a session string."""
    if not s:
        return ""
    return "".join(s.split()).strip("\"'")

def clean_env(key: str, default: str = "") -> str:
    """Safely retrieves and cleans standard environment variables."""
    val = os.getenv(key, default)
    if val is None:
        return default
    return val.strip().strip('"').strip("'")

API_ID_RAW = clean_env("TELEGRAM_API_ID")
API_HASH = clean_env("TELEGRAM_API_HASH")
STRING_SESSION = sanitize_session_string(os.getenv("TELEGRAM_STRING_SESSION", ""))
SESSION_NAME = clean_env("TELEGRAM_SESSION_NAME", "user_session")
TARGET_CONTACT_RAW = clean_env("TARGET_CONTACT", "ALL")
AUTO_REPLY_MESSAGE = clean_env("AUTO_REPLY_MESSAGE", "Hi, Harsha is currently busy")
COOLDOWN_SECONDS = int(clean_env("COOLDOWN_SECONDS", "30"))  # Cooldown per user to prevent spam
PORT = clean_env("PORT")  # Injected automatically by Render for Web Services

# Track last reply timestamp per chat_id for cooldown
last_reply_time = {}


def parse_targets(target_str: str):
    """Parses target contacts from comma-separated string or 'ALL'/'*'."""
    if not target_str or target_str.upper() in ("ALL", "*", "ANY"):
        return "ALL"
    
    targets = []
    for item in target_str.split(","):
        cleaned = item.strip()
        if not cleaned:
            continue
        try:
            targets.append(int(cleaned))
        except ValueError:
            targets.append(cleaned)
    return targets if targets else "ALL"


async def start_health_server(port: int):
    """Starts a lightweight HTTP server for Render Web Service health checks."""
    try:
        from aiohttp import web
        app = web.Application()

        async def handle_ping(request):
            return web.Response(text="TeleBot is running OK ✅", status=200)

        app.router.add_get("/", handle_ping)
        app.router.add_get("/health", handle_ping)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        logger.info(f"🌐 Health check HTTP server is listening on port {port} (for Render)")
        return runner
    except Exception as e:
        logger.warning(f"Could not start HTTP health server on port {port}: {e}")
        return None


async def main():
    # Validate API credentials
    if not API_ID_RAW or not API_HASH:
        logger.error("Missing TELEGRAM_API_ID or TELEGRAM_API_HASH in environment variables.")
        print("\n[!] Please configure your Telegram API credentials in Render Environment Variables:")
        print("    TELEGRAM_API_ID=your_api_id")
        print("    TELEGRAM_API_HASH=your_api_hash")
        print("    TELEGRAM_STRING_SESSION=your_string_session\n")
        sys.exit(1)

    try:
        api_id = int(API_ID_RAW)
    except ValueError:
        logger.error(f"TELEGRAM_API_ID must be a valid integer, got: {API_ID_RAW}")
        sys.exit(1)

    targets = parse_targets(TARGET_CONTACT_RAW)
    is_all_contacts = (targets == "ALL")

    logger.info(f"Target Mode: {'ALL Contacts / Private DMs' if is_all_contacts else f'Specific Targets: {targets}'}")
    logger.info(f"Auto-Reply Message: '{AUTO_REPLY_MESSAGE}'")
    logger.info(f"Cooldown per user: {COOLDOWN_SECONDS}s")

    # Initialize TelegramClient with StringSession (cloud/Render) or SQLite Session (local)
    session = None
    if STRING_SESSION:
        logger.info(f"🔑 Initializing client with TELEGRAM_STRING_SESSION (Length: {len(STRING_SESSION)} chars)...")
        try:
            session = StringSession(STRING_SESSION)
        except Exception as err:
            logger.critical("=" * 60)
            logger.critical(f"❌ Failed to parse TELEGRAM_STRING_SESSION: {err}")
            logger.critical(f"String received (first 20 chars): '{STRING_SESSION[:20]}...' (Total len: {len(STRING_SESSION)})")
            logger.critical("Please regenerate your StringSession using: python generate_string_session.py")
            logger.critical("=" * 60)
            sys.exit(1)
    else:
        logger.info(f"📁 Initializing client with local file session '{SESSION_NAME}.session'...")
        session = SESSION_NAME

    client = TelegramClient(session, api_id, API_HASH)

    # Connect non-interactively to avoid EOFError on headless cloud environments (Render)
    logger.info("Connecting to Telegram...")
    await client.connect()

    # Verify authorization
    if not await client.is_user_authorized():
        # If in interactive local terminal, offer login prompt
        if not STRING_SESSION and sys.stdin and sys.stdin.isatty():
            logger.info("Local terminal detected. Prompting for login...")
            await client.start()
        else:
            logger.critical("=" * 60)
            logger.critical("❌ ERROR: Telegram client is NOT authorized!")
            logger.critical("Reason: TELEGRAM_STRING_SESSION is missing or invalid in Render Environment Variables.")
            logger.critical("=" * 60)
            logger.critical("👉 How to fix on Render:")
            logger.critical("1. Run 'python generate_string_session.py' on your local computer.")
            logger.critical("2. Go to Render Dashboard -> Your Web Service -> Environment.")
            logger.critical("3. Add environment variable: TELEGRAM_STRING_SESSION=<your_session_string>")
            logger.critical("4. Save Changes & Redeploy.")
            logger.critical("=" * 60)
            sys.exit(1)

    me = await client.get_me()
    logger.info(f"✅ Successfully logged in as: {me.first_name} (@{me.username}) [ID: {me.id}]")

    # Optional: Start health server if PORT is set (e.g. on Render Web Service)
    health_runner = None
    if PORT:
        try:
            port_num = int(PORT)
            health_runner = await start_health_server(port_num)
        except ValueError:
            logger.warning(f"Invalid PORT value '{PORT}', skipping HTTP health server.")

    # Pre-resolve target entities if specific targets are set
    resolved_target_ids = set()
    if not is_all_contacts:
        for t in targets:
            try:
                entity = await client.get_entity(t)
                eid = getattr(entity, "id", t)
                resolved_target_ids.add(eid)
                name = getattr(entity, "first_name", getattr(entity, "title", str(t)))
                logger.info(f"Resolved target: '{name}' (ID: {eid})")
            except Exception as e:
                logger.warning(f"Could not pre-resolve target '{t}': {e}. Using raw value.")
                if isinstance(t, int):
                    resolved_target_ids.add(t)

    # Register NewMessage event handler with case-insensitive 'hi' pattern
    # Regex: (?i)^hi[!.]*$ matches "hi", "Hi", "HI", "hi!", "Hi.", "HI!!", etc.
    @client.on(events.NewMessage(incoming=True, pattern=r'(?i)^hi[!.]*$'))
    async def auto_reply_handler(event: events.NewMessage.Event):
        try:
            # 1. Ignore outgoing messages or messages from yourself
            if event.out:
                return

            # 2. Only auto-reply in private chats (DMs) to avoid spamming groups/channels
            if not event.is_private:
                return

            # 3. Ignore messages from bots
            sender = await event.get_sender()
            if getattr(sender, "bot", False):
                return

            sender_name = getattr(sender, "first_name", "Unknown") if sender else "Unknown"
            chat_id = event.chat_id
            received_text = event.raw_text

            # 4. If specific targets configured, ensure sender matches
            if not is_all_contacts:
                sender_username = f"@{sender.username}".lower() if getattr(sender, "username", None) else None
                sender_id = getattr(sender, "id", chat_id)

                matches_target = (
                    sender_id in resolved_target_ids or
                    chat_id in resolved_target_ids or
                    (sender_username and sender_username in [str(t).lower() for t in targets])
                )
                if not matches_target:
                    return

            # 5. Cooldown check (prevent spamming if user sends 'hi' repeatedly)
            now = time.time()
            if chat_id in last_reply_time and (now - last_reply_time[chat_id]) < COOLDOWN_SECONDS:
                remaining = int(COOLDOWN_SECONDS - (now - last_reply_time[chat_id]))
                logger.info(f"[Cooldown] Skipping auto-reply to {sender_name} (ID: {chat_id}) - {remaining}s remaining.")
                return

            logger.info(f"[Incoming Match] From: {sender_name} (Chat ID: {chat_id}) | Text: '{received_text}'")

            # 6. Dispatch automated reply
            await event.reply(AUTO_REPLY_MESSAGE)
            last_reply_time[chat_id] = now
            logger.info(f"[Auto-Reply] ✅ Successfully sent auto-reply to {sender_name} (Chat ID: {chat_id})")

        except RPCError as rpc_err:
            logger.error(f"[RPC Error] Telegram error while responding: {rpc_err}")
        except Exception as exc:
            logger.error(f"[Handler Error] Unexpected error in event handler: {exc}", exc_info=True)

    logger.info("=" * 60)
    logger.info("🤖 Telethon Auto-Responder is ACTIVE.")
    logger.info(f"🎯 Listening for 'Hi' from: {'ALL Private Chats' if is_all_contacts else targets}")
    logger.info(f"💬 Auto-Response: '{AUTO_REPLY_MESSAGE}'")
    logger.info("Press Ctrl+C to stop.")
    logger.info("=" * 60)

    # Keep client running until interrupted
    try:
        await client.run_until_disconnected()
    except (asyncio.CancelledError, KeyboardInterrupt):
        logger.info("Shutdown signal received.")
    finally:
        if health_runner:
            await health_runner.cleanup()
            logger.info("Health server stopped.")
        if client.is_connected():
            await client.disconnect()
            logger.info("Client disconnected cleanly.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Auto-responder terminated by user.")
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
