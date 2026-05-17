# InfinityGuard AI

AI finance operations layer for cross-border SMB payments.

InfinityGuard AI is a production-style full-stack fintech project: a standalone finance intelligence system with mock APIs, webhooks, fraud detection, FX recommendations, cash forecasting, compliance scoring, and a state-aware AI finance copilot.

## Stack

- Frontend: React, Vite, TailwindCSS, React Router, Recharts, Framer Motion
- Backend: FastAPI, JWT auth, REST APIs, background event handling, webhook ingestion
- Data: PostgreSQL
- Cache/queue: Redis
- ML service: FastAPI, scikit-learn, XGBoost, pandas, Prophet dependency, joblib-ready runtime
- Deployment: Docker, docker-compose, Vercel frontend config, Render backend/ML blueprint

## Run With Docker

```bash
docker compose up --build
```

Open:

- Frontend: `http://localhost:8080`
- Backend API docs: `http://localhost:8000/docs`
- ML health: `http://localhost:9000/health`

Seed users:

- `admin@infinityguard.ai` / `AdminPass123`
- `finance@infinityguard.ai` / `FinancePass123`
- `viewer@infinityguard.ai` / `ViewerPass123`

## Local Development

Backend:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

ML service:

```bash
cd ml-service
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 9000
```

Frontend:

```bash
cd frontend
npm install
copy .env.example .env
npm run dev
```

## Key APIs

- `POST /api/auth/signup`
- `POST /api/auth/login`
- `POST /api/auth/refresh`
- `GET /api/payments`
- `GET /api/invoices`
- `GET /api/customers`
- `GET /api/transactions`
- `GET /api/fx-rates`
- `POST /api/webhooks/payment-received`
- `POST /api/webhooks/invoice-created`
- `POST /api/compliance/check`
- `POST /api/predict/payment-delay`
- `POST /api/predict/fx`
- `POST /api/predict/anomaly`
- `POST /api/predict/runway`
- `POST /api/copilot`

## Example Webhook

```bash
curl -X POST http://localhost:8000/api/webhooks/payment-received \
  -H "Authorization: Bearer <access-token>" \
  -H "Content-Type: application/json" \
  -d "{\"external_ref\":\"pay_live_001\",\"customer_name\":\"Northstar Robotics\",\"country\":\"US\",\"currency\":\"USD\",\"amount\":42000,\"invoice_number\":\"INV-2026-1001\",\"rail\":\"ACH\"}"
```

## Project Structure

```text
frontend/      React dashboard and Vercel config
backend/       FastAPI API, auth, domain models, webhooks, compliance, copilot
ml-service/    ML prediction service
docker/        shared deployment config
docs/          architecture notes
```

See `docs/ARCHITECTURE.md` for the service design.
