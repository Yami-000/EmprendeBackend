@echo off
setlocal EnableDelayedExpansion
title Ecia - arranque

REM ===========================================================================
REM  Ecia - levanta el proyecto completo para usarlo desde Telegram
REM
REM  Arranca tres procesos, EN ESTE ORDEN, que no es arbitrario:
REM
REM    1. Ollama            motor LLM local          puerto 11434
REM    2. ai-service        pipeline RAG (FastAPI)   puerto 11400
REM    3. Backend Node      bot de Telegram          puerto 4000
REM
REM  POR QUE EL ORDEN IMPORTA: el bot consulta al RAG en el primer mensaje que
REM  recibe, y el RAG tarda ~30 s en aceptar consultas porque carga el modelo de
REM  embeddings (470 MB) al arrancar. Si el bot arranca primero, los primeros
REM  mensajes fallan con "el servicio no respondio". Este script ESPERA a que
REM  cada servicio responda antes de arrancar el siguiente.
REM
REM  ESTA VENTANA NUNCA SE CIERRA SOLA. Todas las salidas pasan por :salir, que
REM  hace pause. Si algo falla, el mensaje queda en pantalla.
REM
REM  Uso: iniciar.bat   (doble clic tambien sirve)
REM ===========================================================================

cd /d "%~dp0"
set "HUBO_AVISOS=0"
set "AVISO1="
set "AVISO2="
set "AVISO3="

echo.
echo  ==========================================================
echo    Ecia - arranque
echo  ==========================================================
echo.

REM --- 0. Requisitos -------------------------------------------------------
echo  [0/5] Comprobando requisitos...
echo.

where node >nul 2>&1
if errorlevel 1 (
  echo  [ERROR] No se encontro 'node' en el PATH.
  echo          Instala Node.js 18 o superior y volve a intentar.
  goto :salir_error
)

where npm >nul 2>&1
if errorlevel 1 (
  echo  [ERROR] No se encontro 'npm' en el PATH.
  goto :salir_error
)

where ollama >nul 2>&1
if errorlevel 1 (
  echo  [ERROR] No se encontro 'ollama' en el PATH.
  echo          Instalalo desde https://ollama.com y volve a abrir la consola.
  goto :salir_error
)

where curl >nul 2>&1
if errorlevel 1 (
  echo  [ERROR] No se encontro 'curl'. Viene con Windows 10 y 11.
  echo          Sin curl este script no puede comprobar si los servicios
  echo          levantaron, y arrancar a ciegas rompe el bot.
  goto :salir_error
)

if not exist ".env" (
  echo  [ERROR] Falta el archivo .env en la raiz del proyecto.
  echo          Necesita al menos TELEGRAM_BOT_TOKEN. Sin el, el bot no arranca.
  goto :salir_error
)

findstr /B /C:"TELEGRAM_BOT_TOKEN" ".env" >nul 2>&1
if errorlevel 1 (
  echo  [ERROR] El archivo .env existe pero no define TELEGRAM_BOT_TOKEN.
  echo          Conseguilo con @BotFather en Telegram.
  goto :salir_error
)

set "PY=%~dp0ai-service\.venv\Scripts\python.exe"
if not exist "!PY!" (
  echo  [ERROR] No existe el entorno virtual ai-service\.venv
  echo.
  echo          Crealo con:
  echo              cd ai-service
  echo              python -m venv .venv
  echo              .venv\Scripts\activate
  echo              pip install -r requirements.txt
  goto :salir_error
)

if not exist "node_modules" (
  echo  [AVISO] Falta node_modules. Instalando dependencias de Node...
  echo          Esto puede tardar varios minutos la primera vez.
  echo.
  call npm install
  if errorlevel 1 (
    echo.
    echo  [ERROR] npm install fallo. Revisa la salida de arriba.
    goto :salir_error
  )
)

echo  [OK]    node, npm, ollama, curl, .env con token, node_modules y venv.

REM --- 1. Ollama -----------------------------------------------------------
echo.
echo  [1/5] Ollama (puerto 11434)...
echo.

curl -s -o nul -m 3 http://localhost:11434/api/tags
if errorlevel 1 (
  echo  [..]    No responde. Arrancando 'ollama serve' en otra ventana...
  start "Ecia - Ollama" cmd /k ollama serve
  call :esperar "http://localhost:11434/api/tags" 30 "Ollama"
  if errorlevel 1 goto :salir_error
) else (
  echo  [OK]    Ya estaba corriendo.
)

