#!/usr/bin/env bash
# プラグインを配布用の zip アーカイブにまとめる。
# 既定では検証を通してからまとめる。壊れたものを配らないため。
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
plugin_name="claude-code-security-audit"
manifest="$repo_root/.claude-plugin/plugin.json"
output_dir="$repo_root/dist"
skip_check=false

usage() {
  cat <<'USAGE'
Usage: package.sh [--output <dir>] [--skip-check]

  --output <dir>  アーカイブの出力先。既定は <repo>/dist
  --skip-check    scripts/verify.sh の実行を省く（テストからの呼び出し用）
USAGE
}

while [ $# -gt 0 ]; do
  case "$1" in
    --output)
      output_dir="${2:?--output には出力先のディレクトリーを指定してください}"
      shift 2
      ;;
    --skip-check)
      skip_check=true
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

if [ "$skip_check" != true ]; then
  "$repo_root/scripts/verify.sh"
fi

version="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$manifest")"

mkdir -p "$output_dir"
output_dir="$(cd "$output_dir" && pwd)"
archive="$output_dir/$plugin_name-$version.zip"

# 一時領域ではなく出力先の下で組み立てる。出力先は必ず書き込めるため。
staging="$output_dir/.package-staging"
trap 'rm -rf "$staging"' EXIT
rm -rf "$staging"

package_root="$staging/$plugin_name"
mkdir -p "$package_root"
cp -R "$repo_root/.claude-plugin" "$package_root/"
cp -R "$repo_root/skills" "$package_root/"
cp "$repo_root/README.md" "$package_root/"
find "$package_root" -type d -name '__pycache__' -prune -exec rm -rf {} +

rm -f "$archive"
(cd "$staging" && zip -rq "$archive" "$plugin_name")

echo "作成しました: $archive"
