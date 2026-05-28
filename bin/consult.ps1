#!/usr/bin/env pwsh
#requires -Version 7.0
#
# consult.ps1 — Windows-native PowerShell port of the consilium consult adapter.
#
# Mirrors bin/consult (the bash adapter) for native Windows PowerShell / cmd,
# where bash is not available. Same agents, options, prompt assembly, dispatch
# table, and transcript logging. Cross-platform: also runs under pwsh 7+ on
# macOS/Linux.
#
# Requires PowerShell 7+ (pwsh). Unlike the bash version, the per-call timeout is
# implemented natively here — no external `timeout`/`gtimeout` is needed.

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Version  = '0.1.0'
$Prog     = 'consult'
$Agents   = @('claude', 'agy', 'opencode', 'codex')
$Preamble = 'You are a peer AI advisor consulted by another agent. Give honest, direct analysis. Advice only — do not modify, create, or delete files.'

function Get-HomeDir {
    if ($env:HOME)        { return $env:HOME }
    if ($env:USERPROFILE) { return $env:USERPROFILE }
    return (Get-Location).Path
}
$LogDir = if ($env:CONSILIUM_LOG_DIR) { $env:CONSILIUM_LOG_DIR } else { Join-Path (Get-HomeDir) '.consilium/log' }

function Write-Err  { param([string]$m) [Console]::Error.WriteLine("${Prog}: $m") }
function Write-WarnMsg { param([string]$m) [Console]::Error.WriteLine("${Prog}: warning: $m") }

function Get-UsageText {
@"
$Prog — consult another AI coding agent for a second opinion.

usage:
  $Prog <agent> [options] -- <question...>
  $Prog <agent> [options] "<question>"

agents:
  claude | agy | opencode | codex

options:
  --context FILE   inline a context file into the prompt
  --code DIR       give the advisor a working directory for code context
  --model NAME     override the model
  --continue       continue the advisor's previous session
  --raw            send the question as-is (no advisor preamble)
  --no-log         do not write a transcript
  --list           list agents and whether each is installed
  -h, --help       show this help
  --version        show version

env:
  CONSILIUM_LOG_DIR   transcript directory (default: ~/.consilium/log)
  CONSILIUM_TIMEOUT   per-call timeout in seconds (0 or unset = no timeout)
  CONSILIUM_MAX_DEPTH consultation-chain depth limit (default: 3)

examples:
  $Prog codex -- "Is a read-only sandbox enough to make a consultant safe?"
  $Prog opencode --context design.md -- "Any race conditions in this plan?"
  $Prog claude --code . -- "Spot bugs in the auth flow"
"@
}

function Show-UsageOut { Get-UsageText }
function Show-UsageErr { [Console]::Error.WriteLine((Get-UsageText)) }

function Show-List {
    foreach ($a in $Agents) {
        $cmd = Get-Command $a -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($cmd) { '  {0,-9} installed  ({1})' -f $a, $cmd.Source }
        else      { '  {0,-9} not found'        -f $a }
    }
}

# ----- argument parsing ------------------------------------------------------

$agent       = ''
$contextFile = ''
$codeDir     = ''
$model       = ''
$doContinue  = $false
$raw         = $false
$noLog       = $false
$question    = ''

$argv = @($args)
$n    = $argv.Count

if ($n -eq 0) { Show-UsageErr; exit 2 }

