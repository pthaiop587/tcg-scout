@echo off
REM Double-click this after typing into Card Run HQ - Master.xlsx.
REM
REM It reads the workbook out, rebuilds card-run-hq.html around it and opens
REM the page. Everything it does is in refresh.py; this file exists only so it
REM is one double-click rather than three commands in the right order.
REM
REM The window stays open at the end on purpose -- if something goes wrong the
REM reason is the last thing printed, and a window that closes itself takes
REM that with it.

cd /d "%~dp0"
echo.
echo  Card Run HQ - refreshing the dashboard from the workbook
echo  ---------------------------------------------------------
echo.

python refresh.py --open
set RC=%ERRORLEVEL%

echo.
if %RC% NEQ 0 (
  echo  Something above needs fixing. Nothing was published.
) else (
  echo  Done.
)
echo.
pause
