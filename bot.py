import os
import sys
import logging
from dotenv import load_dotenv
from google.adk.agents.llm_agent import Agent
from adk_connectors.telegram import TelegramConnector
from adk_connectors.models.incoming import IncomingMessage
from adk_connectors.models.outgoing import OutgoingMessage
from agent import create_agent

# 1. Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("TelegramBot")

# 2. Load environment variables
load_dotenv()

# Retrieve configuration
telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
google_api_key = os.getenv("GOOGLE_API_KEY")
model_name = os.getenv("GEMINI_MODEL", "gemini-3.7-flash")

# Auto-reply configuration
AUTO_REPLY_MESSAGE = os.getenv(
    "AUTO_REPLY_MESSAGE",
    "Hello! 👋 Thanks for reaching out. How can I assist you today?"
)
# If ONLY_RESPOND_TO_HI is True, the bot will strictly respond to "Hi"/greetings and ignore all other messages.
# If False, "Hi" triggers the instant auto-reply, while all other messages are processed by the Google ADK Agent.
ONLY_RESPOND_TO_HI = os.getenv("ONLY_RESPOND_TO_HI", "True").strip().lower() in ("true", "1", "yes")

# Target Chat ID(s) filter (e.g., "2029901529"). Comma-separated if multiple, or empty to allow all chats.
target_chat_env = os.getenv("TARGET_CHAT_ID", "2029901529").strip()
TARGET_CHAT_IDS = [cid.strip() for cid in target_chat_env.split(",") if cid.strip()]

# Validation check
if not telegram_token or telegram_token.startswith("your_"):
    logger.error("Missing or invalid TELEGRAM_BOT_TOKEN in .env")
    print("Please obtain a bot token from @BotFather on Telegram and set it in your .env file.")
    sys.exit(1)

if not google_api_key or google_api_key.startswith("your_"):
    logger.warning("GOOGLE_API_KEY is not set or using placeholder in .env.")
    print("Make sure your Google Gemini API key is configured for ADK to work.")

# 3. Define your Google ADK Agent
assistant = create_agent(model=model_name)


def is_target_chat(chat_id: str, user_id: str) -> bool:
    """Checks if the incoming message is from a target chat ID."""
    if not TARGET_CHAT_IDS:
        return True  # If empty, allow all chats
    cid = str(chat_id).strip()
    uid = str(user_id).strip()
    for target in TARGET_CHAT_IDS:
        if cid == target or uid == target or cid.endswith(target) or uid.endswith(target):
            return True
    return False


def is_hi_message(text: str) -> bool:
    """Checks if the incoming message is a 'Hi', greeting, or /start."""
    if not text:
        return False
    
    clean = text.strip().lower()
    
    # Handle /start command (Telegram's default start button)
    if clean.startswith("/start"):
        return True
        
    # Strip trailing punctuation
    normalized = clean.rstrip("!.,:;?~ ")
    
    greeting_triggers = {
        "hi", "hii", "hiii", "hiiii",
        "hello", "helloo", "hey", "heyy", "heya",
        "hola", "namaste", "greetings", "yo",
        "good morning", "good afternoon", "good evening"
    }
    
    # Exact match check
    if normalized in greeting_triggers:
        return True
        
    # Multi-word greeting check (e.g. "hi there", "hello bot", "hey friend")
    words = normalized.split()
    if words and words[0] in greeting_triggers and len(words) <= 4:
        return True
        
    return False


if __name__ == "__main__":
    logger.info(f"Starting Telegram Bot with Google ADK Agent ({assistant.name})...")
    logger.info(f"Model: {model_name}")
    logger.info(f"Target Chat ID(s): {TARGET_CHAT_IDS if TARGET_CHAT_IDS else 'All chats'}")
    logger.info(f"Auto Message Sender: Enabled for 'Hi' greetings")
    logger.info(f"Only Respond to 'Hi': {'Enabled (Ignoring non-Hi messages)' if ONLY_RESPOND_TO_HI else 'Disabled (Passing other messages to Google ADK)'}")

    # 4. Bind the connector
    connector = TelegramConnector(
        token=telegram_token,
        agent=assistant,
        streaming=True
    )

    # 5. Attach auto-responder interceptor
    original_handler = connector.manager.handle_incoming_message

    async def custom_message_handler(message: IncomingMessage):
        user_text = (message.text or "").strip()
        chat_id_str = str(message.chat_id)
        user_id_str = str(message.user_id)
        
        is_target = is_target_chat(chat_id_str, user_id_str)
        is_hi = is_hi_message(user_text)

        logger.info(
            f"[Incoming] Chat ID: {chat_id_str} | User ID: {user_id_str} | "
            f"Target Match: {'YES' if is_target else 'NO'} | Message: '{user_text}'"
        )
        
        # Check if the incoming message is from target chat and is a "Hi" greeting
        if is_target and is_hi:
            logger.info(f"[Auto-Sender] ✅ 'Hi' detected from TARGET chat {chat_id_str}. Sending auto-reply: '{AUTO_REPLY_MESSAGE}'")
            reply = OutgoingMessage(
                chat_id=message.chat_id,
                text=AUTO_REPLY_MESSAGE
            )
            try:
                await connector.adapter.send_message(message.chat_id, reply)
                logger.info(f"[Auto-Sender] 🚀 Reply delivered successfully to chat {chat_id_str}")
            except Exception as e:
                logger.error(f"[Auto-Sender] ❌ Failed to send reply to chat {chat_id_str}: {e}")
            return

        # If strict "Hi only" or target-only mode is enabled, ignore non-matching messages
        if ONLY_RESPOND_TO_HI or not is_target:
            if not is_target:
                logger.info(f"[Auto-Sender] Message from non-target chat {chat_id_str} ignored.")
            else:
                logger.info(f"[Auto-Sender] Non-'Hi' message from chat {chat_id_str} ignored (ONLY_RESPOND_TO_HI=True).")
            return

        # Otherwise, forward standard messages to the Google ADK Agent
        logger.info(f"[Google ADK] Forwarding query to agent: '{user_text}'")
        await original_handler(message)

    # Register the custom handler with the Telegram adapter
    connector.adapter.register_message_handler(custom_message_handler)

    # 6. Start polling
    try:
        connector.start()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")


