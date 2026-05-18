from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import get_settings
from .database import Base, SessionLocal, engine
from .routers import auth, intelligence, payment_app, resources, webhooks
from .seed import seed


settings = get_settings()
app = FastAPI(title="InfinityGuard AI API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()


@app.get("/health")
def health():
    return {"status": "ok", "service": "backend"}


app.include_router(auth.router)
app.include_router(resources.router)
app.include_router(payment_app.router)
app.include_router(webhooks.router)
app.include_router(intelligence.router)
