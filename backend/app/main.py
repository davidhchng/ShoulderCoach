from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import ALLOWED_ORIGINS
from app.database import create_all_tables, count_total_rows

app = FastAPI(
    title="ShoulderCoach",
    description="In-game basketball decision assistant backed by NBA historical data",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    create_all_tables()


@app.get("/api/health")
def health():
    from app.engine.registry import ENGINES
    db_rows = count_total_rows()
    return {
        "status": "ok",
        "db_rows": db_rows,
        "engines_registered": len(ENGINES),
    }


# Routers are imported here after engines are defined (Steps 4 & 9)
def _mount_routers():
    from app.routers.meta import router as meta_router
    from app.routers.decisions import router as decisions_router
    from app.routers.coach import router as coach_router
    app.include_router(meta_router, prefix="/api")
    app.include_router(decisions_router, prefix="/api")
    app.include_router(coach_router, prefix="/api")


_mount_routers()
