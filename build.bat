@echo off
echo Building Hostel Scheduler...
pyinstaller hostel_scheduler.spec --clean --noconfirm
echo.
echo Build complete. Executable in dist\hostel_scheduler\
pause
