@echo off
echo ========================================
echo KORUM LAB - STARTUP ORCHESTRATOR
echo ========================================

echo [1/3] Spinning up Neo4j Graph Database (Docker)...
docker-compose up -d

echo [2/3] Booting Korum Neural Engine (FastAPI Backend)...
:: Open a new terminal window for the backend
start "Korum Engine Backend" cmd /k "cd /d %~dp0 && call .\venv\Scripts\activate.bat && uvicorn api:app --host 127.0.0.1 --port 8000 --reload"

echo [3/3] Igniting Gold Noir Dashboard (Vite Frontend)...
:: Open a new terminal window for the frontend UI
start "Korum Frontend UI" cmd /k "cd /d %~dp0\korum-ui && npm run dev -- --open"

echo.
echo ========================================
echo ALL SYSTEMS GO.
echo Dashboard booting at http://localhost:5173 (opening automatically)
echo Engine running at http://127.0.0.1:8000
echo ========================================
pause
