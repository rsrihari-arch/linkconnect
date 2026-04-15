FROM python:3.11-slim

WORKDIR /app

# Install system deps for Playwright
RUN apt-get update && apt-get install -y \
    wget gnupg \
    libglib2.0-0 libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2 libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

# Install API deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install worker deps (includes playwright)
COPY worker_requirements.txt .
RUN pip install --no-cache-dir -r worker_requirements.txt
RUN playwright install chromium

COPY . .

EXPOSE 8000

# Default: run the API server. Override with `python worker.py` for the worker.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
