@echo off
title Qdrant Vector Database
cd /d "%~dp0"
echo ====================================================
echo Starting Qdrant Vector Database on localhost:6333...
echo Web UI Dashboard: http://localhost:6333/dashboard
echo REST API:         http://localhost:6333
echo gRPC API:         localhost:6334
echo Storage folder:   %~dp0storage
echo ====================================================
qdrant.exe --config-path config/config.yaml
pause
