"""FastAPI app. Each feature is a module with its own routes, models,
schemas and services; this file only wires them together."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.challenges.routes import router as challenges_router
from app.core.config import settings
from app.progress.routes import router as progress_router
from app.submissions.routes import router as submissions_router
from app.users.routes import router as users_router

app = FastAPI(title="Pandas Visual Trainer API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (users_router, challenges_router, submissions_router, progress_router):
    app.include_router(router)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}
