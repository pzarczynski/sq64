@echo off
setlocal

where uv >nul 2>nul
if %errorlevel% neq 0 (
    echo uv not found, installing...
    powershell -ExecutionPolicy ByPass -Command "irm https://astral.sh/uv/install.ps1 | iex"
)

set "UV_EXE=%USERPROFILE%\.local\bin\uv.exe"
if exist "%UV_EXE%" (
    "%UV_EXE%" run -m sq64
) else (
    uv run -m sq64
)

endlocal