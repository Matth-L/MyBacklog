@echo off
REM Lance MyBacklog sous Windows : cree un environnement virtuel si besoin,
REM installe les dependances, puis demarre l'application (ouverture auto du navigateur).
cd /d "%~dp0"

if not exist ".venv" (
    echo Creation de l'environnement virtuel...
    python -m venv .venv
)

call .venv\Scripts\activate.bat
pip install --quiet -r requirements.txt
python app.py
pause
