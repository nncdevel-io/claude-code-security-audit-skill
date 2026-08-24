<#
.SYNOPSIS
Claude Code の設定を読み取り専用で収集し、JSON で出力する。

.DESCRIPTION
collect_config.py と同じ JSON を返す PowerShell 実装。Python が入っていない
Windows 環境でも監査できるようにするためにある。両実装の出力が一致することは
tests/test_collector_parity.py で検証する。

Windows PowerShell 5.1 でも動くよう、6.0 以降でしか使えない構文
（$IsWindows、ConvertFrom-Json -AsHashtable、3 引数の Join-Path）は使わない。

一切の書き込みを行わない。判定もしない。事実の収集のみを担う。

.PARAMETER ProjectDir
監査対象プロジェクトのパス。省略時はカレントディレクトリー。

.EXAMPLE
pwsh -NoProfile -File collect_config.ps1 C:\path\to\project
#>

[CmdletBinding()]
param(
    [string] $ProjectDir = (Get-Location).Path
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

# collect_config.py の SECURITY_KEYS と同じ順序・内容を保つ。
$SecurityKeys = @(
    'permissions', 'env', 'apiKeyHelper', 'cleanupPeriodDays',
    'disableBypassPermissionsMode', 'enableAllProjectMcpServers',
    'enabledMcpjsonServers', 'disabledMcpjsonServers', 'allowedMcpServers',
    'deniedMcpServers', 'forceLoginMethod', 'forceLoginOrgUUID', 'sandbox',
    'allowManagedHooksOnly', 'strictKnownMarketplaces', 'extraKnownMarketplaces',
    'otelHeadersHelper'
)
$ProjectStateKeys = @(
    'enabledMcpjsonServers', 'disabledMcpjsonServers',
    'enableAllProjectMcpServers', 'allowedTools'
)
$AccountKeys = @(
    'billingType', 'organizationType', 'seatTier', 'organizationRole',
    'workspaceRole', 'organizationRateLimitTier', 'userRateLimitTier'
)

$PathsFile = Join-Path (Join-Path (Split-Path $PSScriptRoot -Parent) 'references') 'paths.json'

function Get-PropertyNames {
    <# PSCustomObject と Hashtable のどちらでもキー名を返す。 #>
    param($Value)
    if ($null -eq $Value) { return @() }
    if ($Value -is [System.Collections.IDictionary]) { return @($Value.Keys) }
    if ($Value.PSObject -and $Value.PSObject.Properties) {
        return @($Value.PSObject.Properties | ForEach-Object { $_.Name })
    }
    return @()
}

function Get-PropertyValue {
    <#
    値の型をそのまま返す。配列は関数の出力境界で展開され、空配列は $null に
    なってしまうため、カンマ演算子で一段包んで展開を打ち消す。
    #>
    param($Value, [string] $Name)
    foreach ($candidate in @(Get-PropertyNames $Value)) {
        if ($candidate -eq $Name) {
            if ($Value -is [System.Collections.IDictionary]) {
                $found = $Value[$Name]
            } else {
                $found = $Value.$Name
            }
            return , $found
        }
    }
    return $null
}

function Test-Mapping {
    param($Value)
    if ($null -eq $Value) { return $false }
    if ($Value -is [string] -or $Value -is [System.Array]) { return $false }
    return ($Value -is [System.Collections.IDictionary]) -or
           ($Value -is [System.Management.Automation.PSCustomObject])
}

function Read-JsonFile {
    <# JSON を読み、path/exists/parse_ok/content/error を返す。 #>
    param([string] $Path)

    $result = [ordered]@{
        path = $Path; exists = $false; parse_ok = $null
        content = $null; error = $null
    }
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $result }

    $result.exists = $true
    try {
        $text = Get-Content -LiteralPath $Path -Raw -Encoding UTF8
        $result.content = $text | ConvertFrom-Json
        $result.parse_ok = $true
    } catch {
        $result.parse_ok = $false
        $result.error = $_.Exception.Message
    }
    return $result
}

function Read-JsonDirectory {
    <# ディレクトリー内の JSON を名前順に読む。無ければ空。 #>
    param([string] $Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Container)) { return @() }
    $files = Get-ChildItem -LiteralPath $Path -Filter '*.json' -File | Sort-Object Name
    return @($files | ForEach-Object { Read-JsonFile $_.FullName })
}

function Get-PlatformName {
    <# collect_config.py の platform.system() と同じ値を返す。 #>
    if ($PSVersionTable.PSVersion.Major -lt 6) { return 'Windows' }
    if ($IsWindows) { return 'Windows' }
    if ($IsMacOS) { return 'Darwin' }
    return 'Linux'
}

function Get-PlatformPaths {
    <# OS 依存パスを references/paths.json から引く。 #>
    $table = (Get-Content -LiteralPath $PathsFile -Raw -Encoding UTF8 | ConvertFrom-Json)
    $system = Get-PlatformName
    $entry = Get-PropertyValue (Get-PropertyValue $table 'platforms') $system
    if ($null -eq $entry) {
        throw "$system 向けのパスが $PathsFile にありません"
    }
    return $entry
}

function Get-ClaudeVersion {
    $result = [ordered]@{ available = $false; version = $null; error = $null }
    $command = Get-Command claude -ErrorAction SilentlyContinue
    if ($null -eq $command) {
        $result.error = 'claude command not found in PATH'
        return $result
    }
    try {
        $output = & claude --version 2>&1
        if ($LASTEXITCODE -ne 0) {
            $result.error = ($output | Out-String).Trim()
            return $result
        }
        $result.available = $true
        $result.version = ($output | Out-String).Trim()
    } catch {
        $result.error = $_.Exception.Message
    }
    return $result
}

