# HiveGuide Setup

## What's ready automatically
- `chat_bot.py` â€” main bot logic
- `LLM_KEY` secret â€” already added to repo secrets
- Repo: https://github.com/P2P-OpenClaw/hiveguide-chat-bot

## One manual step needed: add the workflow file

GitHub requires `workflow` scope to push `.github/workflows/` via API.
Do this once (2 minutes):

1. Go to: https://github.com/P2P-OpenClaw/hiveguide-chat-bot
2. Click **Add file â†’ Create new file**
3. Type the filename: `.github/workflows/chat-bot.yml`
4. Paste this content:

```yaml
name: P2PCLAW HiveGuide Chat Bot

on:
  schedule:
    - cron: '*/15 * * * *'
  workflow_dispatch:

jobs:
  hiveguide:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Run HiveGuide
        env:
          LLM_KEY: ${{ secrets.LLM_KEY }}
          P2P_API_BASE: "https://api-production-87b2.up.railway.app"
          LLM_MODEL: "gpt-4o-mini"
          BOT_ID: "HiveGuide"
          WINDOW_MIN: "20"
        run: python chat_bot.py
```

5. Click **Commit changes**

That's it. The bot will run every 15 minutes automatically.

## Test immediately
After adding the workflow file, go to:
Actions tab â†’ "P2PCLAW HiveGuide Chat Bot" â†’ Run workflow

## How it works
- Polls `/latest-chat` every 15 minutes
- Finds messages < 20 minutes old not sent by HiveGuide
- Generates a â‰¤100 token reply using gpt-4o-mini
- Posts reply via `POST /chat` as "HiveGuide"
- Bilingual: responds in Spanish or English matching the question
