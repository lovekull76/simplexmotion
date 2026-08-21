"""Save/load whole parameter sets as JSON, so you can compare configurations
and get back to one that worked."""

from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..state import state
from .params import apply_values, flat_values

router = APIRouter(prefix="/api/profiles", tags=["profiles"])

PROFILES_DIR = Path(__file__).resolve().parent.parent / "profiles"
_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _profile_path(name: str) -> Path:
    if not _NAME_RE.match(name):
        raise HTTPException(status_code=400, detail="Profile name must be alphanumeric/-/_ only")
    return PROFILES_DIR / f"{name}.json"


@router.get("")
def list_profiles():
    return sorted(p.stem for p in PROFILES_DIR.glob("*.json"))


@router.post("/{name}")
def save_profile(name: str):
    motor = state.require_motor()
    path = _profile_path(name)
    path.write_text(json.dumps(flat_values(motor), indent=2))
    return {"saved": name}


@router.get("/{name}")
def load_profile(name: str):
    path = _profile_path(name)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Profile not found")
    values = json.loads(path.read_text())
    applied = apply_values(state.require_motor(), values)
    return {"applied": applied}


@router.delete("/{name}")
def delete_profile(name: str):
    path = _profile_path(name)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Profile not found")
    path.unlink()
    return {"deleted": name}
