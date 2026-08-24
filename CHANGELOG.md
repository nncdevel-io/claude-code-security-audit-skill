# 変更履歴

このファイルの書式は [Keep a Changelog](https://keepachangelog.com/ja/1.1.0/)
に従い、バージョンは [セマンティックバージョニング](https://semver.org/lang/ja/)
に従う。

## [未リリース]

### 追加

- 収集スクリプトの PowerShell 実装。Python を導入せずに Windows で監査できる
- OS 依存パスを `references/paths.json` へ外出し
- `managed-settings.d` の断片と契約種別（`account`）の収集
- 2 実装の出力を突き合わせるパリティテストと、`windows-latest` の CI ジョブ
- `v<version>` タグの push で配布用アーカイブを作る CI ワークフロー。
  タグと `plugin.json` の `version` が一致しないときは失敗させる
- 利用者向けの `skills/security-audit/README.md` と
  `skills/security-audit/INSTALL.md`。アーカイブではルートにも複製する。
  導入手順は Windows と macOS / Linux に分けて載せ、同梱時に `<version>` を
  実際の版へ置き換える

### 修正

- Windows の managed 設定パスが v2.1.75 で廃止された `C:\ProgramData` を
  指していた。`C:\Program Files\ClaudeCode` に修正
- 取得スクリプトの User-Agent が既定のままで、取得先に 403 で拒否されていた
- `managed-mcp.json` を収集しておらず、定義済みの MCP を未定義と誤判定していた
- 収集手順で引数を省略するとスキル自身が監査対象になっていた
- `scripts/package.sh` が作業ツリーの未追跡ファイルまで配布物へ含めて
  いた。git が追跡しているファイルだけを同梱するよう変更
- 配布物にリポジトリーの `README.md`（開発手順やベースライン生成の説明）を
  含めていた。利用者向けの README に差し替え
- `collect_config.ps1` が BOM なし UTF-8 だったため、日本語版 Windows の
  Windows PowerShell 5.1 が CP932 として読み、日本語コメントが直後の改行を
  飲み込んで構文エラーになっていた。UTF-8 BOM 付きに変更
- Windows PowerShell 5.1 の CI ステップが `$LASTEXITCODE` で成否を判定して
  いた。直接呼び出した `.ps1` はこの変数を設定せず、未設定の `$null` は
  `-ne 0` が真になるため、収集が成功しても常に失敗していた。判定を削除

## [0.1.0] - 2026-08-21

### 追加

- 監査スキル `security-audit`。`/security-audit` で明示的に起動する
  コマンド専用スキルで、自然言語では起動しない。設定を読み取り専用で
  収集する `collect_config.py` と、要件との突合手順を定めた `SKILL.md`
- 公式セキュリティドキュメント（2026-08-21 取得）から起こした
  同梱ベースライン。要件 17 件
- 基準の生成側の道具。取得と差分検知の `fetch_security_doc.py`、
  要件化の手順書 `generate.md`、フォーマット仕様
  `requirements-format.md`、検証の `validate_requirements.py`
- 配置スクリプト `install.sh` と配布用アーカイブ作成の `package.sh`
- プラグインとマーケットプレースの定義
- 週次でベースラインの更新を検知しプルリクエストを作る
  `baseline-update.yml` と、lint とテストを実行する `ci.yml`

[未リリース]: https://github.com/t-izuno/claude-code-security-audit-skill/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/t-izuno/claude-code-security-audit-skill/releases/tag/v0.1.0
