# AgentOS frontend

## Run locally

1. Start the FastAPI server from `server/`:

   ```bash
   uv run uvicorn backend.main:app --reload
   ```

2. Copy `.env.local.example` to `.env.local` if your API runs somewhere other
   than `http://127.0.0.1:8000`.

3. Install and start the frontend:

   ```bash
   npm install
   npm run dev
   ```

Open `http://localhost:3000`.
