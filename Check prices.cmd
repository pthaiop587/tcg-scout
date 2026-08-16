@echo off
REM Double-click for a day's price check.
REM
REM Refreshes raw / PSA 9 / PSA 10 for every card from sportscardspro, records
REM when each last sold and what that sale actually made, then says what moved
REM since the last check. Every run is appended to price_history.csv, so after
REM a week this is a trend and not a snapshot, and the audit is appended to
REM price-check.log so a run you were not watching still leaves an answer.
REM
REM It takes about four minutes: one page per card with a pause between,
REM because that is what asking a website sixty questions politely looks like.
REM
REM CLOSE THE WORKBOOK FIRST. It will refuse to run otherwise and say so --
REM both it and Excel would be writing the same file minutes apart, and one of
REM the two saves would win.
REM
REM Pass "auto" to skip the pause at the end. That is what a scheduled task
REM uses; a window waiting for a keypress at 8am forever is not a daily check.

cd /d "%~dp0"
echo.
echo  Card Run HQ - checking today's prices
echo  ------------------------------------------------------
echo.

python prices.py --daily
set RC=%ERRORLEVEL%

echo.
if %RC% NEQ 0 (
  echo  Something above needs fixing. The workbook was not changed.
) else (
  echo  Done. What moved is above, in price-check.log, and in price_history.csv
)
echo.

if /I "%~1"=="auto" goto :eof
pause
