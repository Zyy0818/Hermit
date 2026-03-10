"""xAI Grok search — uses the Agent Tools API (web_search + x_search)."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

_XAI_BASE_URL = "https://api.x.ai/v1"
_DEFAULT_MODEL = "grok-4-1-fast-non-reasoning"


def _get_api_key() -> str:
    return os.environ.get("XAI_API_KEY") or os.environ.get("GROK_API_KEY") or ""


def handle_grok_search(payload: dict[str, Any]) -> str:
    query = str(payload.get("query", "")).strip()
    if not query:
        return "Error: empty query"

    api_key = _get_api_key()
    if not api_key:
        return (
            "Error: XAI_API_KEY is not set. "
            "Please set the XAI_API_KEY environment variable with your xAI API key."
        )

    model = str(payload.get("model", _DEFAULT_MODEL))
    max_tokens = int(payload.get("max_tokens", 2048))
    # search_type: "web" | "x" | "both" (default)
    search_type = str(payload.get("search_type", "both"))

    tools: list[dict[str, Any]] = []
    if search_type in ("web", "both"):
        tools.append({"type": "web_search"})
    if search_type in ("x", "both"):
        tools.append({"type": "x_search"})
    if not tools:
        tools = [{"type": "web_search"}]

    request_body: dict[str, Any] = {
        "model": model,
        "input": [{"role": "user", "content": query}],
        "max_output_tokens": max_tokens,
        "tools": tools,
    }

    data = json.dumps(request_body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{_XAI_BASE_URL}/responses",
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "Hermit/1.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            response_data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        if exc.code == 429:
            try:
                err_msg = json.loads(body).get("error") or body[:300]
            except Exception:
                err_msg = body[:300]
            return f"xAI 账户额度已耗尽：{err_msg}\n请前往 https://console.x.ai 充值或提升用量限制。"
        if exc.code == 401:
            return "xAI API Key 无效或已过期，请检查 XAI_API_KEY 配置。"
        return f"xAI API HTTP error {exc.code}: {body[:500]}"
    except Exception as exc:
        return f"xAI API error: {exc}"

    # /v1/responses returns output as a list of message objects
    content = ""
    output = response_data.get("output") or []
    for item in output:
        if isinstance(item, dict) and item.get("type") == "message":
            for block in item.get("content") or []:
                if isinstance(block, dict) and block.get("type") == "output_text":
                    content += block.get("text") or ""

    # Append citations
    citations = response_data.get("citations") or []
    if citations and content:
        lines = ["\n\n## 来源"]
        for i, c in enumerate(citations, 1):
            title = c.get("title") or c.get("url") or f"来源 {i}"
            url = c.get("url") or ""
            lines.append(f"{i}. [{title}]({url})" if url else f"{i}. {title}")
        content += "\n".join(lines)

    return content or "（Grok 返回了空响应）"
