<#
.SYNOPSIS
    Pull a consistent snapshot of the VM's production database down to this machine.

.DESCRIPTION
    Pull, not push: this desktop sits behind NAT with no inbound route, so the VM
    cannot reach it on a schedule without port-forwarding. Running the transfer from
    here reuses the outbound SSH that already works, and adds no new exposure.

    Three steps, and each one exists for a reason:

      1. Ask the VM to make a snapshot via SQLite's Online Backup API. A plain scp of
         the live DB can miss the -wal file — the scanner writes in WAL mode every 4h,
         so recent commits may not be in the main file yet. `.backup` is safe against
         a database being written to concurrently and yields one self-contained file.
      2. Download to a temp name, then move into place. The dashboard may have the
         snapshot open (MACD_SEARCHER_DB_PATH points at it); a half-transferred file
         appearing at that path would be read as a corrupt database.
      3. Verify and report freshness. The scan runs every 4h, so a latest-run older
         than that is a signal the VM's cron is unhealthy — worth knowing here rather
         than discovering it mid-analysis.

    Nothing is written on the VM except the snapshot file, which is overwritten each
    run rather than accumulating.

.PARAMETER VmHost
    SSH target: `user@host`, or an alias from ~/.ssh/config. Required, and passed in
    rather than hardcoded so this script carries no host details into the repo.

.EXAMPLE
    .\scripts\sync_prod_db.ps1 -VmHost tristan@203.0.113.10

.EXAMPLE
    # Register a daily pull at 13:00 local. See the runbook at the bottom of
    # docs/regime_consistency_analysis.md for the full Task Scheduler command.
    .\scripts\sync_prod_db.ps1 -VmHost macd-vm
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$VmHost,

    [string]$RemoteDir = '~/macd_searcher',
    [string]$LocalDb = 'state\prod_snapshot.sqlite3'
)

$ErrorActionPreference = 'Stop'

# Resolve the project root from this script's own location, so the task works no
# matter what working directory the scheduler hands us. Same trick as run_scan.cmd.
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path 'logs')) { New-Item -ItemType Directory 'logs' | Out-Null }
if (-not (Test-Path 'state')) { New-Item -ItemType Directory 'state' | Out-Null }

$log = Join-Path $root 'logs\sync_prod_db.log'
function Write-Log($msg) {
    $line = "{0}  {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg
    Write-Host $line
    Add-Content -Path $log -Value $line -Encoding utf8
}

Write-Log "=== sync starting (host=$VmHost) ==="

if (-not (Get-Command ssh -ErrorAction SilentlyContinue)) {
    Write-Log 'FAILED: ssh not on PATH. Install the Windows OpenSSH client or use Git Bash''s ssh.'
    exit 1
}

$remoteSnap = 'state/macd_searcher_snapshot.sqlite3'
$localTmp = "$LocalDb.part"

# --- 1. WAL-safe snapshot on the VM -------------------------------------------
# The program travels base64-encoded. That looks indirect, so here is why — it is
# the only form that survives two separate Windows-side hazards:
#
#   * PowerShell 5.1 STRIPS embedded double quotes when handing a string to a native
#     .exe. A `python -c "..."` argument therefore reaches the remote bash unquoted:
#     -c swallows only the first word and bash parses the rest as shell, dying on the
#     first parenthesis.
#   * Piping the program to `python -` over stdin instead trips a different wire: the
#     pipe prepends a UTF-8 BOM, and Python rejects U+FEFF as an invalid character.
#     Setting $OutputEncoding (UTF8-no-BOM, ASCII) does not remove it.
#
# Base64 is [A-Za-z0-9+/=] only: no quotes, no spaces, no shell metacharacters, and
# we control the exact bytes. Nothing downstream can reinterpret it.
$py = @"
import sqlite3
src = sqlite3.connect('state/macd_searcher.sqlite3')
dst = sqlite3.connect('$remoteSnap')
with dst:
    src.backup(dst)
src.close()
dst.close()
print('snapshot ok')
"@
# Normalise CRLF before encoding so the payload is identical whatever wrote this file.
$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes(($py -replace "`r", "")))
$remoteCmd = "cd $RemoteDir; echo $b64 | base64 -d | .venv/bin/python -"

Write-Log 'step 1/3: creating WAL-safe snapshot on the VM'
$out = & ssh $VmHost $remoteCmd 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Log "FAILED: remote snapshot exited $LASTEXITCODE"
    Write-Log "  $out"
    exit 1
}
Write-Log "  remote said: $out"

# --- 2. Download, then move into place ----------------------------------------
Write-Log 'step 2/3: downloading'
if (Test-Path $localTmp) { Remove-Item $localTmp -Force }
& scp -q "${VmHost}:$RemoteDir/$remoteSnap" $localTmp 2>&1 | ForEach-Object { Write-Log "  $_" }
if ($LASTEXITCODE -ne 0) {
    Write-Log "FAILED: scp exited $LASTEXITCODE"
    exit 1
}
if (-not (Test-Path $localTmp)) {
    Write-Log 'FAILED: scp reported success but no file arrived'
    exit 1
}

# Atomic-ish swap: the dashboard may hold the old file open, and a partially
# written DB at that path would read as corruption.
Move-Item -Path $localTmp -Destination $LocalDb -Force
$mb = [math]::Round((Get-Item $LocalDb).Length / 1MB, 1)
Write-Log "  wrote $LocalDb ($mb MB)"

# --- 3. Verify + freshness check ----------------------------------------------
Write-Log 'step 3/3: verifying'
$verify = @"
import sqlite3, datetime
c = sqlite3.connect('file:$($LocalDb -replace '\\','/')?mode=ro', uri=True)
runs, snaps, sigs = (c.execute('SELECT COUNT(*) FROM ' + t).fetchone()[0]
                    for t in ('runs', 'asset_snapshots', 'signals'))
latest = c.execute('SELECT MAX(started_at) FROM runs').fetchone()[0]
age = (datetime.datetime.now(datetime.timezone.utc)
       - datetime.datetime.fromisoformat(latest)).total_seconds() / 3600
print(f'runs={runs} snapshots={snaps} signals={sigs}')
print(f'latest run {latest} ({age:.1f}h ago)')
# The scan cron is every 4h; much older than that and the VM side is unhealthy.
print('STALE: latest run is over 8h old - check the VM cron' if age > 8 else 'freshness ok')
"@
$verifyOut = & '.venv\Scripts\python.exe' -c $verify 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Log "FAILED: snapshot did not open cleanly - the download may be truncated"
    Write-Log "  $verifyOut"
    exit 1
}
$verifyOut | ForEach-Object { Write-Log "  $_" }

Write-Log '=== sync complete ==='
exit 0
