# InfinityGuard AI Architecture

InfinityGuard AI is a standalone finance intelligence layer for cross-border SMB payment operations. It is designed as a drop-in integration surface with REST APIs and webhooks, using simulated data and mock models instead of private fintech systems.

## Services

- `frontend`: React + Vite dashboard with TailwindCSS, React Router, Recharts, Framer Motion, and authenticated views.
- `backend`: FastAPI API service with JWT auth, role-based access, PostgreSQL persistence, Redis-backed event queue hooks, webhook handlers, compliance logic, and ML proxy endpoints.
- `ml-service`: Python FastAPI microservice using scikit-learn, XGBoost, pandas, and synthetic operational training data.
- `postgres`: system of record for users, customers, invoices, payments, transactions, FX rates, alerts, predictions, compliance checks, and event logs.
- `redis`: event queue/cache dependency for webhook processing.

## Integration Model

External payment processors, invoicing tools, or banking partners can call:

- `POST /api/webhooks/payment-received`
- `POST /api/webhooks/invoice-created`
- `POST /api/compliance/check`

The backend stores normalized data, logs events, creates operational alerts, and calls the ML service for risk or forecasting outputs. The dashboard consumes the same REST APIs a production integration would use.

## AI/ML Boundaries

The ML service is a recommendation and anomaly-scoring layer. FX outputs are framed as operational recommendations, not guaranteed market predictions. The copilot answers from system state: pending invoices, exposure, customers, predictions, and recent alerts.
