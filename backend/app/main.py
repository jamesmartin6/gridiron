from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import backtest, games, predictions, teams

settings = get_settings()

app = FastAPI(
    title="Gridiron API",
    description="NFL game outcome predictions from prior-season team stats.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(teams.router)
app.include_router(games.router)
app.include_router(predictions.router)
app.include_router(backtest.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
