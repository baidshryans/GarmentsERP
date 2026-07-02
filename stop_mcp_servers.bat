@echo off
REM ============================================================
REM  stop_mcp_servers.bat
REM  Stops all Django/Python MCP server processes (mcp_server.py)
REM  running from this project's backend directory.
REM ============================================================

setlocal

echo Searching for backend mcp_server.py processes...
echo.

set "FOUND="

REM Find every python process whose command line runs mcp_server.py
REM from the "Jewel India ERP\backend" path, and kill it by PID.
for /f "usebackq tokens=*" %%P in (`powershell -NoProfile -Command ^
  "Get-CimInstance Win32_Process -Filter \"Name like 'python%%'\" | Where-Object { $_.CommandLine -like '*Jewel India ERP\backend\mcp_server.py*' } | Select-Object -ExpandProperty ProcessId"`) do (
    set "FOUND=1"
    echo   Stopping PID %%P
    taskkill /PID %%P /F >nul 2>&1
)

echo.
if defined FOUND (
    echo Done. All backend MCP server processes have been stopped.
) else (
    echo No backend MCP server processes were running.
)

endlocal
pause
