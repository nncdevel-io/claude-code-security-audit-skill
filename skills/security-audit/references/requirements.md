---
baseline_version: 2026-08-21-7aba02e7
source_url: https://code.claude.com/docs/en/security.md
retrieved_at: 2026-08-21
content_sha256: 7aba02e7f539d2384954d05443e1ce3ccd4f4b99adf54937b9e623b8fdaa7d25
---

# Claude Code セキュリティ要件

公式セキュリティドキュメントから起こした要件。生成手順は
`baseline/generate.md`、フォーマット仕様は
`baseline/requirements-format.md` にある。手で編集せず、生成手順で更新する。

## REQ-001: Bash サンドボックスの有効化

- category: permission
- check: config
- target: `sandbox.enabled` が true であること
- rationale: サンドボックスはファイルシステムとネットワークを隔離し、
  権限プロンプトを減らしつつ自律実行の範囲を限定する

## REQ-002: サンドボックスによる認証情報の読み取り制限

- category: permission
- check: config
- target: `sandbox.filesystem.denyRead` に認証情報のパス
  （`~/.ssh`、クラウド認証情報、`*.pem` など）が登録されていること
- rationale: 読み取り専用 Bash コマンドは作業ディレクトリー境界の外まで
  読めるため、denyRead で読み取り範囲を絞る必要がある

## REQ-003: 作業ディレクトリー境界の拡張の妥当性

- category: permission
- check: config
- target: `permissions.additionalDirectories` が設定されていないこと。
  設定する場合は、各ディレクトリーの必要性を要件外の所見として記録すること
- rationale: 追加ディレクトリーは書き込み可能な範囲を作業フォルダーの外へ
  広げるため、必要最小限に保つ

## REQ-004: auto mode の利用方針の反映

- category: permission
- check: config
- target: auto mode を使わない方針の場合、`permissions.disableAutoMode`
  または最上位の `disableAutoMode` が `disable` に設定されていること
- rationale: auto mode では利用者の代わりに分類モデルが可否を判断するため、
  組織の方針として使わない場合は設定で無効化する

## REQ-005: 権限設定の定期的な棚卸し

- category: permission
- check: manual
- target: `/permissions` で許可ルールを定期的に確認する運用があること
- rationale: 許可ルールは追加されやすく減らされにくいため、
  定期的な棚卸しがないと権限が広がり続ける

## REQ-006: 隔離環境の利用

- category: permission
- check: manual
- target: 機微なコードを扱う場合や外部サービスへアクセスするスクリプトを
  実行する場合に、dev container や仮想マシンで隔離していること
- rationale: 隔離環境は、権限システムをすり抜けた操作の影響範囲を限定する

## REQ-007: ネットワーク取得コマンドの統制

- category: prompt-injection
- check: config
- target: `Bash(curl *)` や `Bash(wget *)` の無条件の許可ルールが
  `permissions.allow` に無いこと。完全に禁止する方針の場合は
  `permissions.deny` に登録されていること
- rationale: Web から任意のコンテンツを取得するコマンドは
  プロンプトインジェクションの主要な経路になる

## REQ-008: 未信頼コンテンツの取り扱い

- category: prompt-injection
- check: manual
- target: 提案されたコマンドと変更を承認前にレビューする運用があり、
  未信頼のコンテンツを Claude へ直接パイプしていないこと
- rationale: 対策を重ねても攻撃を完全には防げないため、
  承認前のレビューが最後の砦になる

## REQ-009: Windows における WebDAV の回避

- category: prompt-injection
- check: config
- target: Windows 以外のプラットフォームでは非該当。Windows の場合、
  WebDAV を有効にせず、
  `\\*` のような WebDAV 配下を含みうるパスへのアクセスを許可していないこと
- rationale: WebDAV 経由のリモートホストへの通信は権限システムを迂回しうる

## REQ-010: MCP サーバーの提供元の信頼性確認

- category: mcp
- check: manual
- target: 利用中の全 MCP サーバーが自作または信頼できる提供元のもので
  あること
- rationale: Anthropic は Directory 掲載時に審査するが、
  個々の MCP サーバーのセキュリティ監査や管理は行わない

## REQ-011: MCP サーバーの信頼確認の迂回禁止

- category: mcp
- check: config
- target: `enableAllProjectMcpServers` が true でないこと
- rationale: 新規 MCP サーバーは信頼確認を経るべきで、
  プロジェクト定義の一括承認はその確認を迂回する

## REQ-012: MCP サーバー定義のバージョン管理

- category: mcp
- check: config
- target: 利用する MCP サーバーが、ソース管理下の設定ファイルに定義されて
  いること。プロジェクト単位なら `.mcp.json`、利用者や組織単位なら
  `managed-mcp.json`。`~/.claude.json` の定義だけで済ませていないこと
- rationale: 許可する MCP サーバーの一覧はソース管理に載せてレビューの
  対象にする。`~/.claude.json` は Claude Code が書き換える状態ファイルで、
  定義の変更が差分に現れない

## REQ-013: 設定変更の監査

- category: hooks
- check: config
- target: `hooks` に `ConfigChange` が定義され、セッション中の設定変更を
  記録または遮断していること
- rationale: セッション中に設定が書き換われば権限方針が崩れる。
  設定を書き換えるのは人だけでなくエージェント自身でもあり、
  バージョン管理では、セッション内で元に戻された変更を検知できない

## REQ-014: 組織標準の強制

- category: team
- check: config
- target: 譲れない権限方針が managed settings
  （`managed-settings.json`）に定義されていること
- rationale: managed settings は利用者設定・プロジェクト設定から上書き
  できない。組織標準の担保だけでなく、セッション中にエージェントが
  設定を書き換えることへの防御にもなる

## REQ-015: 承認済み権限設定の共有

- category: team
- check: config
- target: プロジェクト固有に必要な権限が、プロジェクト共有設定
  `.claude/settings.json` に定義され、バージョン管理下にあること
- rationale: 利用者スコープの許可は全プロジェクトに効くため、
  未信頼のコードを含むリポジトリーでも同じ許可が有効になる。
  プロジェクト単位に置けば影響範囲を限定でき、同時に共有も可能になる

## REQ-016: 利用状況の監視

- category: team
- check: config
- target: 複数人が利用する契約（収集結果の `account.seatTier` が設定されて
  いる、または `account.organizationType` が個人向け以外）の場合、
  OpenTelemetry によるメトリクス送信が `env` に設定されていること
- rationale: 利用状況の監視は、自分以外の利用者の使われ方を把握するための
  統制である。統制対象が本人だけの契約では、監視する相手も、比較対象となる
  母数も存在しない。条件は自己申告ではなく収集した契約情報で判定する

## REQ-017: 利用者への教育

- category: team
- check: manual
- target: チームメンバーがセキュリティのベストプラクティスについて
  教育を受けていること
- rationale: 最終的な承認判断は利用者が行うため、判断の質が統制の質になる
