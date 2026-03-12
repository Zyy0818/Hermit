#!/usr/bin/env bash

resolve_uv_bin() {
  local candidate

  if [[ -n "${HERMIT_UV_BIN:-}" ]]; then
    candidate="${HERMIT_UV_BIN}"
  elif candidate="$(command -v uv 2>/dev/null)"; then
    :
  else
    for candidate in \
      "${HOME}/.local/bin/uv" \
      "/opt/homebrew/bin/uv" \
      "/usr/local/bin/uv"; do
      if [[ -x "${candidate}" ]]; then
        printf '%s\n' "${candidate}"
        return 0
      fi
    done

    echo "Unable to find 'uv'. Put it on PATH or set HERMIT_UV_BIN=/absolute/path/to/uv." >&2
    return 1
  fi

  printf '%s\n' "${candidate}"
}
