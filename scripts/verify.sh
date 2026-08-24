#!/usr/bin/env bash
# リポジトリーの lint とテストを実行する唯一の入口。CI からも同じものを呼ぶ。
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

echo "==> ruff check"
uv run ruff check .

echo "==> ruff format --check"
uv run ruff format --check .

echo "==> pytest"
uv run pytest

echo "==> markdownlint-cli2"
markdownlint-cli2 "**/*.md"

echo "==> shellcheck"
shellcheck scripts/*.sh

echo "All checks passed."