$i = 0
while ($i -lt $n) {
    $tok = [string]$argv[$i]
    if ($tok -eq '-h' -or $tok -eq '--help') { Show-UsageOut; exit 0 }
    elseif ($tok -eq '--version') { Write-Output "consilium $Prog $Version"; exit 0 }
    elseif ($tok -eq '--list')    { Show-List; exit 0 }
    elseif ($tok -eq '--context') { if ($i + 1 -lt $n) { $i++; $contextFile = [string]$argv[$i] } else { Write-Err 'option --context needs a value'; exit 2 } }
    elseif ($tok -like '--context=*') { $contextFile = $tok.Substring('--context='.Length) }
    elseif ($tok -eq '--code')    { if ($i + 1 -lt $n) { $i++; $codeDir = [string]$argv[$i] } else { Write-Err 'option --code needs a value'; exit 2 } }
    elseif ($tok -like '--code=*')    { $codeDir = $tok.Substring('--code='.Length) }
    elseif ($tok -eq '--model')   { if ($i + 1 -lt $n) { $i++; $model = [string]$argv[$i] } else { Write-Err 'option --model needs a value'; exit 2 } }
    elseif ($tok -like '--model=*')   { $model = $tok.Substring('--model='.Length) }
    elseif ($tok -eq '--continue') { $doContinue = $true }
    elseif ($tok -eq '--raw')      { $raw = $true }
    elseif ($tok -eq '--no-log')   { $noLog = $true }
    elseif ($tok -eq '--') {
        $i++
        $rest = @()
        while ($i -lt $n) { $rest += [string]$argv[$i]; $i++ }
        $question = ($rest -join ' ')
        break
    }
    elseif ($tok.StartsWith('-')) { Write-Err "unknown option: $tok"; Show-UsageErr; exit 2 }
    elseif ([string]::IsNullOrEmpty($agent)) { $agent = $tok }
    else {
        $rest = @()
        while ($i -lt $n) { $rest += [string]$argv[$i]; $i++ }
        $question = ($rest -join ' ')
        break
    }
    $i++
}

# ----- validation ------------------------------------------------------------

if ([string]::IsNullOrEmpty($agent))    { Write-Err 'no agent given'; Show-UsageErr; exit 2 }
if ($Agents -notcontains $agent)        { Write-Err "unknown agent: $agent (expected one of: $($Agents -join ' '))"; exit 2 }
if ([string]::IsNullOrEmpty($question)) { Write-Err 'no question given'; Show-UsageErr; exit 2 }
if ($contextFile -and -not (Test-Path -LiteralPath $contextFile -PathType Leaf))      { Write-Err "context file not found: $contextFile"; exit 2 }
if ($codeDir     -and -not (Test-Path -LiteralPath $codeDir     -PathType Container)) { Write-Err "code dir not found: $codeDir"; exit 2 }
if (-not (Get-Command $agent -CommandType Application -ErrorAction SilentlyContinue)) { Write-Err "agent '$agent' is not installed or not on PATH"; exit 127 }

# ----- recursion guard -------------------------------------------------------
# Stop A -> B -> A consultation loops from burning tokens. Each call bumps
# CONSILIUM_CALL_DEPTH in the environment the advisor inherits; abort past max.
$depth = 0
if ($env:CONSILIUM_CALL_DEPTH) { [void][int]::TryParse($env:CONSILIUM_CALL_DEPTH, [ref]$depth) }
$maxDepth = 3
if ($env:CONSILIUM_MAX_DEPTH) { $parsedMax = 0; if ([int]::TryParse($env:CONSILIUM_MAX_DEPTH, [ref]$parsedMax)) { $maxDepth = $parsedMax } }
if ($depth -ge $maxDepth) {
    Write-Err "consultation depth limit reached (depth=$depth, max=$maxDepth); aborting to prevent a consult loop"
    exit 3
}
$env:CONSILIUM_CALL_DEPTH = ($depth + 1)

# ----- prompt assembly -------------------------------------------------------

if ($raw) {
    $prompt = $question
} else {
    $prompt = $Preamble
    if ($contextFile) {
        $ctx = Get-Content -LiteralPath $contextFile -Raw
        $prompt = "$prompt`n`n## Context`n`n$ctx"
    }
    $prompt = "$prompt`n`n## Question`n`n$question"
}

# ----- build the agent argument list ----------------------------------------

$cmdArgs = @()
switch ($agent) {
    'claude' {
        $cmdArgs += '-p'
        if ($doContinue) { $cmdArgs += '-c' }
        if ($model)   { $cmdArgs += @('--model', $model) }
        if ($codeDir) { $cmdArgs += @('--add-dir', $codeDir) }
        $cmdArgs += $prompt
    }
    'agy' {
        $cmdArgs += '-p'
        if ($doContinue) { $cmdArgs += '-c' }
        if ($model)   { $cmdArgs += @('--model', $model) }
        if ($codeDir) { $cmdArgs += @('--add-dir', $codeDir) }
        $cmdArgs += $prompt
    }
    'opencode' {
        $cmdArgs += 'run'
        if ($doContinue) { $cmdArgs += '-c' }
        if ($model)   { $cmdArgs += @('-m', $model) }
        if ($codeDir) { Write-WarnMsg 'opencode: --code is not wired in the dispatch table; ignoring' }
        $cmdArgs += $prompt
    }
    'codex' {
        $cmdArgs += @('exec', '--sandbox', 'read-only')
        if ($doContinue) { Write-WarnMsg 'codex: --continue is not supported in exec mode; ignoring' }
        if ($model)   { $cmdArgs += @('-m', $model) }
        if ($codeDir) { $cmdArgs += @('-C', $codeDir) }
        $cmdArgs += $prompt
    }
}

