#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_NAME="${1:-}"

if [[ -z "${ENV_NAME}" ]]; then
  echo "Usage: scripts/hermit-menubar-install-env.sh <prod|dev|test> [extra appbundle args...]" >&2
  exit 1
fi

case "${ENV_NAME}" in
  prod)
    export HERMIT_BASE_DIR="${HOME}/.hermit"
    ;;
  dev)
    export HERMIT_BASE_DIR="${HOME}/.hermit-dev"
    ;;
  test)
    export HERMIT_BASE_DIR="${HOME}/.hermit-test"
    ;;
  *)
    echo "Unknown environment: ${ENV_NAME}" >&2
    echo "Allowed values: prod, dev, test" >&2
    exit 1
    ;;
esac

shift

exec /opt/homebrew/bin/uv run --project "${ROOT_DIR}" --python 3.11 python -m hermit.companion.appbundle "$@"
