#!/usr/bin/env bash
# プラグインを配布用の zip アーカイブにまとめる。
# 既定では検証を通してからまとめる。壊れたものを配らないため。
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
plugin_name="claude-code-security-audit"
skill_name="security-audit"
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

# 同梱するファイルは git の追跡情報から決める。作業ツリーの外では作れない。
if ! git -C "$repo_root" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "git の作業ツリーではないため、配布用アーカイブを作れません: $repo_root" >&2
  exit 1
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

# 追跡されているファイルだけを複製する。作業ツリーに落ちている未追跡の
# ファイルやディレクトリーが配布物へ混ざるのを防ぐため。
while IFS= read -r -d '' file; do
  mkdir -p "$package_root/$(dirname "$file")"
  cp "$repo_root/$file" "$package_root/$file"
done < <(git -C "$repo_root" ls-files -z -- .claude-plugin skills)

skill_dir="$package_root/skills/$skill_name"

# 受け取った人が読み替えずに済むよう、手順の <version> を実際の版に変える。
sed "s/<version>/$version/g" "$repo_root/skills/$skill_name/INSTALL.md" \
  > "$skill_dir/INSTALL.md"

# 展開した直後に読めるよう、利用者向けの 2 つをルートにも置く。リポジトリーの
# README.md は開発側の話なので配らない。
cp "$skill_dir/README.md" "$package_root/README.md"
cp "$skill_dir/INSTALL.md" "$package_root/INSTALL.md"

rm -f "$archive"
(cd "$staging" && zip -rq "$archive" "$plugin_name")

echo "作成しました: $archive"
