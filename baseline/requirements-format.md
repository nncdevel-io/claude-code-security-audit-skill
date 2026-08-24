# セキュリティ要件ファイルのフォーマット仕様

`baseline/generate.md` の手順で生成し、監査スキルが入力として読み取る
ファイルの仕様。`baseline/validate_requirements.py` がこの仕様を機械的に
検証する。仕様を変えるときは検証スクリプトも同じ変更に含める。

## ファイル全体の構造

Markdown ファイル。冒頭に YAML フロントマターでバージョン情報を持つ。

```yaml
---
baseline_version: 2026-08-21-a1b2c3d4
source_url: https://code.claude.com/docs/en/security.md
retrieved_at: 2026-08-21
content_sha256: a1b2c3d4...（16進64桁）
---
```

| フィールド | 必須 | 意味 |
| --- | --- | --- |
| `baseline_version` | 必須 | `取得日-本文SHA256先頭8桁`。レポートに必ず転記する |
| `source_url` | 必須 | 要件の出典 URL |
| `retrieved_at` | 必須 | 取得日。`YYYY-MM-DD` |
| `content_sha256` | 必須 | 取得した Markdown 本文のハッシュ。16進64桁 |

`baseline_version` は `retrieved_at` と `content_sha256` から機械的に決まる。
両者と食い違う値は検証で落ちる。

## 要件エントリーの構造

要件 1 件を以下の形式で記述する。`check` の値が判定方法を決める。

```markdown
## REQ-001: ネットワーク取得コマンドの統制

- category: prompt-injection
- check: config
- target: permissions.deny または permissions.ask に Bash(curl:*) と
  Bash(wget:*) が含まれること
- rationale: Web から任意コンテンツを取得するコマンドは
  プロンプトインジェクションの主要経路のため

## REQ-002: MCP サーバーの信頼性確認

- category: mcp
- check: manual
- target: 利用中の全 MCP サーバーが自作または信頼できる提供元であること
- rationale: Anthropic は Directory 掲載審査を行うが
  個々のサーバーのセキュリティ監査はしない
```

字下げされた行は直前の項目の続きとして連結される。項目の途中で改行してよい。

## フィールド定義

| フィールド | 必須 | 意味 |
| --- | --- | --- |
| `REQ-NNN` | 必須 | 要件 ID。見出しに書く。レポートで突合キーになる |
| `category` | 必須 | 分類。値は下記の分類一覧から選ぶ |
| `check` | 必須 | `config`（設定から機械判定可能）または `manual`（人の確認が必要） |
| `target` | 必須 | 何がどうなっていれば合格か。`config` の場合は設定キーと条件 |
| `rationale` | 任意 | 要件の根拠。セキュリティドキュメントの該当記述の要約 |
| `status` | 任意 | `active`（既定）または `deprecated` |

分類一覧: `permission` / `prompt-injection` / `mcp` / `hooks` /
`credential` / `team`

## 要件 ID の安定性

要件 ID は過去のレポートとの突合キーなので、振り直してはならない。

- 既存 ID は、文言が変わっても同じ要件を指す限り維持する
- 新規要件には未使用の最大番号 + 1 を割り当てる
- 廃止された要件は削除せず `status: deprecated` を付けて残す

## 判定の対応

- `check: config` → 収集した設定 JSON と突合し OK / NG / 非該当 を判定する
- `check: manual` → **判定しない**。人が定期的に確認する性質のものなので、
  レポート末尾の「定期確認事項」に参考として列挙するだけにする
- `status: deprecated` の要件は判定せず、レポートにも出さない

`check` の使い分けが要件の質を決める。判定を人に投げる要件が増えるほど
レポートは読まれなくなるため、次を基準にする。

- 設定から決まるなら `config`。値が無いことも判定材料になる
- 環境の前提（個人利用かチーム利用か、auto mode を意図して使うか）に
  依存するだけなら `config` にする。前提は監査の開始時に人へ確認し、
  条件が成立しなければ「非該当」とする
- プラットフォームに依存するだけなら `config` にする。収集結果の
  `platform` で決まる
- 運用や教育など、人の営みそのものを問うものだけを `manual` にする

## 検証

```bash
uv run python baseline/validate_requirements.py \
  skills/security-audit/references/requirements.md
```

問題があれば標準エラーへ列挙し、終了コード 1 を返す。
