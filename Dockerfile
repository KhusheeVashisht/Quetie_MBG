FROM node:20-slim AS frontend-build
WORKDIR /workspace
COPY . /workspace
WORKDIR /workspace/frontend
RUN npm ci
RUN npm run build

FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends build-essential git curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app
COPY --from=frontend-build /workspace/quetie/web/static /app/quetie/web/static

EXPOSE 8000

# Start the unified runner which can run the web dashboard, the bot, or both.
# Running with `--mode all` launches the bot runtime (if TWITCH_OAUTH_TOKEN is set)
# and the web dashboard in the same container, suitable for simple Render deployments.
CMD ["python", "main.py", "--mode", "all"]
