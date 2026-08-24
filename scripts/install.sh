#!/usr/bin/env bash
# 監査スキルを Claude Code のスキルディレクトリーへ配置する。
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# ディレクトリー名がそのままコマンド名（/security-audit）になる。
skill_name="security-audit"
source_dir="$repo_root/skills/$skill_name"
target_dir="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"
use_link=false
force=false

usage() {
  cat <<'USAGE'
Usage: install.sh [--target <dir>] [--link] [--force]

  --target <dir>  配置先。既定は ${CLAUDE_SKILLS_DIR:-~/.claude/skills}
  --link          コピーではなくシンボリックリンクを張る（開発用）
  --force         配置先に同名のスキルがあっても置き換える
USAGE
}

while [ $# -gt 0 ]; do
  case "$1" in
    --target)
      target_dir="${2:?--target には配置先のディレクトリーを指定してください}"
      shift 2
      ;;
    --link)
      use_link=true
      shift
      ;;
    --force)
      force=true
      shift
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      echo "不明な引数: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

destination="$target_dir/$skill_name"

if [ -e "$destination" ] || [ -L "$destination" ]; then
  if [ "$force" != true ]; then
    echo "既に存在します: ${destination}（置き換えるには --force を付けてください）" >&2
    exit 1
  fi
  rm -rf "$destination"
fi

mkdir -p "$target_dir"

if [ "$use_link" = true ]; then
  ln -s "$source_dir" "$destination"
else
  cp -R "$source_dir" "$destination"
  # テスト実行で生成される Python のキャッシュは配布物に含めない。
  find "$destination" -type d -name '__pycache__' -prune -exec rm -rf {} +
fi

echo "配置しました: $destination"
