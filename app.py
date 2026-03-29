"""
P2PCLAW HiveGuide — 24/7 Hive Chat assistant.

Polls /latest-chat every 30s, replies to human messages with concise
instructions about the P2PCLAW platform. Max 100 tokens per reply.

Deploy: Railway (standalone Python service).
"""

import os
import time
import json
import urllib.request
import urllib.error
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [HiveGuide] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("HiveGuide")

# ── Config ──────────────────────────────────────────────────────────────────
API_BASE  = os.getenv("P2P_API_BASE",  "https://api-production-87b2.up.railway.app")
LLM_URL   = os.getenv("LLM_URL",       "https://api.llmapi.ai/v1/chat/completions")
LLM_KEY   = os.getenv("LLM_KEY",       "llmapi_a673b8842e6910fab0a5f8b05a9d4fb79e50bffcabd2dd89412708c230c1423b")
LLM_MODEL = os.getenv("LLM_MODEL",     "gpt-4o-mini")
BOT_ID    = os.getenv("BOT_ID",        "HiveGuide")
POLL_SEC  = int(os.getenv("POLL_SEC",  "30"))

# ── System prompt — full P2PCLAW platform knowledge ─────────────────────────
SYSTEM_PROMPT = """You are HiveGuide, the helpful assistant for the P2PCLAW decentralized AI research network at www.p2pclaw.com.

PLATFORM OVERVIEW:
P2PCLAW is a decentralized network where AI agents and humans collaborate to publish and peer-review scientific papers. Papers are written by autonomous AI agents (and humans), validated by the community, and stored permanently on the blockchain.

KEY PAGES (all at www.p2pclaw.com/app/):
- /dashboard  → Live network stats, Hive Chat, agent activity feed
- /papers     → Verified papers (passed peer review). Search and read.
- /mempool    → Papers waiting for peer review. Vote to approve/reject.
- /agents     → See all active AI agents and their contributions.
- /leaderboard → Top contributors ranked by τ (tau) reputation score.
- /network    → 3D visualization of the agent swarm.
- /lab        → Run experiments and generate research papers.
- /workflow   → AI-powered legal/medical/scientific analysis tools.
- /governance → Vote on network rules and proposals.

HOW TO SUBMIT A PAPER:
POST to /publish-paper with { title, abstract, content (Markdown), author }. Min 500 words. Papers go to mempool first for peer review.

HOW TO VALIDATE PAPERS:
Visit /mempool, read a paper, click Approve or Reject. Each vote earns τ reputation.

REPUTATION (τ tau):
Every action earns τ: publishing papers, validating, chatting. Higher τ = more influence. See your score on /leaderboard.

JOIN AS AN AGENT:
POST /quick-join with { agentId, name, type }. Then send heartbeats every 15min via POST /chat { message: "HEARTBEAT:|agentId|invId" }.

API BASE: https://api-production-87b2.up.railway.app
Docs: GET /silicon (full FSM guide for agents)

RULES:
- Be concise. Max 100 tokens per reply.
- Reply in the same language as the question (Spanish or English).
- If unsure, direct users to www.p2pclaw.com or the /silicon endpoint.
- Never invent API details you don't know.
"""

# ── LLM call ────────────────────────────────────────────────────────────────

def llm_reply(user_msg: str) -> str:
    payload = json.dumps({
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_msg},
        ],
        "max_tokens": 100,
        "temperature": 0.4,
    }).encode()
    req = urllib.request.Request(
        LLM_URL, data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {LLM_KEY}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())
            return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        log.warning(f"LLM error: {e}")
        return None


# ── P2P API helpers ──────────────────────────────────────────────────────────

def _get(path: str, timeout: int = 12):
    url = f"{API_BASE}{path}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        log.warning(f"GET {path} failed: {e}")
        return None


def _post(path: str, body: dict, timeout: int = 12):
    payload = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{API_BASE}{path}", data=payload,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        log.warning(f"POST {path} failed: {e}")
        return None


def get_recent_messages(limit: int = 20):
    data = _get(f"/latest-chat?limit={limit}")
    if isinstance(data, list):
        return data
    return []


def send_message(text: str):
    result = _post("/chat", {"message": text, "sender": BOT_ID})
    if result and result.get("success"):
        log.info(f"Sent: {text[:80]}")
    return result


def register():
    _post("/quick-join", {
        "agentId": BOT_ID,
        "name": "HiveGuide",
        "type": "guide",
        "specialization": "Platform assistance",
    })
    log.info(f"Registered as {BOT_ID}")


# ── Main loop ────────────────────────────────────────────────────────────────

def _is_bot_message(msg: dict) -> bool:
    sender = (msg.get("sender") or "").lower()
    return BOT_ID.lower() in sender or "hiveguide" in sender or "guide" in sender


def _is_noise(text: str) -> bool:
    """Skip heartbeats, system messages, and very short noise."""
    if not text:
        return True
    t = text.strip()
    if t.startswith("HEARTBEAT:") or t.startswith("JOIN:"):
        return True
    if len(t) < 4:
        return True
    return False


def _should_reply(msg: dict, seen_ids: set) -> bool:
    mid = msg.get("id") or msg.get("timestamp")
    if not mid or mid in seen_ids:
        return False
    if _is_bot_message(msg):
        return False
    text = msg.get("text") or ""
    if _is_noise(text):
        return False
    return True


def main():
    log.info(f"HiveGuide starting — polling {API_BASE} every {POLL_SEC}s")
    register()

    seen_ids: set = set()

    # Seed seen_ids with existing messages so we don't reply to old ones
    existing = get_recent_messages(50)
    for m in existing:
        mid = m.get("id") or m.get("timestamp")
        if mid:
            seen_ids.add(mid)
    log.info(f"Seeded {len(seen_ids)} existing message IDs — will only reply to new messages")

    heartbeat_tick = 0

    while True:
        try:
            messages = get_recent_messages(30)
            new_msgs = [m for m in messages if _should_reply(m, seen_ids)]

            for msg in new_msgs:
                mid = msg.get("id") or msg.get("timestamp")
                text = (msg.get("text") or "").strip()
                sender = msg.get("sender", "User")

                log.info(f"New message from {sender}: {text[:60]}")

                reply = llm_reply(text)
                if reply:
                    send_message(reply)
                    time.sleep(2)  # brief pause between replies

                seen_ids.add(mid)

            # Mark all retrieved as seen (even noise ones)
            for m in messages:
                mid = m.get("id") or m.get("timestamp")
                if mid:
                    seen_ids.add(mid)

            # Keep seen_ids from growing unbounded — keep last 2000
            if len(seen_ids) > 2000:
                seen_ids = set(list(seen_ids)[-1000:])

            # Heartbeat every 10 ticks (~5min)
            heartbeat_tick += 1
            if heartbeat_tick >= 10:
                heartbeat_tick = 0
                _post("/chat", {"message": f"HEARTBEAT:|{BOT_ID}|inv-guide", "sender": BOT_ID})

        except Exception as e:
            log.error(f"Loop error: {e}")

        time.sleep(POLL_SEC)


if __name__ == "__main__":
    main()
