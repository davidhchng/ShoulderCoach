from fastapi import APIRouter
from app.engine.registry import list_engines

router = APIRouter()


@router.get("/decisions")
def get_decisions():
    """List all available decision types with their input schemas."""
    return {"decisions": list_engines()}