# ----- timeout ---------------------------------------------------------------

$timeoutSec = 0
if ($env:CONSILIUM_TIMEOUT) {
    $parsed = 0
    if ([int]::TryParse($env:CONSILIUM_TIMEOUT, [ref]$parsed)) { $timeoutSec = $parsed }
    else { Write-WarnMsg 'CONSILIUM_TIMEOUT is not an integer; ignoring' }
}

# ----- run the agent (native subprocess, stdin guard, timeout, capture) ------

function Invoke-Agent {
    param([string]$AgentName, [string[]]$ArgList, [int]$TimeoutSec)

    $src      = (Get-Command $AgentName -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
    $fileName = $src
    $prefix   = @()
    # On Windows, npm-style shims are often .cmd/.bat — those must run via cmd.exe.
    if ($IsWindows -and ($src -match '\.(cmd|bat)$')) {
        $fileName = Join-Path $env:SystemRoot 'System32\cmd.exe'
        $prefix   = @('/c', $src)
    }

    $psi = [System.Diagnostics.ProcessStartInfo]::new()
    $psi.FileName               = $fileName
    foreach ($a in ($prefix + $ArgList)) { $psi.ArgumentList.Add([string]$a) }
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError  = $true
    $psi.RedirectStandardInput  = $true
    $psi.UseShellExecute        = $false
    # Run the advisor in OUR working directory so it shares the same cwd-scoped
    # context (e.g. tqmemory keys memory by cwd, project AGENTS.md/GEMINI.md).
    # PowerShell's $PWD is not [Environment]::CurrentDirectory, so set it explicitly.
    $psi.WorkingDirectory       = (Get-Location).Path

    $p = [System.Diagnostics.Process]::new()
    $p.StartInfo = $psi
    [void]$p.Start()
    $p.StandardInput.Close()   # stdin guard: immediate EOF, prevents TTY hangs

    $outTask = $p.StandardOutput.ReadToEndAsync()
    $errTask = $p.StandardError.ReadToEndAsync()

    $timedOut = $false
    if ($TimeoutSec -gt 0) {
        if (-not $p.WaitForExit($TimeoutSec * 1000)) {
            $timedOut = $true
            try { $p.Kill($true) } catch { try { $p.Kill() } catch {} }
            try { [void]$p.WaitForExit(5000) } catch {}
        }
    } else {
        $p.WaitForExit()
    }

    $code = if ($timedOut) { 124 } else { $p.ExitCode }
    return [pscustomobject]@{
        StdOut   = $outTask.Result
        StdErr   = $errTask.Result
        Code     = $code
        TimedOut = $timedOut
    }
}

$res = Invoke-Agent -AgentName $agent -ArgList $cmdArgs -TimeoutSec $timeoutSec

if ($res.StdOut) { [Console]::Out.Write($res.StdOut) }
if ($res.StdErr) { [Console]::Error.Write($res.StdErr) }
if ($res.TimedOut) { Write-WarnMsg "timed out after ${timeoutSec}s" }

# ----- transcript ------------------------------------------------------------

if (-not $noLog) {
    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
    $ts      = Get-Date -Format 'yyyyMMdd-HHmmss'
    $logfile = Join-Path $LogDir "$ts-$agent-$PID.md"
    $fence   = '```'
    $lines   = @(
        "# consilium consult — $agent — $ts",
        '',
        '## Prompt',
        '',
        $fence,
        $prompt,
        $fence,
        '',
        '## Answer',
        '',
        [string]$res.StdOut
    )
    Set-Content -LiteralPath $logfile -Value $lines -Encoding UTF8
    [Console]::Error.WriteLine('')
    [Console]::Error.WriteLine("[consilium] transcript: $logfile")
}

exit $res.Code
