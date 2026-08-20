import os
import sys
from dotenv import load_dotenv
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

load_dotenv()

API_ID_RAW = os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("TELEGRAM_API_HASH")
SESSION_NAME = os.getenv("TELEGRAM_SESSION_NAME", "user_session")

def main():
    print("=" * 60)
    print("🔑 Telethon StringSession Generator for Render Deployment")
    print("=" * 60)

    api_id = API_ID_RAW
    api_hash = API_HASH

    if not api_id or not api_hash:
        print("\nMissing TELEGRAM_API_ID or TELEGRAM_API_HASH in .env.")
        api_id = input("Enter your Telegram API ID: ").strip()
        api_hash = input("Enter your Telegram API Hash: ").strip()

    try:
        api_id = int(api_id)
    except ValueError:
        print(f"Error: API ID must be an integer. Received: {api_id}")
        sys.exit(1)

    # Check if a local session file already exists
    session_file = f"{SESSION_NAME}.session"
    if os.path.exists(session_file):
        print(f"\n[+] Found existing session file '{session_file}'. Attempting direct export...")
        try:
            with TelegramClient(SESSION_NAME, api_id, api_hash) as client:
                if client.is_user_authorized():
                    session_str = StringSession.save(client.session)
                    me = client.get_me()
                    print(f"[+] Successfully exported session for: {me.first_name} (@{me.username}) [ID: {me.id}]")
                    display_result(session_str)
                    return
                else:
                    print("[-] Existing session file is not authorized. Proceeding to fresh login...")
        except Exception as e:
            print(f"[-] Could not export from file ({e}). Proceeding to login...")

    # Interactive StringSession login
    print("\n[+] Initiating interactive login for StringSession...")
    with TelegramClient(StringSession(), api_id, api_hash) as client:
        session_str = client.session.save()
        me = client.get_me()
        print(f"\n[+] Logged in as: {me.first_name} (@{me.username}) [ID: {me.id}]")
        display_result(session_str)


def display_result(session_str: str):
    print("\n" + "=" * 60)
    print("🎉 YOUR TELEGRAM_STRING_SESSION IS READY:")
    print("=" * 60)
    print(f"\n{session_str}\n")
    print("=" * 60)
    print("📋 WHAT TO DO NEXT FOR RENDER:")
    print("1. Go to your Render Dashboard -> Your Service -> Environment")
    print("2. Add an environment variable:")
    print(f"   Key:   TELEGRAM_STRING_SESSION")
    print(f"   Value: {session_str}")
    print("=" * 60)


if __name__ == "__main__":
    main()
