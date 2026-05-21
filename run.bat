@echo off
title PDF Page Extractor & Splitter
echo Launching PDF Page Extractor & Splitter...
if exist "%~dp0dist\pdf_extractor.exe" (
    start "" "%~dp0dist\pdf_extractor.exe"
) else if exist "%~dp0dist\pdf_extractor\pdf_extractor.exe" (
    start "" "%~dp0dist\pdf_extractor\pdf_extractor.exe"
) else (
    echo Executable not found. Running Python script fallback...
    python "%~dp0pdf_extractor.py"
    if %errorlevel% neq 0 (
        echo.
        echo An error occurred while running the script.
        echo Please make sure Python and the required libraries (customtkinter, pypdf) are installed correctly.
        pause
    )
)
