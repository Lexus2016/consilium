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

$Version  = '0.4.1'
$Prog     = 'consult'
$Agents   = @('claude', 'agy', 'hermes', 'opencode', 'codex')
$Preamble = 'You are a peer AI advisor consulted by another agent. Give honest, direct analysis. Advice only — do not modify, create, or delete files.'
# Used by --review. Deliberately adversarial: a reviewer told to 'assess quality'
# rubber-stamps; one told to 'find where the RESULT fails the TASK' catches real
# defects. The PASS/FAIL verdict makes the answer actionable for the hub.
$ReviewPreamble = 'You are a peer AI advisor doing an ADVERSARIAL review for another agent. You are given a TASK (the question, plus any ## Context) and a RESULT to judge (a diff or files under ## Input, and/or the working directory). Find every place the RESULT does NOT satisfy the TASK, plus bugs, missing edge cases, and weaknesses. Do not rubber-stamp; if it is fine, say so, but only after a genuine search. Be concrete: cite the exact location and explain what is wrong and why. Finish with a line ''VERDICT: PASS'' or ''VERDICT: FAIL'' followed by a short, ranked list of the most important issues. Advice only — do not modify, create, or delete files.'

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
  $Prog --panel <a,b,c> [options] -- <question...>
  <command> | $Prog <agent> [options] -- <question...>

agents:
  claude | agy | hermes | opencode | codex

options:
  --panel LIST     ask several advisors in parallel (comma-separated), each
                   independently, then print all answers back-to-back
  --context FILE   inline a context file into the prompt
  --code DIR       give the advisor a working directory for code context
  --model NAME     override the model (claude/agy/hermes/opencode/codex)
  --continue       continue the advisor's previous session
  --review         use an adversarial review preamble: judge the RESULT
                   (piped diff / --context / --code) against the TASK in the
                   question, hunt for mismatches and bugs, end with PASS/FAIL
  --raw            send the question as-is (no advisor preamble)
  --no-log         do not write a transcript
  --list           list agents and whether each is installed
  -h, --help       show this help
  --version        show version

stdin:
  if you pipe text in (e.g. ``git diff | $Prog ...``) it is added to the
  prompt under an "## Input" heading, so the advisor sees it as the material
  to review. The advisor's own stdin is closed; only the hub reads the pipe.

env:
  CONSILIUM_LOG_DIR   transcript directory (default: ~/.consilium/log)
  CONSILIUM_TIMEOUT   per-call timeout in seconds (0 or unset = no timeout)
  CONSILIUM_MAX_DEPTH consultation-chain depth limit (default: 3)
  CONSILIUM_LOG_KEEP  keep only the newest N transcripts (default: 200; 0 = all)

examples:
  $Prog codex -- "Is a read-only sandbox enough to make a consultant safe?"
  $Prog opencode --context design.md -- "Any race conditions in this plan?"
  $Prog claude --code . -- "Spot bugs in the auth flow"
  $Prog --panel agy,opencode,codex -- "Is this migration safe to run twice?"
  git diff | $Prog codex -- "Review these changes for bugs"
  git diff | $Prog --panel codex,agy --review -- "Task: add rate limiting to the login route"
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
$panel       = ''
$contextFile = ''
$codeDir     = ''
$model       = ''
$doContinue  = $false
$raw         = $false
$review      = $false
$noLog       = $false
$question    = ''

# How to re-invoke ourselves for --panel children: run THIS script with the same
# pwsh, so a panel is the exact same code path regardless of how it was launched.
$SelfExe    = [Environment]::ProcessPath
$SelfScript = $PSCommandPath

$argv = @($args)
$n    = $argv.Count

if ($n -eq 0) { Show-UsageErr; exit 2 }

# Council mode: `consult council -f FILE -q "Q"` runs the Python council instead of
# a single advisor. Intercepted before the option parser so the council's own flags
# (-f/-q) go to the council CLI, not consult. No recursion (members spawn as
# `consult agy|opencode|hermes`, never `consult council`).
if ($argv[0] -eq 'council') {
    $py = if (Get-Command python3 -ErrorAction SilentlyContinue) { 'python3' }
          elseif (Get-Command python -ErrorAction SilentlyContinue) { 'python' }
          else { $null }
    if (-not $py) { Write-Err 'council mode needs python3 (or python) on PATH'; exit 127 }
    $scriptPath = $PSCommandPath
    try {
        $li = Get-Item $scriptPath -ErrorAction Stop
        if ($li.LinkType -eq 'SymbolicLink' -and $li.Target) { $scriptPath = $li.Target }
    } catch {}
    $root = Split-Path (Split-Path $scriptPath -Parent) -Parent
    $env:PYTHONPATH = if ($env:PYTHONPATH) { "$root$([IO.Path]::PathSeparator)$($env:PYTHONPATH)" } else { $root }
    if (-not $env:COUNCIL_CONFIG) { $env:COUNCIL_CONFIG = Join-Path $root 'config/council.json' }
    $rest = if ($n -gt 1) { $argv[1..($n - 1)] } else { @() }
    & $py -m council audit @rest
    exit $LASTEXITCODE
}

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
    elseif ($tok -eq '--panel')   { if ($i + 1 -lt $n) { $i++; $panel = [string]$argv[$i] } else { Write-Err 'option --panel needs a value'; exit 2 } }
    elseif ($tok -like '--panel=*')   { $panel = $tok.Substring('--panel='.Length) }
    elseif ($tok -eq '--model')   { if ($i + 1 -lt $n) { $i++; $model = [string]$argv[$i] } else { Write-Err 'option --model needs a value'; exit 2 } }
    elseif ($tok -like '--model=*')   { $model = $tok.Substring('--model='.Length) }
    elseif ($tok -eq '--continue') { $doContinue = $true }
    elseif ($tok -eq '--raw')      { $raw = $true }
    elseif ($tok -eq '--review')   { $review = $true }
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

