@echo off
REM macd_searcher scan wrapper for Windows Task Scheduler / manual runs.
REM Resolves the project root from this script's own location (%~dp0 = this
REM script's dir), so it works no matter where the repo lives. The cd is
REM required so state\ and logs\ land inside the project, not the cwd.
cd /d "%~dp0.."
if not exist "logs" mkdir "logs"

REM Real run: logs to the SQLite DB AND sends Telegram.
REM For data-only collection without sending alerts, add --dry-run:
REM     ".venv\Scripts\macd-searcher.exe" --dry-run >> "logs\scan.log" 2>&1
".venv\Scripts\macd-searcher.exe" >> "logs\scan.log" 2>&1
