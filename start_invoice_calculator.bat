@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1

echo ================================================
echo  Kalkulacka tisku — Printing Volume Calculator
echo ================================================
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [CHYBA] Python nenalezen. Nainstalujte Python 3.8+
    pause
    exit /b 1
)

:: Install / upgrade all dependencies
echo [INFO] Instaluji zavislosti...
python -m pip install --quiet --upgrade Flask Werkzeug reportlab python-dateutil flask-bcrypt waitress
if %errorlevel% neq 0 (
    echo [CHYBA] Instalace zavislosti selhala.
    pause
    exit /b 1
)
echo [OK] Zavislosti nainstalovany.
echo.

:: Secret key — generate once and store in .env.local so it persists across restarts
if not exist ".env.local" (
    echo [INFO] Generuji tajny klic...
    python -c "import secrets; open('.env.local','w').write('SECRET_KEY='+secrets.token_hex(32)+'\n')"
    echo [OK] Tajny klic ulozen do .env.local
)
for /f "tokens=1,* delims==" %%a in (.env.local) do (
    if "%%a"=="SECRET_KEY" set SECRET_KEY=%%b
)

:: Admin password — prompt if not set and not yet saved
if "%ADMIN_PASSWORD%"=="" (
    if not exist ".admin_pass.local" (
        echo.
        echo [NASTAVENI] Prvni spusteni — nastavte heslo pro admina.
        set /p ADMIN_PASSWORD="  Zadejte admin heslo (min. 8 znaku): "
        if "!ADMIN_PASSWORD!"=="" (
            echo [WARN] Heslo nezadano — pouzivam vychozi 'changeme'. Zmente to!
            set ADMIN_PASSWORD=changeme
        )
        echo ADMIN_PASSWORD=!ADMIN_PASSWORD!>.admin_pass.local
        echo [OK] Heslo ulozeno do .admin_pass.local
    ) else (
        for /f "tokens=1,* delims==" %%a in (.admin_pass.local) do (
            if "%%a"=="ADMIN_PASSWORD" set ADMIN_PASSWORD=%%b
        )
    )
)

:: Admin username — default to 'admin' unless overridden
if "%ADMIN_USER%"=="" set ADMIN_USER=admin

:: Port — default 5000
if "%PORT%"=="" set PORT=5000

echo.
echo [OK] Startuju server na portu %PORT%...
echo [OK] Uzivatel: %ADMIN_USER%
echo.

python app.py

echo.
echo Server zastaven.
pause
