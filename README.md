# Telegram Auto-Responder Bot (TeleBot)

An automated 24/7 personal Telegram responder built with **Telethon**, designed for seamless deployment on **Render**, Docker, or any Linux server.

---

## ⚡ Key Features
- **Instant Auto-Reply**: Matches incoming greetings (`Hi`, `Hello`, `Hey`, etc.) in private direct messages.
- **Render Ready**: Includes a built-in HTTP health check server for Render Web Services (Free Tier) and supports `StringSession` to avoid headless terminal login issues.
- **Spam / Cooldown Protection**: Prevents spamming users with a configurable cooldown timer.
- **Target Filtering**: Can respond to `ALL` private contacts or specific target IDs/usernames.

---

## 🚀 Deploying to Render (Step-by-Step)

### Step 1: Generate your `TELEGRAM_STRING_SESSION`
Because Render is headless (no terminal for OTP SMS verification), you need a StringSession for cloud authentication:
```bash
python generate_string_session.py
```
*(If you already logged in locally, this exports your session instantly without prompting for a new OTP code).*
Copy the generated string session.

### Step 2: Push code to GitHub
Initialize git and push your repository to GitHub:
```bash
git init
git add .
git commit -m "Deploy Telegram bot to Render"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

### Step 3: Create a Web Service on Render
1. Go to [Render Dashboard](https://dashboard.render.com/) and click **New +** -> **Web Service**.
2. Connect your GitHub repository.
3. Configure the service:
   - **Name**: `telebot-auto-responder`
   - **Language / Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python main.py`
   - **Plan**: `Free`

4. Add your **Environment Variables**:
   | Key | Value | Description |
   |---|---|---|
   | `TELEGRAM_API_ID` | `your_api_id` | From [my.telegram.org](https://my.telegram.org) |
   | `TELEGRAM_API_HASH` | `your_api_hash` | From [my.telegram.org](https://my.telegram.org) |
   | `TELEGRAM_STRING_SESSION` | `1BVts...` | The StringSession from Step 1 |
   | `TARGET_CONTACT` | `ALL` | `ALL` or comma-separated user IDs |
   | `AUTO_REPLY_MESSAGE` | `Hi, Harsha is currently busy...` | Your custom message |
   | `COOLDOWN_SECONDS` | `30` | Seconds between replies to the same contact |

5. Click **Create Web Service**.

> [!TIP]
> **Keep-Alive (Render Free Tier)**: Free services on Render spin down after 15 minutes of web inactivity. You can use a free uptime monitor (like [UptimeRobot](https://uptimerobot.com/) or [cron-job.org](https://cron-job.org/)) to ping your Render URL (`https://your-service.onrender.com/health`) every 10 minutes.

---

## 💻 Local Development Setup

1. **Clone and create a virtual environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configure `.env`**:
   ```bash
   cp .env.example .env
   ```

3. **Run locally**:
   ```bash
   python main.py
   ```
# TeleBot
