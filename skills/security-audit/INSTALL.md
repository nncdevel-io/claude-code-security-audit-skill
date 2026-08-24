# インストール

`claude-code-security-audit` は Claude Code のスキルとして動作します。
配布用アーカイブを展開し、中の `skills/security-audit` を Claude Code が
読み込む場所へ置いてください。

```text
claude-code-security-audit/
  INSTALL.md
  README.md
  .claude-plugin/
  skills/
    security-audit/     ← これを配置します
```

置いたディレクトリー名がそのままコマンド名になります。`security-audit`
から名前を変更すると `/security-audit` では起動しなくなりますので、
そのままでお使いください。

## 配置先を選ぶ

| 手段 | 配置先 | 使える範囲 |
| --- | --- | --- |
| ユーザースキル | `~/.claude/skills/security-audit/` | すべてのプロジェクト |
| プロジェクトスキル | `<project>/.claude/skills/security-audit/` | そのプロジェクトだけ |
| 展開した場所から読み込ませる | 任意のディレクトリー | 起動時に指定した範囲 |

ご自身の環境でいつでもお使いになる場合はユーザースキル、チームで共有して
リポジトリーへコミットする場合はプロジェクトスキルをお選びください。
試してから決めたい場合や、複数の版を切り替えたい場合は、展開した場所から
読み込ませる方法が向いています。

同じ名前のスキルがユーザースキルとプロジェクトスキルの両方にある場合は、
ユーザースキルが優先されます。

## 手順

ご自身の環境の節だけをお読みください。

### Windows

PowerShell で実行してください。

ユーザースキルとして置く場合。

```powershell
Expand-Archive claude-code-security-audit-<version>.zip -DestinationPath .
$dest = Join-Path $HOME '.claude\skills'
New-Item -ItemType Directory -Force -Path $dest | Out-Null
Copy-Item claude-code-security-audit\skills\security-audit $dest -Recurse
```

プロジェクトスキルとして置く場合。`$project` には対象のプロジェクトの
パスを指定してください。

```powershell
Expand-Archive claude-code-security-audit-<version>.zip -DestinationPath .
$dest = Join-Path $project '.claude\skills'
New-Item -ItemType Directory -Force -Path $dest | Out-Null
Copy-Item claude-code-security-audit\skills\security-audit $dest -Recurse
```

展開した場所から読み込ませる場合。

```powershell
Expand-Archive claude-code-security-audit-<version>.zip -DestinationPath .
$root = 'claude-code-security-audit'
New-Item -ItemType Directory -Force -Path "$root\.claude\skills" | Out-Null
Move-Item "$root\skills\security-audit" "$root\.claude\skills\"
claude --add-dir $root
```

更新する場合。置き換える前に古いものを削除してください。

```powershell
$dest = Join-Path $HOME '.claude\skills'
Remove-Item (Join-Path $dest 'security-audit') -Recurse -Force
Copy-Item claude-code-security-audit\skills\security-audit $dest -Recurse
```

削除する場合。

```powershell
Remove-Item (Join-Path $HOME '.claude\skills\security-audit') -Recurse -Force
```

### macOS / Linux

ユーザースキルとして置く場合。

```bash
unzip claude-code-security-audit-<version>.zip
mkdir -p ~/.claude/skills
cp -R claude-code-security-audit/skills/security-audit ~/.claude/skills/
```

プロジェクトスキルとして置く場合。`$project` には対象のプロジェクトの
パスを指定してください。

```bash
unzip claude-code-security-audit-<version>.zip
mkdir -p "$project/.claude/skills"
cp -R claude-code-security-audit/skills/security-audit \
  "$project/.claude/skills/"
```

展開した場所から読み込ませる場合。

```bash
unzip claude-code-security-audit-<version>.zip
mkdir -p claude-code-security-audit/.claude/skills
mv claude-code-security-audit/skills/security-audit \
  claude-code-security-audit/.claude/skills/
claude --add-dir claude-code-security-audit
```

更新する場合。置き換える前に古いものを削除してください。

```bash
rm -rf ~/.claude/skills/security-audit
cp -R claude-code-security-audit/skills/security-audit ~/.claude/skills/
```

削除する場合。

```bash
rm -rf ~/.claude/skills/security-audit
```

## 確認する

Claude Code を起動して次を実行してください。OS による違いはありません。

```text
/security-audit
```

Claude Code はスキルのディレクトリーを監視しているため、追加しても再起動は
不要です。ただし、そのセッションの開始時点で存在しなかった置き場所を新しく
作成した場合は、再起動してください。

起動しない場合は、次をご確認ください。

- `SKILL.md` の場所が `<配置先>/security-audit/SKILL.md` になっているか
- ディレクトリー名を `security-audit` から変更していないか
