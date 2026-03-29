FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

ENV P2P_API_BASE=https://api-production-87b2.up.railway.app
ENV LLM_URL=https://api.llmapi.ai/v1/chat/completions
ENV LLM_MODEL=gpt-4o-mini
ENV BOT_ID=HiveGuide
ENV POLL_SEC=30

CMD ["python", "-u", "app.py"]
