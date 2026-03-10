"""Shared Feishu lark-oapi client factory."""
from __future__ import annotations

import os


def build_lark_client() -> "lark_oapi.Client":
    """Build a lark-oapi Client from environment variables.

    Reads HERMIT_FEISHU_APP_ID / HERMIT_FEISHU_APP_SECRET (with
    legacy FEISHU_APP_ID / FEISHU_APP_SECRET as fallbacks).

    Raises RuntimeError if credentials are not configured.
    """
    app_id = os.environ.get("HERMIT_FEISHU_APP_ID", os.environ.get("FEISHU_APP_ID", ""))
    app_secret = os.environ.get(
        "HERMIT_FEISHU_APP_SECRET",
        os.environ.get("FEISHU_APP_SECRET", ""),
    )
    if not app_id or not app_secret:
        raise RuntimeError(
            "Feishu credentials not configured. "
            "Set HERMIT_FEISHU_APP_ID and HERMIT_FEISHU_APP_SECRET."
        )
    import lark_oapi as lark

    return lark.Client.builder().app_id(app_id).app_secret(app_secret).build()