if ([string]::IsNullOrEmpty($question)) { Write-Err 'no question given'; Show-UsageErr; exit 2 }
if ($contextFile -and -not (Test-Path -LiteralPath $contextFile -PathType Leaf))      { Write-Err "context file not found: $contextFile"; exit 2 }
if ($codeDir     -and -not (Test-Path -LiteralPath $codeDir     -PathType Container)) { Write-Err "code dir not found: $codeDir"; exit 2 }

# $panelAgents is the resolved, validated list for --panel mode; empty otherwise.
$panelAgents = @()
if ($panel) {
    if ($agent) { Write-Err 'use either <agent> or --panel, not both'; exit 2 }
    foreach ($a in ($panel -split ',')) {
        $a = $a.Trim()
        if (-not $a) { continue }
        if ($Agents -notcontains $a) { Write-WarnMsg "panel: unknown agent '$a' (expected one of: $($Agents -join ' ')); skipping"; continue }
        if (-not (Get-Command $a -CommandType Application -ErrorAction SilentlyContinue)) { Write-WarnMsg "panel: agent '$a' is not installed or not on PATH; skipping"; continue }
        if ($panelAgents -notcontains $a) { $panelAgents += $a }
    }
    if ($panelAgents.Count -eq 0) { Write-Err "panel: no usable advisors in '$panel'"; exit 2 }
} else {
    if ([string]::IsNullOrEmpty($agent)) { Write-Err 'no agent given'; Show-UsageErr; exit 2 }
    if ($Agents -notcontains $agent)     { Write-Err "unknown agent: $agent (expected one of: $($Agents -join ' '))"; exit 2 }
    if (-not (Get-Command $agent -CommandType Application -ErrorAction SilentlyContinue)) { Write-Err "agent '$agent' is not installed or not on PATH"; exit 127 }
}

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

# ----- piped stdin -----------------------------------------------------------
# If text was piped in, read it ONCE here in the hub; it becomes review material
# in the prompt (## Input). Advisors are always started with their stdin closed,
# so the hub is the only thing that consumes the pipe. The 10s cap mirrors the
# bash -p/-f guard: a launcher that leaves stdin open but silent must not hang us.
$stdinContent = ''
if ([Console]::IsInputRedirected) {
    try {
        $readTask = [Console]::In.ReadToEndAsync()
        if ($readTask.Wait(10000)) { $stdinContent = [string]$readTask.Result }
    } catch { $stdinContent = '' }
}

