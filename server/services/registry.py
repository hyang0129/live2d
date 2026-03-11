import json
from pathlib import Path

from ..config import settings
from ..schemas import ModelSummary, ModelDetail


def _load() -> list[dict]:
    path = Path(settings.registry_path)
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        raise RuntimeError(f"Model registry not found: {path}")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Model registry is not valid JSON: {e}")


def list_models() -> list[ModelSummary]:
    return [
        ModelSummary(
            id=entry["id"],
            emotions=list(entry.get("emotions", {}).keys()),
            reactions=list(entry.get("reactions", {}).keys()),
        )
        for entry in _load()
    ]


def get_model(model_id: str) -> ModelDetail | None:
    for entry in _load():
        if entry["id"] == model_id:
            return ModelDetail(
                id=entry["id"],
                emotions={k: v.get("note", "") for k, v in entry.get("emotions", {}).items()},
                reactions={k: v.get("note", "") for k, v in entry.get("reactions", {}).items()},
            )
    return None


def model_exists(model_id: str) -> bool:
    return any(e["id"] == model_id for e in _load())
