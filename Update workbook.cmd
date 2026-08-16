@echo off
REM Double-click this after typing into Card Run HQ - Master.xlsx.
REM
REM It gives a SKU and a Category to anything you typed by hand, then rebuilds
REM the per-game tabs from Inventory. Everything it does is in refresh.py; this
REM file exists only so it is one double-click rather than three commands in
REM the right order.
REM
REM It used to rebuild a dashboard as well. That was retired on 16 Aug 2026 --
REM the workbook is the whole system now.
REM
REM The window stays open at the end on purpose -- if something goes wrong the
REM reason is the last thing printed, and a window that closes itself takes
REM that with it.

cd /d "%~dp0"
echo.
echo  Card Run HQ - tidying the workbook
echo  ---------------------------------------------------------
echo.

python refresh.py
set RC=%ERRORLEVEL%

echo.
if %RC% NEQ 0 (
  echo  Something above needs fixing. The workbook was not changed.
) else (
  echo  Done. Open Card Run HQ - Master.xlsx.
)
echo.
pause
