from __future__ import annotations

import hashlib
import json
from typing import Any

_UNSET = object()


def _json_loads(raw: str | None) -> Any:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _canonical_json_from_raw(raw: str | None) -> str:
    if raw is None or raw == "":
        return _canonical_json({})
    try:
        return _canonical_json(json.loads(raw))
    except json.JSONDecodeError:
        return _canonical_json(raw)


def _sha256_hex(value: str | bytes) -> str:
    payload = value.encode("utf-8") if isinstance(value, str) else value
    return hashlib.sha256(payload).hexdigest()
