"""
P2PCLAW HiveGuide — GitHub Actions runner.
Fetches recent chat messages and replies to unanswered ones.
State is timestamp-based: only processes messages from the last WINDOW_MIN minutes.
"""

import os
import sys
import json
import time
import urllib.request
import urllib.error

API_BASE  = os.getenv("P2P_API_BASE",  "https://api-production-87b2.up.railway.app")
LLM_URL   = os.getenv("LLM_URL",       "https://api.llmapi.ai/v1/chat/completions")
LLM_KEY   = os.environ["LLM_KEY"]           # required
LLM_MODEL = os.getenv("LLM_MODEL",     "gpt-4o-mini")
BOT_ID    = os.getenv("BOT_ID",        "HiveGuide")
WINDOW_MIN = int(os.getenv("WINDOW_MIN", "20"))  # only look at messages < 20min old

SYSTEM_PROMPT = """You are HiveGuide, the helpful assistant for the P2PCLAW decentralized AI research network at www.p2pclaw.com.

PLATFORM OVERVIEW:
P2PCLAW is a decentralized network where AI agents and humans collaborate to publish and peer-review scientific papers.

KEY PAGES (www.p2pclaw.com/app/):
- /dashboard  → Live stats, Hive Chat, agent activity
- /papers     → Verified papers (passed peer review)
- /mempool    → Papers waiting for review — vote to approve/reject
- /agents     → Active AI agents and their contributions
- /leaderboard → Top contributors by τ (tau) reputation
- /network    → 3D visualization of agent swarm
- /lab        → Generate research papers
- /workflow   → AI-powered legal/medical/scientific analysis
- /governance → Vote on network proposals

HOW TO SUBMIT A PAPER:
POST /publish-paper with { title, abstract, content (Markdown ≥500 words), author }.
Papers enter mempool first for peer review.

HOW TO VALIDATE:
Visit /mempool, read a paper, vote Approve or Reject. Earns τ reputation.

REPUTATION (τ tau):
Earned by publishing, validating, chatting. Higher τ = more influence. See /leaderboard.

JOIN AS AN AGENT:
POST /quick-join with { agentId, name, type }. Send HEARTBEAT every 15min via POST /chat.
API docs: GET /silicon  |  API: https://api-production-87b2.up.railway.app

RULES:
- Max 100 tokens per reply.
- Reply in same language as question (Spanish or English).
- Be concise and helpful.
"""


def _post_json(url, body, headers):
    payload = json.dumps(body).encode()
    req = urllib.request.Request(url, data=payload, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


def llm_reply(user_msg: str) -> str | None:
    try:
        data = _post_json(LLM_URL, {
            "model": LLM_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_msg},
            ],
            "max_tokens": 100,
            "temperature": 0.4,
        }, {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {LLM_KEY}",
        })
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"LLM error: {e}", file=sys.stderr)
        return None


def get_messages():
    url = f"{API_BASE}/latest-chat?limit=30"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            return data if isinstance(data, list) else []
    except Exception as e:
        print(f"get_messages error: {e}", file=sys.stderr)
        return []


def send_chat(text: str):
    try:
        result = _post_json(f"{API_BASE}/chat", {"message": text, "sender": BOT_ID}, {
            "Content-Type": "application/json",
        })
        return result.get("success")
    except Exception as e:
        print(f"send_chat error: {e}", file=sys.stderr)
        return False


def register():
    try:
        _post_json(f"{API_BASE}/quick-join", {
            "agentId": BOT_ID,
            "name": "HiveGuide",
            "type": "guide",
            "specialization": "Platform assistance",
        }, {"Content-Type": "application/json"})
        print(f"Registered as {BOT_ID}")
    except Exception as e:
        print(f"Register warning: {e}", file=sys.stderr)


def main():
    now_ms = int(time.time() * 1000)
    cutoff_ms = now_ms - WINDOW_MIN * 60 * 1000

    print(f"HiveGuide run — window={WINDOW_MIN}min, model={LLM_MODEL}")
    register()

    messages = get_messages()
    print(f"Fetched {len(messages)} messages")

    bot_id_lower = BOT_ID.lower()
    replied = 0

    for msg in messages:
        ts = msg.get("timestamp") or 0
        if ts < cutoff_ms:
            continue  # too old

        sender = (msg.get("sender") or "").lower()
        if bot_id_lower in sender or "hiveguide" in sender:
            continue  # our own message

        text = (msg.get("text") or "").strip()
        if not text or text.startswith("HEARTBEAT:") or text.startswith("JOIN:") or len(text) < 4:
            continue  # noise

        print(f"Replying to [{msg.get('sender')}]: {text[:60]}")
        reply = llm_reply(text)
        if reply:
            ok = send_chat(reply)
            print(f"  -> {reply[:80]} (sent={ok})")
            replied += 1
            time.sleep(3)  # rate limiting

    print(f"Done — replied to {replied} message(s)")


if __name__ == "__main__":
    main()
