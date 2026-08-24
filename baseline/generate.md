# セキュリティ要件ファイルの生成手順

公式セキュリティドキュメントから要件エントリーを起こし、同梱ベースライン
`skills/security-audit/references/requirements.md` を更新する手順。

この手順は GitHub Actions の `baseline-update.yml` から実行される。手元で
実行する場合も同じ手順に従う。

## 前提

`baseline/fetch_security_doc.py --write` が実行済みで、
`baseline/security.md` に最新の原文が入っていること。取得と要件化を
1 回の実行で混ぜない。取得は決定的な処理、要件化は判断を伴う処理で、
再実行時の性質が違うため。

## 入力

| 入力 | 役割 |
| --- | --- |
| `baseline/security.md` | 取得した原文。要件の唯一の出典 |
| `skills/security-audit/references/requirements.md` | 現行のベースライン。要件 ID の対応付けに使う |
| `baseline/requirements-format.md` | 出力フォーマットの仕様 |
| `fetch_security_doc.py` の出力 JSON | フロントマターに転記する値 |

## 出力

`skills/security-audit/references/requirements.md` を上書きする。
他のファイルは変更しない。

## 手順

### 1. 仕様と現状を読む

`baseline/requirements-format.md` を読み、出力フォーマットを確認する。
続いて現行の `requirements.md` を読み、既存の要件 ID と内容を把握する。

### 2. 原文から要件を起こす

`baseline/security.md` を読み、要件にする記述を抜き出す。

要件にするもの:

- 利用者側の設定や運用で満たせる、具体的な統制
- 満たしているかどうかを判定できる形に書けるもの

要件にしないもの:

- Anthropic 側の実装や運用の説明（利用者が設定できないもの）
- 製品の紹介や背景説明のみの記述
- 原文に書かれていない、こちらの推測による統制

原文に無い基準を足さない。原文が曖昧で判定基準に落とせない場合は
`check: manual` にして、確認手順を `target` に書く。

### 3. 要件 ID を対応付ける

要件 ID は過去のレポートとの突合キーなので、振り直してはならない。

- **既存 ID の維持**: 現行要件と同じ統制を指す限り、文言が変わっても
  同じ ID を使う
- **新規要件**: 現行ファイルで使われている最大番号 + 1 を割り当てる。
  欠番の再利用はしない
- **廃止された要件**: 削除せず `status: deprecated` を付けて残す。
  `target` は当時の内容のまま残す

### 4. フロントマターを更新する

`fetch_security_doc.py` の出力 JSON から `baseline_version` /
`source_url` / `retrieved_at` / `content_sha256` をそのまま転記する。
値を自分で組み立て直さない。

### 5. 検証する

```bash
uv run python baseline/validate_requirements.py \
  skills/security-audit/references/requirements.md
```

終了コードが 0 になるまで直す。検証を通していないファイルを残さない。

続いて Markdown の体裁を確認する。

```bash
markdownlint-cli2 skills/security-audit/references/requirements.md
```

## してはいけないこと

- `baseline/security.md` の書き換え。原文のスナップショットであり、
  取得スクリプトだけが更新する
- 検証スクリプトを通さないままの出力
- 要件 ID の振り直しや欠番の再利用
- 原文に根拠が無い要件の追加
- 生成した要件ファイルの自動マージ。判定基準そのものなので、
  人のレビューを必ず通す