REM El modelo tiene que estar descargado, o la primera consulta falla con un
REM error de Ollama y el bot muestra el fallback en vez de una respuesta.
ollama list | findstr /I "llama3.2" >nul 2>&1
if errorlevel 1 (
  echo  [AVISO] Falta el modelo llama3.2. Descargandolo ^(~2 GB^)...
  echo.
  ollama pull llama3.2
  if errorlevel 1 (
    echo.
    echo  [ERROR] No se pudo descargar llama3.2.
    goto :salir_error
  )
) else (
  echo  [OK]    Modelo llama3.2 disponible.
)

REM --- 2. Indice vectorial -------------------------------------------------
echo.
echo  [2/5] Indice vectorial (ChromaDB)...
echo.

REM chroma_db\ NO esta versionado, asi que tras clonar o hacer pull no existe.
REM Sin indice el RAG arranca igual pero no recupera nada, y el bot responde
REM que no tiene la informacion: un fallo silencioso perfecto.
if not exist "ai-service\chroma_db\chroma.sqlite3" (
  echo  [AVISO] El indice no existe. Construyendolo con ingest.py...
  echo          La primera vez descarga el embedder ^(~470 MB^). Paciencia.
  echo.
  pushd "%~dp0ai-service"
  "!PY!" ingest.py
  set "ING=!errorlevel!"
  popd
  if not "!ING!"=="0" (
    echo.
    echo  [ERROR] La ingesta fallo. Revisa la salida de arriba.
    goto :salir_error
  )
  echo.
  echo  [OK]    Indice construido.
) else (
  echo  [OK]    El indice existe.
  REM Si el corpus se toco despues de construir el indice, lo que el bot
  REM responde no refleja los documentos actuales. Es exactamente el tipo de
  REM desfase que no da ningun error visible, asi que se avisa.
  for /f "delims=" %%A in ('powershell -NoProfile -Command "$i=(Get-Item 'ai-service\chroma_db\chroma.sqlite3').LastWriteTime; $c=[datetime]::MinValue; foreach($f in Get-ChildItem 'ai-service\docs\sii\*.md'){if($f.LastWriteTime -gt $c){$c=$f.LastWriteTime}}; if($c -gt $i){'VIEJO'}else{'OK'}"') do set "EDAD=%%A"
  if "!EDAD!"=="VIEJO" (
    echo.
    echo  [AVISO] EL INDICE ESTA DESACTUALIZADO.
    echo          Hay documentos en ai-service\docs\sii\ mas nuevos que el indice.
    echo          El bot va a responder segun el corpus VIEJO, sin dar ningun error.
    echo.
    echo          Para reconstruirlo:
    echo              cd ai-service
    echo              .venv\Scripts\python ingest.py
    echo.
    set "HUBO_AVISOS=1"
    set "AVISO1=El indice esta desactualizado: hay .md mas nuevos que el indice."
  )
)

REM --- 3. ai-service -------------------------------------------------------
echo.
echo  [3/5] ai-service, pipeline RAG (puerto 11400)...
echo.

curl -s -o nul -m 3 http://localhost:11400/docs
if not errorlevel 1 (
  echo  [OK]    Ya estaba corriendo.
  echo.
  echo  [AVISO] Hay un ai-service previo escuchando en el 11400. Este script NO
  echo          lo reinicia, asi que si cambiaste codigo de ai-service o
  echo          reconstruiste el indice, esa instancia vieja sigue en memoria.
  echo          Cerrala y volve a correr este script.
  echo.
  set "HUBO_AVISOS=1"
  set "AVISO2=Se reuso un ai-service que ya estaba corriendo, no se reinicio."
  goto :nodo
)

REM 'start' hereda el directorio actual, asi que se entra con pushd y el
REM comando queda sin comillas anidadas, que es donde los .bat se rompen.
pushd "%~dp0ai-service"
start "Ecia - ai-service (RAG)" cmd /k .venv\Scripts\python -m uvicorn api:app --host 0.0.0.0 --port 11400
popd

echo  [..]    Arrancado. Esperando a que cargue el modelo de embeddings...
call :esperar "http://localhost:11400/docs" 90 "ai-service"
if errorlevel 1 (
  echo.
  echo  [ERROR] El RAG no respondio. Mira la ventana "Ecia - ai-service (RAG)":
  echo          lo mas comun es que falte una dependencia de Python o que el
  echo          puerto 11400 este ocupado por otro proceso.
  goto :salir_error
)

REM --- 4. Backend Node y bot de Telegram -----------------------------------
:nodo
echo.
echo  [4/5] Backend Node y bot de Telegram (puerto 4000)...
echo.