function Get-SecurityKeys {
    param($Content)
    $extracted = [ordered]@{}
    if (-not (Test-Mapping $Content)) { return $extracted }
    $names = @(Get-PropertyNames $Content)
    foreach ($key in $SecurityKeys) {
        if ($names -contains $key) { $extracted[$key] = Get-PropertyValue $Content $key }
    }
    return $extracted
}

function Get-HookSummary {
    <# hooks 定義をイベント名・matcher・コマンドの一覧へ平坦化する。 #>
    param($Content)

    $summary = @()
    if (-not (Test-Mapping $Content)) { return $summary }
    $hooks = Get-PropertyValue $Content 'hooks'
    if (-not (Test-Mapping $hooks)) { return $summary }

    foreach ($event in @(Get-PropertyNames $hooks)) {
        # Get-PropertyValue はカンマ演算子で型を保つため、呼び出しを直接
        # @() で包むと二重配列になる。いったん変数へ入れてから包む。
        $entries = Get-PropertyValue $hooks $event
        foreach ($entry in @($entries)) {
            if (-not (Test-Mapping $entry)) { continue }
            $inner = Get-PropertyValue $entry 'hooks'
            if ($null -eq $inner) { continue }
            foreach ($hook in @($inner)) {
                $summary += [ordered]@{
                    event   = $event
                    matcher = Get-PropertyValue $entry 'matcher'
                    type    = Get-PropertyValue $hook 'type'
                    command = Get-PropertyValue $hook 'command'
                }
            }
        }
    }
    return $summary
}

function Get-AccountInfo {
    param($Account)
    $extracted = [ordered]@{}
    if (-not (Test-Mapping $Account)) { return $extracted }
    foreach ($key in $AccountKeys) { $extracted[$key] = Get-PropertyValue $Account $key }
    return $extracted
}

function Get-SortedKeys {
    <# 空配列は関数の戻り値で $null へ展開されるため、必ず @() に包む。 #>
    param($Value)
    $names = @(Get-PropertyNames $Value)
    if ($names.Count -eq 0) { return @() }
    return @($names | Sort-Object)
}

function Get-UserStateSummary {
    <# ~/.claude.json から監査に必要な鍵だけを抽出する。 #>
    param($UserState, [string] $ProjectPath)

    $extracted = [ordered]@{
        path = $UserState.path; exists = $UserState.exists; parse_ok = $UserState.parse_ok
    }
    if ($UserState.parse_ok -ne $true) { return $extracted }

    $content = $UserState.content
    $extracted['global_mcp_servers'] = @(Get-SortedKeys (Get-PropertyValue $content 'mcpServers'))

    $project = Get-PropertyValue (Get-PropertyValue $content 'projects') $ProjectPath
    $state = [ordered]@{}
    foreach ($key in $ProjectStateKeys) { $state[$key] = Get-PropertyValue $project $key }
    $state['mcpServers'] = @(Get-SortedKeys (Get-PropertyValue $project 'mcpServers'))
    $extracted['project_state'] = $state
    return $extracted
}

# --- 収集 ---------------------------------------------------------------

# Python 版の os.path.abspath と同じく、正規化はするがシンボリックリンクは
# 解決しない。Claude Code が記録する作業ディレクトリーの表記に合わせるため。
if ([System.IO.Path]::IsPathRooted($ProjectDir)) {
    $resolvedProject = [System.IO.Path]::GetFullPath($ProjectDir)
} else {
    $resolvedProject = [System.IO.Path]::GetFullPath((Join-Path (Get-Location).Path $ProjectDir))
}
$home_ = [Environment]::GetFolderPath('UserProfile')
$paths = Get-PlatformPaths

$claudeDir = Join-Path $resolvedProject '.claude'
$scopes = [ordered]@{
    managed = Read-JsonFile (Get-PropertyValue $paths 'managed_settings')
    user    = Read-JsonFile (Join-Path (Join-Path $home_ '.claude') 'settings.json')
    project = Read-JsonFile (Join-Path $claudeDir 'settings.json')
    local   = Read-JsonFile (Join-Path $claudeDir 'settings.local.json')
}
$userState = Read-JsonFile (Join-Path $home_ '.claude.json')

$settingsFiles = [ordered]@{}
$securityView = [ordered]@{}
$hookView = [ordered]@{}
foreach ($name in $scopes.Keys) {
    $scope = $scopes[$name]
    $settingsFiles[$name] = [ordered]@{
        path = $scope.path; exists = $scope.exists
        parse_ok = $scope.parse_ok; error = $scope.error
    }
    if ($scope.parse_ok -eq $true) {
        $securityView[$name] = Get-SecurityKeys $scope.content
        $hookView[$name] = @(Get-HookSummary $scope.content)
    }
}

$account = [ordered]@{}
if ($userState.parse_ok -eq $true) {
    $account = Get-AccountInfo (Get-PropertyValue $userState.content 'oauthAccount')
}

$output = [ordered]@{
    collected_at = (Get-Date).ToString('yyyy-MM-ddTHH:mm:sszzz')
    platform     = Get-PlatformName
    project_dir  = $resolvedProject
    claude_version = Get-ClaudeVersion
    settings_files = $settingsFiles
    security_relevant_settings = $securityView
    hooks = $hookView
    mcp_project_file = Read-JsonFile (Join-Path $resolvedProject '.mcp.json')
    managed_mcp_file = Read-JsonFile (Get-PropertyValue $paths 'managed_mcp')
    managed_settings_fragments = @(Read-JsonDirectory (Get-PropertyValue $paths 'managed_settings_dir'))
    user_state = Get-UserStateSummary $userState $resolvedProject
    account = $account
}

$output | ConvertTo-Json -Depth 32
