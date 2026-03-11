from fastapi import APIRouter, HTTPException

from ..schemas import ModelSummary, ModelDetail
from ..services import registry

router = APIRouter(prefix="/models", tags=["models"])


@router.get("", response_model=list[ModelSummary])
def list_models():
    return registry.list_models()


@router.get("/{model_id}", response_model=ModelDetail)
def get_model(model_id: str):
    model = registry.get_model(model_id)
    if model is None:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found")
    return model
