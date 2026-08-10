@echo off
set DSN_FILE="C:\Users\soyko\Documents\Pulse-main\output\flipper_killer_mk_ii_0.9.7_unrouted\board.dsn"
set SES_FILE="C:\Users\soyko\Documents\Pulse-main\output\flipper_killer_mk_ii_0.9.7_unrouted\board.ses"
set FREEROUTING="C:\Users\soyko\AppData\Local\freerouting\freerouting.exe"

echo Launching FreeRouting...
%FREEROUTING% -de %DSN_FILE% -do %SES_FILE% -mp 50
echo FreeRouting finished.
pause
