# claude-code-security-audit-skill

Claude Code のセキュリティ設定を、公式セキュリティドキュメントから起こした
要件ファイルと突合して監査し、改善方法を出すスキル。

要件ファイルは生成物としてリポジトリーで管理し、公式ドキュメントの変更を
GitHub Actions が検知して更新のプルリクエストを作る。起動は手動。

## 構成

```text
.claude-plugin/          プラグインとマーケットプレースの定義
skills/
  README.md              利用者向けの使い方
  INSTALL.md             配布物からの導入手順
  security-audit/        ディレクトリー名が /security-audit になる
    SKILL.md             監査の手順。判定基準は持たない
    references/
      requirements.md    同梱ベースライン（生成物）
    references/
      paths.json         OS依存の設定ファイルの場所
    scripts/
      collect_config.py  設定を読み取り専用で収集する
      collect_config.ps1 同じ内容のPowerShell実装（Python不要）
baseline/                基準の生成側。配布物には含まない
  generate.md            要件化の手順書
  requirements-format.md 要件ファイルのフォーマット仕様
  fetch_security_doc.py  公式ドキュメントの取得と差分検知
  validate_requirements.py 要件ファイルの検証
  security.md            取得した原文のスナップショット
scripts/
  verify.sh              lint とテストの唯一の入口
  install.sh             スキルの配置
  package.sh             配布用アーカイブの作成
```

配布するのは `skills/security-audit/` の 1 スキルだけで、
`baseline/` は基準を作る側の道具として手元と CI に残る。

## 使い方

監査はスラッシュコマンドで明示的に起動する。自然言語では起動しない
（`disable-model-invocation: true` を指定しているため、Claude が
自動で読み込むことはない）。

```text
/security-audit
/security-audit ../other-project
/security-audit ../other-project ~/my-requirements.md
```

| 引数 | 省略時 |
| --- | --- |
| 第 1 引数: 監査対象プロジェクト | カレントディレクトリー |
| 第 2 引数: セキュリティ要件ファイル | 同梱の `references/requirements.md` |

コマンド名はスキルのディレクトリー名 `security-audit` から決まる。
プラグインとして導入した場合は `/claude-code-security-audit:security-audit`
でも起動できる。

このスキルは設定を読むだけで、書き換えはしない。修正はレポートを見て
利用者が行う。

## インストール

このリポジトリーをクローンできるなら、`scripts/install.sh` が
`skills/security-audit/` をスキルディレクトリーへ配置する。

```bash
./scripts/install.sh
```

既定の配置先は `${CLAUDE_SKILLS_DIR:-~/.claude/skills}`。

| オプション | 意味 |
| --- | --- |
| `--target <dir>` | 配置先を指定する |
| `--link` | コピーではなくシンボリックリンクを張る（開発用） |
| `--force` | 同名のスキルがあっても置き換える |

配布用アーカイブを受け取った場合の手順は `skills/INSTALL.md` にある。
ユーザースキル、プロジェクトスキル、`--add-dir` の 3 通りを、Windows と
macOS / Linux に分けて載せてある。

## 配布

配布用アーカイブを作るときは次のとおり。既定では `scripts/verify.sh` を
通してからまとめる。同梱するのは git が追跡しているファイルだけで、
作業ツリーに落ちている未追跡のファイルは含めない。

```bash
./scripts/package.sh
```

`dist/claude-code-security-audit-<version>.zip` ができる。利用者向けの
`skills/README.md` と `skills/INSTALL.md` は配置対象の外に置いてあり、
インストール先へは運ばれない。開発向けのこのファイルは配らない。
`INSTALL.md` の `<version>` は同梱時に実際の版へ置き換える。

CI でも同じものを作る。`.claude-plugin/plugin.json` の `version` と同じ名前で
`v<version>` のタグを押すと、`.github/workflows/package.yml` が
`scripts/package.sh` を実行し、アーカイブをワークフローの成果物として残す。
タグとバージョンが食い違うときは、配る前に失敗させる。

マーケットプレースはまだ公開していないため、プラグインとしての導入は
提供していない。

## ベースラインの更新

要件ファイルは手で書き換えず、次の流れで更新する。

1. `.github/workflows/baseline-update.yml` を手動起動すると
   公式ドキュメントを取得し、SHA256 をスナップショットと比較する
2. 変化があったときだけ、`baseline/generate.md` の手順に従って
   Claude が `requirements.md` を再生成する
3. `baseline/validate_requirements.py` の検証を通してから
   プルリクエストを作る

自動マージはしない。要件ファイルは判定基準そのものなので、要件の追加・
変更・廃止が妥当かを人がレビューしてからマージする。

手元で更新するときは同じ手順を手で実行する。

```bash
uv run python baseline/fetch_security_doc.py --write
# baseline/generate.md に従って requirements.md を更新する
uv run python baseline/validate_requirements.py \
  skills/security-audit/references/requirements.md
```

### 認証トークンの登録

ワークフローは API キーではなく、サブスクリプションの長期トークンで
Claude を実行する。従量課金は発生せず、利用枠を消費する。

1. `claude setup-token` を実行してトークンを発行する
2. リポジトリーのシークレットに `CLAUDE_CODE_OAUTH_TOKEN` として登録する
3. リポジトリー設定で Actions によるプルリクエスト作成を許可する

トークンは失効するので、ワークフローが認証で失敗したら再発行する。

## 開発

Python の依存とツールは uv で管理する。

```bash
uv sync
./scripts/verify.sh
```

`scripts/verify.sh` が `ruff` / `pytest` / `markdownlint-cli2` /
`shellcheck` を順に実行する唯一の入口で、CI も同じものを呼ぶ。
`markdownlint-cli2` と `shellcheck` は別途インストールしておく。

### 対応プラットフォーム

| 対象 | Windows | macOS / Linux |
| --- | --- | --- |
| 監査スキル本体 | 対応（PowerShell / Python どちらでも） | 対応 |
| プラグインとしての導入 | 対応 | 対応 |
| `scripts/*.sh`（開発・単体配置） | bash が要る（Git Bash / WSL） | 対応 |

収集スクリプトは Python 版と PowerShell 版の 2 実装があり、同じ JSON を返す。
Windows は PowerShell が標準で入っているため、Python を導入せずに監査できる。
Claude Code は PowerShell ツールを持ち、Git Bash が無い Windows では既定で
有効になる。

2 実装がずれないよう、`tests/test_collector_parity.py` が両者を実行して出力を
突き合わせる。手元では PowerShell がある場合のみ実行され、CI では
`windows-latest` 上で Windows PowerShell 5.1 も含めて検証する。

OS 依存のパスは `references/paths.json` に外出ししてあり、両実装が同じ表を
読む。上流でパスが変わったらこのファイルだけを直す。

作業計画は `task.md` にある。
