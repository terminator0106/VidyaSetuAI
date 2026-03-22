# VidyaSetu Backend (FastAPI)

This backend is designed to run locally in a normal Python virtual environment.

Note: Docker has been removed temporarily for development speed (ML dependency builds were too slow). The architecture is kept clean so Docker can be re-added later without redesign.

## API surface (unchanged)
- Auth: `POST /api/auth/signup`, `POST /api/auth/login`, `GET /api/auth/session`, `POST /api/auth/logout`
- Ingest: `POST /api/ingest/pdf` (also `POST /api/ingest` alias)
- Ask: `POST /api/ask`
- Admin: `GET /api/admin/savings` (admin-only)

Backend base URL: `http://localhost:8000`

## Local setup (Windows)

### 1) Python virtual environment
From the `backend/` folder:

1. Create venv:
   - `py -m venv venv`
2. Activate:
   - `venv\Scripts\activate`
3. Install deps:
   - `pip install -r requirements.txt`

### 2) Configure environment
1. Ensure you have a `backend/.env` file (this project loads config only from `.env`).
2. Use `.env.example` as a template.

Minimum required:
- `JWT_SECRET`

LLM provider (pick one):
- Default (`LLM_PROVIDER=groq`): set `GROQ_API_KEY`
- If `LLM_PROVIDER=openai`: set `OPENAI_API_KEY`

PDF ingestion storage (required for ingest):
- `CLOUDINARY_CLOUD_NAME`
- `CLOUDINARY_API_KEY`
- `CLOUDINARY_API_SECRET`

Local defaults are already set for:
- `POSTGRES_HOST=localhost`
- `POSTGRES_PORT=5432`
- `REDIS_URL=redis://localhost:6379/0`

Optional admin seed (idempotent):
- `ADMIN_EMAIL`
- `ADMIN_PASSWORD`

### 3) PostgreSQL (local)
You need a local Postgres instance and a database matching `POSTGRES_DB`.

Common options:
- Install Postgres locally (Windows installer) and create database `vidyasetu`.
- Ensure your user/password match `POSTGRES_USER`/`POSTGRES_PASSWORD`.

Tables auto-create on startup if missing.

### 3b) Supabase (hosted Postgres)
Supabase is still PostgreSQL under the hood; this backend connects via SQLAlchemy.

1. In Supabase, go to **Project Settings → Database** and copy the connection details.
2. In `backend/.env`, set:
   - `POSTGRES_HOST=db.<project-ref>.supabase.co`
   - `POSTGRES_PORT=5432`
   - `POSTGRES_DB=postgres` (or your DB name)
   - `POSTGRES_USER=postgres`
   - `POSTGRES_PASSWORD=...`
   - `POSTGRES_SSLMODE=require`

Notes:
- Supabase requires SSL; `POSTGRES_SSLMODE=require` is the important bit.
- You can also set `DATABASE_URL` directly if you prefer; if it points to a `*.supabase.co` host and omits `sslmode`, the backend auto-enforces `sslmode=require`.

Basic migration (local Postgres → Supabase):
- Export: `pg_dump --no-owner --no-privileges -Fc -h localhost -U <user> <db> > dump.dump`
- Import: restore into Supabase using `pg_restore` (or Supabase tooling) with the connection string credentials.

If you don't want to install Postgres for local dev, you can run with SQLite instead by setting:
- `DATABASE_URL=sqlite:///./data/vidyasetu.db`

### 4) Redis (local)
Run Redis on `localhost:6379`.

If Redis is down, the backend will log a warning once and automatically fall back to an in-memory cache (so the app still works). This fallback is per-process and resets on restart.

Windows-friendly options to run Redis:
- Docker Desktop: `docker run --name vidyasetu-redis -p 6379:6379 -d redis:7-alpine`
- Memurai (Redis-compatible for Windows): install and ensure it listens on `127.0.0.1:6379`
- WSL: install Redis inside your WSL distro and expose port `6379`

## Run the server
From the `backend/` folder with venv activated:

- Recommended (reload only on Python code changes; ignores `data/` changes like PDF deletes):
   - `uvicorn app.main:app --reload --reload-include "*.py" --reload-exclude "data/*" --reload-exclude "data/**" --host 127.0.0.1 --port 8000`

- If you prefer the simple command (may reload on PDF/data changes):
   - `uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`

Health check:
- `GET http://localhost:8000/health`

`/health` reports basic dependency status (DB + Redis) to make local setup issues obvious.

## Frontend connectivity
The frontend lives in `frontend/` (Vite). It proxies `/api/*` to the backend.

Defaults:
- Frontend dev server: `http://localhost:8080`
- Backend: `http://localhost:8000`

If you need to override the backend URL, set in the frontend:
- `VITE_BACKEND_URL=http://localhost:8000`

## Data persistence
- Embeddings + FAISS index + chunk files are persisted under `backend/data/` by default.
- You can override with `DATA_DIR` in `.env`.

## Chapter splitting accuracy
Chapters are split using the Table of Contents (printed page numbers). The backend auto-detects the offset between printed page numbers (header/footer) and the underlying PDF page index, so chapter ranges align with the page numbers printed on the textbook pages.

## OCR for scanned / multilingual PDFs (Windows)
Some textbooks (especially Hindi/Marathi/Gujarati scans) have little or unreadable embedded text. In that case ingestion uses an OCR fallback via `pytesseract`, which requires the **system Tesseract** binary.

Checklist:
- Ensure `tesseract.exe` is installed and available on your `PATH` (verify with `where tesseract`).
- Ensure language packs for `eng`, `hin`, `mar`, `guj` are installed/available in Tesseract's `tessdata`.

If Tesseract (or those language packs) are missing, ingest will fail with a descriptive error telling you OCR is required.