# ----- panel mode: fan out to several advisors in parallel -------------------
# Each advisor is this same script re-invoked, so it reuses ALL dispatch /
# timeout / logging logic and writes its own transcript. Advisors never see each
# other's answers — independence is the point; the hub synthesizes. Children
# inherit CONSILIUM_CALL_DEPTH+1, so the depth guard still bounds onward calls.
if ($panelAgents.Count -gt 0) {
    # One effective context file for the children: optional --context plus
    # optional piped stdin, merged once (children cannot read our consumed stdin).
    $panelCtx    = ''
    $panelCtxTmp = ''
    if ($stdinContent) {
        $panelCtxTmp = [System.IO.Path]::GetTempFileName()
        $merged = ''
        if ($contextFile) { $merged = (Get-Content -LiteralPath $contextFile -Raw) + "`n" }
        $merged += $stdinContent + "`n"
        Set-Content -LiteralPath $panelCtxTmp -Value $merged -Encoding UTF8 -NoNewline
        $panelCtx = $panelCtxTmp
    } elseif ($contextFile) {
        $panelCtx = $contextFile
    }

    $loc = Get-Location
    $childWd = if ($loc.Provider.Name -eq 'FileSystem') { $loc.ProviderPath } else { [System.IO.Directory]::GetCurrentDirectory() }

    $children = @()
    foreach ($a in $panelAgents) {
        $childArgs = @('-NoProfile', '-File', $SelfScript, $a)
        if ($panelCtx)   { $childArgs += @('--context', $panelCtx) }
        if ($codeDir)    { $childArgs += @('--code', $codeDir) }
        if ($model)      { $childArgs += @('--model', $model) }
        if ($doContinue) { $childArgs += '--continue' }
        if ($raw)        { $childArgs += '--raw' }
        if ($review)     { $childArgs += '--review' }
        if ($noLog)      { $childArgs += '--no-log' }
        $childArgs += @('--', $question)

        $psi = [System.Diagnostics.ProcessStartInfo]::new()
        $psi.FileName = $SelfExe
        foreach ($ca in $childArgs) { $psi.ArgumentList.Add([string]$ca) }
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError  = $true
        $psi.RedirectStandardInput  = $true
        $psi.UseShellExecute        = $false
        $psi.WorkingDirectory       = $childWd

        $p = [System.Diagnostics.Process]::new()
        $p.StartInfo = $psi
        [void]$p.Start()
        $p.StandardInput.Close()
        $children += [pscustomobject]@{
            Agent = $a
            Proc  = $p
            Out   = $p.StandardOutput.ReadToEndAsync()
            Err   = $p.StandardError.ReadToEndAsync()
        }
    }

    $panelStatus = 0
    foreach ($c in $children) {
        $c.Proc.WaitForExit()
        if ($c.Proc.ExitCode -ne 0) { $panelStatus = 1 }
    }

    foreach ($c in $children) {
        [Console]::Out.WriteLine('')
        [Console]::Out.WriteLine("===== $($c.Agent) =====")
        [Console]::Out.WriteLine('')
        $o = [string]$c.Out.Result
        $e = [string]$c.Err.Result
        if ($o) { [Console]::Out.Write($o) }
        if ($e) { [Console]::Error.Write($e) }
    }
    [Console]::Out.WriteLine('')

    if ($panelCtxTmp) { Remove-Item -LiteralPath $panelCtxTmp -Force -ErrorAction SilentlyContinue }
    exit $panelStatus
}

# ----- prompt assembly -------------------------------------------------------

if ($raw) {
    if ($review) { Write-WarnMsg '--review has no effect with --raw (raw sends the question verbatim); ignoring --review' }
    $prompt = $question
    if ($stdinContent) { $prompt = "$prompt`n`n$stdinContent" }
} else {
    $prompt = if ($review) { $ReviewPreamble } else { $Preamble }
    if ($contextFile) {
        $ctx = Get-Content -LiteralPath $contextFile -Raw
        $prompt = "$prompt`n`n## Context`n`n$ctx"
    }
    if ($stdinContent) {
        $prompt = "$prompt`n`n## Input`n`n$stdinContent"
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
        # agy reads the prompt as the positional that IMMEDIATELY follows -p. Any
        # flag placed between -p and the prompt (e.g. --add-dir) is parsed as the
        # request itself, so every flag must precede -p and the prompt must be the
        # final token. Verified: `agy --add-dir DIR -p "..."` answers correctly,
        # while `agy -p --add-dir DIR "..."` makes agy investigate "--add-dir".
        if ($doContinue) { $cmdArgs += '-c' }
        if ($model)   { $cmdArgs += @('--model', $model) }
        if ($codeDir) { $cmdArgs += @('--add-dir', $codeDir) }
        $cmdArgs += @('-p', $prompt)
    }
    'hermes' {
        # Nous Research Hermes Agent: one-shot via `hermes chat -q "<prompt>"`.
        # All flags precede -q so the prompt is consumed as -q's value.
        $cmdArgs += 'chat'
        if ($model)   { $cmdArgs += @('--model', $model) }
        if ($doContinue) { $cmdArgs += '-c' }
        if ($codeDir) { Write-WarnMsg 'hermes: --code is not supported (no --add-dir flag); ignoring' }
        $cmdArgs += @('-q', $prompt)
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
    # Use ProviderPath (the native filesystem path) and guard against non-FileSystem
    # locations (Registry::, Cert::), whose .Path is not a valid process directory.
    $loc = Get-Location
    if ($loc.Provider.Name -eq 'FileSystem') {
        $psi.WorkingDirectory = $loc.ProviderPath
    } else {
        $psi.WorkingDirectory = [System.IO.Directory]::GetCurrentDirectory()
    }

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

    # prune old transcripts so the log directory doesn't grow forever
    $keep = 200
    if ($env:CONSILIUM_LOG_KEEP) { $parsedKeep = 0; if ([int]::TryParse($env:CONSILIUM_LOG_KEEP, [ref]$parsedKeep)) { $keep = $parsedKeep } }
    if ($keep -gt 0) {
        Get-ChildItem -LiteralPath $LogDir -Filter '*.md' -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending | Select-Object -Skip $keep |
            Remove-Item -Force -ErrorAction SilentlyContinue
    }
}

exit $res.Code
