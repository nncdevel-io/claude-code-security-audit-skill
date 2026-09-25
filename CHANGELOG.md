# 変更履歴

このファイルの書式は [Keep a Changelog](https://keepachangelog.com/ja/1.1.0/)
に従い、バージョンは [セマンティックバージョニング](https://semver.org/lang/ja/)
に従う。

## [未リリース]

## [0.2.0] - 2026-09-25

### 追加

- 要件の出典に公式のサンドボックスドキュメントを追加。既存要件の適用条件
  （どのプラットフォームで統制が成立するか）の出典として使い、ここからは
  新規要件を起こさない。基準バージョンは全出典を束ねたハッシュから決めるので、
  どちらの出典が変わっても要件の起こし直しが走る

### 変更

- 要件ファイルのフロントマターの `source_url` を `source_urls` に変更。
  複数の出典をカンマ区切りで並べる。`content_sha256` の意味も出典 1 件の
  ハッシュから全出典を束ねたハッシュに変わった
- 同梱ベースラインを 2026-09-25 取得の公式ドキュメントで更新
  （`2026-09-25-f329e73b`）。要件の追加と廃止はない。REQ-007 の根拠に、
  拒否ルールはコマンドの文字列に一致するだけで、書き方に依存しない
  通信の統制はサンドボックスのネットワーク隔離が担うことを書き足した

### 修正

- サンドボックスの要件（REQ-001 / REQ-002）に、ネイティブ Windows では
  条件が成立しないことが書かれていなかった。判定を監査の実行時の気づきに
  委ねると、同じ設定でも実行のたびに結果が変わるため、条件を要件へ明記した
- 非該当の判定規則が緩く、要件に条件の明記が無くてもプラットフォームを
  根拠に非該当にできた。target に明記がある場合だけに限定し、明記が無い
  ものは「要件外の所見」へ回すようにした。あわせて、非該当の項目には統制を
  成立させる代替手段（WSL2 での実行など）を書かせるようにした
- 取得スクリプトが、TLS を中継するプロキシの配下で証明書の検証に失敗して
  いた。Python 3.13 の既定の TLS 設定は厳格検証を有効にしており、プロキシが
  発行し直す証明書に AKI 拡張が無いと拒否する。厳格検証だけを外し、
  証明書チェーンとホスト名の検証は残した

## [0.1.0] - 2026-08-24

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
- 収集スクリプトの PowerShell 実装。Python を導入せずに Windows で監査できる
- OS 依存パスを `references/paths.json` へ外出し
- `managed-settings.d` の断片と契約種別（`account`）の収集
- 2 実装の出力を突き合わせるパリティテストと、`windows-latest` の CI ジョブ
- `v<version>` タグの push で配布用アーカイブを作る CI ワークフロー。
  タグと `plugin.json` の `version` が一致しないときは失敗させる
- 利用者向けの `skills/README.md` と `skills/INSTALL.md`。配置対象の外に
  置き、インストール先へは運ばれないようにした。導入手順は Windows と
  macOS / Linux に分けて載せ、同梱時に `<version>` を実際の版へ置き換える

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

[未リリース]: https://github.com/t-izuno/claude-code-security-audit-skill/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/t-izuno/claude-code-security-audit-skill/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/t-izuno/claude-code-security-audit-skill/releases/tag/v0.1.0
