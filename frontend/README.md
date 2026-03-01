# VidyaSetu Frontend (Vite + React)

This frontend is designed to run locally and proxy API calls to the FastAPI backend.

## Run locally

From the `frontend/` folder:

1. Install deps:
	- `npm install`
2. Start dev server:
	- `npm run dev`

Default dev URL: `http://localhost:8080`

## Backend connectivity

This app calls the backend via the `/api/*` prefix.

- In dev, [frontend/vite.config.ts](vite.config.ts) proxies `/api/*` to the backend.
- Override backend target (optional): set `VITE_BACKEND_URL`.

Example:
- `VITE_BACKEND_URL=http://127.0.0.1:8000`
