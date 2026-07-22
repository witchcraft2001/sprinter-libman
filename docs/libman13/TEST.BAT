@echo off
.\cross\z80asm.exe test.asm -o TEST.EXE
if errorlevel 1 goto ERR
echo Ok!
goto END

:ERR
pause
echo ошибки компиляции...

:END
