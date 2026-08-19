@echo off
setlocal
cd /d "%~dp0"
title Painel de Backtest B3

where py >nul 2>nul
if %errorlevel%==0 (
  py -3 scripts\realistic_backtest_control_panel.py
) else (
  python scripts\realistic_backtest_control_panel.py
)

if errorlevel 1 (
  echo.
  echo Nao foi possivel iniciar o painel. Verifique se o Python 3.11 ou superior esta instalado.
  pause
)
