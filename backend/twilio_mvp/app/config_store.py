from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .settings import DATA_DIR


CONFIG_PATH = DATA_DIR / "device_config.json"
STATE_PATH = DATA_DIR / "runtime_state.json"

DEFAULT_CONFIG = {
    "device_id": "esp32-max30102-01",
    "device_token": "CAMBIAR_TOKEN",
    "admin_phone": "",
    "contacts": [],
    "reset_code": "2468",
}

DEFAULT_STATE = {
    "last_alert": None,
    "last_startup": None,
    "audit_log": [],
}


def _ensure_file(path: Path, default_payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(json.dumps(default_payload, indent=2), encoding="utf-8")


def _load_json(path: Path, default_payload: dict[str, Any]) -> dict[str, Any]:
    _ensure_file(path, default_payload)
    return json.loads(path.read_text(encoding="utf-8"))


def _save_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def normalize_phone(number: str) -> str:
    cleaned = "".join(ch for ch in number if ch.isdigit() or ch == "+")
    if cleaned.startswith("+"):
        return cleaned
    if cleaned.startswith("51") and len(cleaned) >= 11:
        return "+" + cleaned
    if len(cleaned) == 9 and cleaned.startswith("9"):
        return "+51" + cleaned
    return cleaned


def load_config() -> dict[str, Any]:
    config = _load_json(CONFIG_PATH, DEFAULT_CONFIG)
    config["admin_phone"] = normalize_phone(config.get("admin_phone", ""))
    config["contacts"] = [normalize_phone(item) for item in config.get("contacts", []) if item]
    return config


def save_config(config: dict[str, Any]) -> None:
    normalized = dict(config)
    normalized["admin_phone"] = normalize_phone(normalized.get("admin_phone", ""))
    normalized["contacts"] = [normalize_phone(item) for item in normalized.get("contacts", []) if item]
    _save_json(CONFIG_PATH, normalized)


def load_state() -> dict[str, Any]:
    return _load_json(STATE_PATH, DEFAULT_STATE)


def save_state(state: dict[str, Any]) -> None:
    _save_json(STATE_PATH, state)


def append_audit_event(event: dict[str, Any], limit: int = 50) -> dict[str, Any]:
    state = load_state()
    history = list(state.get("audit_log", []))
    history.append(event)
    state["audit_log"] = history[-limit:]
    save_state(state)
    return state


def recipients(config: dict[str, Any]) -> list[str]:
    numbers = []
    if config.get("admin_phone"):
        numbers.append(normalize_phone(config["admin_phone"]))
    for item in config.get("contacts", []):
        normalized = normalize_phone(item)
        if normalized and normalized not in numbers:
            numbers.append(normalized)
    return numbers


def is_admin(config: dict[str, Any], number: str) -> bool:
    return normalize_phone(number) == normalize_phone(config.get("admin_phone", ""))


def is_authorized(config: dict[str, Any], number: str) -> bool:
    normalized = normalize_phone(number)
    return normalized == normalize_phone(config.get("admin_phone", "")) or normalized in [
        normalize_phone(item) for item in config.get("contacts", [])
    ]
