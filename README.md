# LinkConnect - LinkedIn Automation Platform

Automate LinkedIn connection requests and campaigns. Upload leads via CSV, create campaigns with custom messages, and send connection requests automatically with rate limiting and safety controls.

## Tech Stack

- **Frontend**: Next.js 15, TypeScript, Tailwind CSS
- **Backend**: Python, FastAPI, SQLAlchemy (async)
- **Automation**: Playwright (headless Chromium)
- **Database**: PostgreSQL
- **Deployment**: Docker, Docker Compose, Nginx

## Features

- Connect LinkedIn accounts (credentials encrypted at rest)
- Create campaigns with daily limits and message templates
- Upload leads via CSV or add individually
- Background automation engine with random delays (20-60s)
- Campaign dashboard with real-time stats
- Safety: max 30 requests/day, auto-retry failed once, skip non-connectable profiles

---

## Quick Start (Docker - Recommended)

### 1. Generate encryption key

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 2. Configure environment

Edit `.env` in the project root:

```
ENCRYPTION_KEY=<paste-key-from-step-1>
SECRET_KEY=<any-random-string>
```

### 3. Build and run

```bash
docker compose up --build -d
```

The app will be available at:
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000/docs
- **Nginx proxy**: http://localhost:80

### 4. Stop

```bash
docker compose down
```

---

## Deploy to a VPS (DigitalOcean, AWS EC2, Hetzner, etc.)

### 1. Provision a server

- Ubuntu 22.04+ recommended
- Minimum 2GB RAM, 1 vCPU
- Open ports: 80 (HTTP), 443 (HTTPS if using SSL)

### 2. Install Docker

```bash
# On the server:
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# Log out and back in, then:
docker --version
```

### 3. Clone and deploy

```bash
git clone <your-repo-url> linkedin-automation
cd linkedin-automation

# Generate encryption key
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Edit .env with your keys
nano .env

# Build and start
docker compose up --build -d
```

### 4. Point your domain

- Add an A record pointing your domain to the server IP
- Update `nginx/nginx.conf` → replace `server_name _` with `server_name yourdomain.com`
- For HTTPS, add Certbot:

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com
```

### 5. Update frontend API URL

In `docker-compose.yml`, update the `NEXT_PUBLIC_API_URL` arg:

```yaml
frontend:
  build:
    args:
      NEXT_PUBLIC_API_URL: https://yourdomain.com
```

Then rebuild: `docker compose up --build -d`

---

## Deploy to Railway / Render

### Railway

1. Push code to GitHub
2. Go to [railway.app](https://railway.app), create new project
3. Add a PostgreSQL service
4. Add backend service (point to `/backend` directory, set Dockerfile)
5. Add frontend service (point to `/frontend` directory, set Dockerfile)
6. Set environment variables:
   - `DATABASE_URL` = Railway PostgreSQL connection string (use `asyncpg` driver)
   - `ENCRYPTION_KEY` = your generated key
   - `NEXT_PUBLIC_API_URL` = backend service URL

### Render

1. Push code to GitHub
2. Create a PostgreSQL database on Render
3. Create a Web Service for backend (Docker, `/backend`)
4. Create a Web Service for frontend (Docker, `/frontend`)
5. Set env vars same as above

---

## Local Development (without Docker)

### Prerequisites

- Python 3.11+
- Node.js 20+
- PostgreSQL running locally

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# Create .env
cat > .env << EOF
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/linkedin_automation
ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
HEADLESS=true
EOF

# Create database
createdb linkedin_automation

# Run
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install

# .env.local already set to http://localhost:8000
npm run dev
```

---

## CSV Format

Upload a CSV with these columns (header required):

| linkedin_url | name |
|---|---|
| https://www.linkedin.com/in/john-doe | John Doe |
| jane-smith | Jane Smith |

- `linkedin_url` (required): Full URL or just the profile slug
- `name` (optional): Display name

Accepted header names: `linkedin_url`, `url`, `profile_url`, `LinkedIn URL`, `name`, `Name`, `full_name`

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/accounts/ | Add LinkedIn account |
| GET | /api/accounts/ | List accounts |
| POST | /api/accounts/{id}/login | Trigger LinkedIn login |
| DELETE | /api/accounts/{id} | Delete account |
| POST | /api/campaigns/ | Create campaign |
| GET | /api/campaigns/ | List campaigns |
| GET | /api/campaigns/{id} | Campaign detail + stats |
| POST | /api/campaigns/{id}/start | Start campaign |
| POST | /api/campaigns/{id}/stop | Stop campaign |
| DELETE | /api/campaigns/{id} | Delete campaign |
| POST | /api/campaigns/{id}/leads/upload | Upload CSV |
| GET | /api/campaigns/{id}/leads | List leads |

Full Swagger docs available at `/docs` when running the backend.

---

## Safety Controls

- Max 30 connection requests per day per account
- Random delay between actions: 20-60 seconds
- Failed requests retried once, then marked as skipped
- Session cookies saved to avoid repeated logins
- Credentials encrypted with Fernet symmetric encryption
