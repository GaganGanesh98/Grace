# Grace

Cryptographic governance receipts for AI agents.

When your AI agent screws up and your lawyer asks what it did, Grace has a signed receipt.

- 6-stage governed execution pipeline (Intent → Strategy → Authority → Dispatch → Evidence → Receipt)
- Ed25519 + ML-DSA-65 (post-quantum FIPS 204) signatures
- RFC 6962 Merkle audit chain
- AES-256-GCM encrypted evidence vault
- Public verification endpoint (no account required)
- Court-admissible PDF export

Status: In active development.

## Local development (Phase 1)

1. Backend secrets: copy `.env.example` → **`apps/backend/.env`** (gitignored) or repo-root `.env` / `.env.dev` — see **[docs/auth-setup.md](docs/auth-setup.md)** for load order and Google OAuth.
2. Copy `apps/frontend/.env.example` → `apps/frontend/.env.local` and set `API_URL` to match the backend (default `http://localhost:8000`).
3. One-time Docker: your user must be in the **`docker`** group (**[docs/dev-setup.md](docs/dev-setup.md)**). `./axiom` never uses `sudo docker`.
4. Run **`./axiom dev`** (Postgres 18 + Redis via Compose; host ports **5433** and **6380**). **Ctrl+C** stops everything cleanly.
5. Backend only: `cd apps/backend && uv run uvicorn axiom.main:app --reload`.
6. Frontend only: `cd apps/frontend && npm run dev`.

Architecture and ADRs: `docs/architecture.md`, `docs/decisions.md`.

© 2026 Gagan Ganesh
