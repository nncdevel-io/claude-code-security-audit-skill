---
title: Claude Code セキュリティ設定監査スキルの初版構築
priority: high
created: 2026-08-21
started: 2026-08-21
completed: 2026-08-21
result: completed
owner: t-izuno
---

# TASKS

マイルストーン: M1

ゴール: Claude Code の設定をセキュリティ要件と突合するスキルを配布可能な
形で用意し、要件ファイルの更新を GitHub Actions で継続的に検知・生成できる
状態にする。

## ワークフロールール

- タスク着手時にステータスを 🚧 に更新する
- 必要な検証をエージェント単独で完遂できた場合は ✅、人の確認が残る場合は
  🧪 に更新し、未確認事項を明記する。判断がつかない場合は 🧪 に倒す
- 🧪 から ✅ への更新はユーザーのレビュー承認をもって行う
- DependsOn のタスクがすべて ✅ でないタスクには着手しない

## ステータス表記ルール

| Status | 意味 |
| --- | --- |
| ⏳ | 未着手、TODO |
| 🚧 | 作業中、IN_PROGRESS |
| 🧪 | 確認待ち、REVIEW |
| ✅ | 完了、DONE |
| 🚫 | 中止、CANCELLED |

## タスク一覧

| ID | Status | Summary | DependsOn |
| --- | --- | --- | --- |
| TASK-001 | ✅ | uvでプロジェクトを初期化し検証入口とCIを整備する | - |
| TASK-002 | ✅ | 設定収集スクリプト `collect_config.py` を移植しテストを追加する | TASK-001 |
| TASK-003 | ✅ | 取得スクリプト `fetch_security_doc.py` を実装しテストを追加する | TASK-001 |
| TASK-004 | ✅ | 要件ファイルの検証スクリプトとフォーマット仕様を作成する | TASK-001 |
| TASK-005 | ✅ | 要件化手順書 `baseline/generate.md` を作成する | TASK-004 |
| TASK-006 | ✅ | 監査スキルの `SKILL.md` を作成し構造テストを追加する | TASK-002,TASK-004 |
| TASK-007 | ✅ | 初版ベースライン `requirements.md` を生成し検証を通す | TASK-003,TASK-005 |
| TASK-008 | ✅ | スキル配置用の `install.sh` を作成しテストを追加する | TASK-006 |
| TASK-009 | ✅ | プラグイン定義と `package.sh` を作成しテストを追加する | TASK-006 |
| TASK-010 | ✅ | 自動更新ワークフロー `baseline-update.yml` を作成する | TASK-007 |
| TASK-011 | ✅ | `README.md` と `CHANGELOG.md` を整備する | TASK-008,TASK-009,TASK-010 |

## タスク詳細

### TASK-001

- 補足: 対象は `pyproject.toml`、`uv.lock`、`.python-version`、
  `.markdownlint-cli2.jsonc`、`.gitignore`、`scripts/verify.sh`、
  `.github/workflows/ci.yml`
- 注意: Pythonの依存とツールはuvで管理し、`ruff` と `pytest` は
  `uv run` 経由で実行する。CIは `astral-sh/setup-uv` を使う
- 注意: `scripts/verify.sh` は `ruff`、`pytest`、`markdownlint-cli2`、
  `shellcheck` を順に実行する唯一の入口とし、CIも同じものを呼ぶ
- 注意: `.markdownlint-cli2.jsonc` はMD013のtables・code_blocks、MD024、
  MD025の`front_matter_title`を無効化する
- 注意: `ci.yml` が呼ぶコマンドはローカルで実行確認済み。GitHub 上での
  実行のみ未確認（プッシュが必要）

### TASK-002

- 補足: 配置先は `skills/security-audit/scripts/`
- 注意: 書き込みが発生しないことをテストで確認する
- 注意: `verify.sh` のpytest終了コード5の許容をこのタスクで外す

### TASK-003

- 補足: 取得、SHA256計算、スナップショット `baseline/security.md` との
  差分判定を担う
- 注意: 標準ライブラリのみで実装し、通信はテストでモックする

### TASK-004

- 補足: `baseline/validate_requirements.py` と
  `baseline/requirements-format.md` の2点
- 注意: `baseline_version` の欠落、REQ-IDの重複、必須フィールド欠落を
  エラーとして検出する

### TASK-005

- 補足: REQ-IDの安定性ルール（既存IDは維持、新規は連番、廃止は
  `status: deprecated` を付けて残す）を明記する

### TASK-006

- 補足: `Desktop/cc-security-audit/SKILL.md` を移植元とする
- 注意: 要件ファイル未指定時は同梱ベースラインを使う。フォーマット仕様への
  参照は持たせず、検証項目をSKILL.mdに直接書く
- 注意: `disable-model-invocation: true` でコマンド起動専用にする。
  ディレクトリー名 `security-audit` がコマンド名になる

### TASK-007

- 補足: 取得から要件化までを実行し、`validate_requirements.py` を通す
- 注意: 全17件が原文の該当記述に辿れることと、同梱ベースラインの
  ハッシュがスナップショットと一致することは確認済み。要件の取捨と
  文言の妥当性のみユーザーのレビュー待ち

### TASK-008

- 補足: `--target`、`--link`、`--force` を持ち、既定の配置先は
  `~/.claude/skills`
- 注意: テストは一時ディレクトリーを配置先に指定して実行する

### TASK-009

- 補足: `.claude-plugin/plugin.json`、`.claude-plugin/marketplace.json`、
  `scripts/package.sh` の3点
- 注意: `package.sh` は既定で `verify.sh` を実行する。テストからの
  呼び出しが再帰しないよう `--skip-check` を用意する

### TASK-010

- 補足: 週次と手動起動で動き、差分があるときだけ `claude-code-action` を
  実行してプルリクエストを作る
- 注意: 認証はサブスクリプションの長期トークンを用いる。シークレット
  `CLAUDE_CODE_OAUTH_TOKEN` の登録はユーザー作業。自動マージはしない
- 注意: 差分検知ステップのシェル処理は定義のままテストで実行確認済み。
  Claude 実行ステップと PR 作成ステップのみ未確認（プッシュが必要）

### TASK-011

- 補足: 構成、インストール手順、パッケージ手順、ベースライン更新フロー、
  トークン登録手順を記載する
