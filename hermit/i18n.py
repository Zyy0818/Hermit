from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Mapping

DEFAULT_LOCALE = "en-US"

_LOCALE_ALIASES = {
    "en": "en-US",
    "en-us": "en-US",
    "zh": "zh-CN",
    "zh-cn": "zh-CN",
    "zh-hans": "zh-CN",
}


def normalize_locale(value: str | None) -> str:
    if not value:
        return DEFAULT_LOCALE
    cleaned = value.strip().replace("_", "-")
    if not cleaned:
        return DEFAULT_LOCALE
    canonical = _LOCALE_ALIASES.get(cleaned.lower())
    if canonical:
        return canonical
    if "-" in cleaned:
        language, region = cleaned.split("-", 1)
        return f"{language.lower()}-{region.upper()}"
    return cleaned.lower()


def locale_from_env(environ: Mapping[str, str] | None = None) -> str:
    env = environ or os.environ
    for key in ("HERMIT_LOCALE", "LC_ALL", "LC_MESSAGES", "LANG"):
        raw = env.get(key)
        if not raw:
            continue
        candidate = raw.split(".", 1)[0].split("@", 1)[0]
        return normalize_locale(candidate)
    return DEFAULT_LOCALE


def resolve_locale(preferred: str | None = None, environ: Mapping[str, str] | None = None) -> str:
    if preferred:
        return normalize_locale(preferred)
    return locale_from_env(environ)


def _catalog_dir() -> Path:
    return Path(__file__).resolve().parent / "locales"


@lru_cache(maxsize=None)
def _load_catalog(locale: str) -> dict[str, str]:
    canonical = normalize_locale(locale)
    catalog = dict(_read_catalog(DEFAULT_LOCALE))
    if canonical != DEFAULT_LOCALE:
        catalog.update(_read_catalog(canonical))
    return catalog


def _read_catalog(locale: str) -> dict[str, str]:
    path = _catalog_dir() / f"{locale}.json"
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    return {str(key): str(value) for key, value in raw.items()}


def tr(key: str, *, locale: str | None = None, default: str | None = None, **kwargs: object) -> str:
    canonical = resolve_locale(locale)
    template = _load_catalog(canonical).get(key, default if default is not None else key)
    if kwargs:
        try:
            return template.format(**kwargs)
        except Exception:
            return template
    return template