curl -s -o nul -m 3 http://localhost:4000/health
if not errorlevel 1 (
  echo  [AVISO] Ya hay algo escuchando en el puerto 4000.
  echo          Si es otra instancia del bot, DOS BOTS CON EL MISMO TOKEN se
  echo          pelean los mensajes y Telegram devuelve error 409. Cerra la
  echo          instancia vieja antes de seguir.
  echo.
  set "HUBO_AVISOS=1"
  set "AVISO3=Habia algo en el puerto 4000: cuidado con dos bots y el mismo token."
) else (
  start "Ecia - Bot de Telegram" cmd /k npm start
  call :esperar "http://localhost:4000/health" 40 "backend Node"
  if errorlevel 1 (
    echo.
    echo  [ERROR] El backend no respondio en /health.
    echo          Mira la ventana "Ecia - Bot de Telegram". Lo mas comun:
    echo            - TELEGRAM_BOT_TOKEN invalido o revocado
    echo            - la base de datos no responde ^(en development cae a SQLite^)
    goto :salir_error
  )
)

REM --- 5. Listo ------------------------------------------------------------
echo.
echo  [5/5] Todo arriba.
echo.
echo  ==========================================================
echo    Ollama ........ http://localhost:11434
echo    ai-service .... http://localhost:11400/docs
echo    Backend ....... http://localhost:4000/health
echo  ==========================================================
echo.

if "!HUBO_AVISOS!"=="1" (
  echo  ----------------------------------------------------------
  echo    AVISOS QUE CONVIENE LEER
  echo  ----------------------------------------------------------
  if defined AVISO1 echo    - !AVISO1!
  if defined AVISO2 echo    - !AVISO2!
  if defined AVISO3 echo    - !AVISO3!
  echo.
)

echo  ----------------------------------------------------------
echo    QUE ESPERAR DEL BOT
echo  ----------------------------------------------------------
echo.
echo    Abri tu bot en Telegram y escribile. Por ejemplo:
echo      "Quien inscribe la empresa en el Registro de Comercio?"
echo.
echo    - La PRIMERA respuesta tarda mas: el modelo se carga en memoria.
echo      Despues, una consulta respondida ronda los 10 segundos.
echo.
echo    - Si preguntas algo que el corpus NO cubre, el bot se ABSTIENE
echo      a proposito. NO ES UN ERROR: es el pipeline de dos pasos
echo      evitando inventar. Con el pipeline anterior esa misma
echo      pregunta se respondia mal en 34%% de los casos.
echo.
echo    - Antes de responder hay una llamada al juez que no se ve, asi
echo      que el primer caracter tarda ~7 s mas que en la version vieja.
echo.
echo  ----------------------------------------------------------
echo    PARA DETENER TODO
echo  ----------------------------------------------------------
echo.
echo    Cerra las ventanas "Ecia - ...". Esta ventana no detiene nada:
echo    solo orquesto el arranque.
echo.
goto :salir_ok

REM ===========================================================================
REM  :esperar URL INTENTOS NOMBRE
REM  Sondea la URL una vez por segundo. Existe porque 'start' devuelve el
REM  control de inmediato: sin esperar, el siguiente servicio arrancaria contra
REM  uno que todavia no acepta conexiones.
REM ===========================================================================
:esperar
set "URL=%~1"
set "MAX=%~2"
set "QUE=%~3"
set /a N=0
:esperar_loop
set /a N+=1
curl -s -o nul -m 2 "!URL!"
if not errorlevel 1 (
  echo  [OK]    %QUE% responde ^(%N% s^).
  exit /b 0
)
if !N! GEQ %MAX% (
  echo  [ERROR] %QUE% no respondio tras %MAX% segundos.
  exit /b 1
)
timeout /t 1 /nobreak >nul
goto :esperar_loop

REM ===========================================================================
REM  Salidas. TODO camino termina aca, para que la ventana nunca se cierre
REM  sola y el mensaje quede en pantalla.
REM ===========================================================================
:salir_error
echo.
echo  ==========================================================
echo    ARRANQUE INTERRUMPIDO
echo  ==========================================================
echo.
echo    Nada quedo a medio configurar: los servicios que si
echo    arrancaron siguen en sus propias ventanas.
echo.
echo    Corregi lo que dice el [ERROR] de arriba y volve a
echo    ejecutar este script.
echo.
:salir_pausa
echo  ----------------------------------------------------------
echo    Presiona una tecla para cerrar esta ventana...
echo  ----------------------------------------------------------
pause >nul
exit /b 1

:salir_ok
echo  ----------------------------------------------------------
echo    Presiona una tecla para cerrar esta ventana...
echo    (los servicios siguen corriendo en sus ventanas)
echo  ----------------------------------------------------------
pause >nul
exit /b 0
