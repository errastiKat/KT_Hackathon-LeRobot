#!/bin/bash

# ==========================================
# 1. CONFIGURACIÓN
# ==========================================
# ⚠️ ASEGÚRATE QUE ESTA KEY ES VÁLIDA
export GEMINI_API_KEY="AIzaSyBX29lNKrRmVi1P-WJfLZwyf7TiNJTAzg8"

# Configuración Pinggy
PINGGY_CMD="ssh -p 443 -R0:localhost:5000 -L4300:localhost:4300 -o StrictHostKeyChecking=no -o ServerAliveInterval=30 fNnCriCVNH6@eu.pro.pinggy.io"

# Archivo QR estático
QR_FILE="qr_access.png"
# Archivo de LOG (Aquí guardaremos el error si ocurre)
LOG_FILE="app_debug.log"

# Colores
GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

# ==========================================
# 2. LIMPIEZA
# ==========================================
cleanup() {
    echo ""
    echo -e "${RED}${BOLD}🛑 Apagando sistemas...${NC}"
    if [ ! -z "$FLASK_PID" ]; then kill $FLASK_PID 2>/dev/null; fi
    if [ ! -z "$SSH_PID" ]; then kill $SSH_PID 2>/dev/null; fi
    exit
}
trap cleanup SIGINT

# ==========================================
# 3. ARRANQUE
# ==========================================
clear
echo -e "${BOLD}🚀 Iniciando secuencia de arranque LeRobot...${NC}"
echo "-----------------------------------------"

# --- A. Arrancar Backend Flask (Con LOGGING) ---
source env/bin/activate

# > $LOG_FILE 2>&1  significa: Guarda todo lo que pase en el archivo log
python web-server/app.py > "$LOG_FILE" 2>&1 &
FLASK_PID=$!

echo -ne "Cargando núcleo: [                    ] 0%\r"
sleep 1
echo -ne "Cargando núcleo: [##########          ] 50%\r"
sleep 2

# VERIFICACIÓN DE VIDA
if ! ps -p $FLASK_PID > /dev/null; then
    echo -e "\rCargando núcleo: [####################] 100%"
    echo -e "${RED}❌ ERROR CRÍTICO: El servidor Python se cerró.${NC}"
    echo "-----------------------------------------"
    echo -e "${YELLOW}🔍 MOSTRANDO EL ERROR REAL:${NC}"
    echo "-----------------------------------------"
    # Mostramos las últimas 20 líneas del log para ver qué pasó
    cat "$LOG_FILE"
    echo "-----------------------------------------"
    exit 1
fi

echo -ne "Cargando núcleo: [####################] 100%\r"
echo ""

# --- B. Arrancar Túnel Pinggy ---
$PINGGY_CMD > /dev/null 2>&1 &
SSH_PID=$!

# --- C. Abrir QR ---
if [ -f "$QR_FILE" ]; then
    xdg-open "$QR_FILE" > /dev/null 2>&1 &
fi

# ==========================================
# 4. DASHBOARD ALINEADO
# ==========================================
clear
# Ancho total interno: 60 caracteres (+2 bordes = 62)
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║${NC}                   🤖 ${BOLD}LEROBOT SYSTEM v2.1${NC}                   ${BLUE}║${NC}"
echo -e "${BLUE}╠════════════════════════════════════════════════════════════╣${NC}"
echo -e "${BLUE}║${NC}                                                            ${BLUE}║${NC}"
echo -e "${BLUE}║${NC}  ${BOLD}ESTADO DEL SISTEMA:${NC}                                       ${BLUE}║${NC}"
# Espaciado calculado: 60 (ancho) - 21 (texto izq) - 6 (estado) = 33 espacios
echo -e "${BLUE}║${NC}  [${GREEN}✔${NC}] Webserver Flask                    ${GREEN}ONLINE${NC}             ${BLUE}║${NC}"
# Espaciado calculado: 60 - 25 - 6 = 29 espacios
echo -e "${BLUE}║${NC}  [${GREEN}✔${NC}] Voice & Vision Core                ${GREEN}ACTIVO${NC}             ${BLUE}║${NC}"
# Espaciado calculado: 60 - 18 - 7 = 35 espacios
echo -e "${BLUE}║${NC}  [${GREEN}✔${NC}] Túnel Pinggy                       ${GREEN}ESTABLE${NC}            ${BLUE}║${NC}"
echo -e "${BLUE}║${NC}                                                            ${BLUE}║${NC}"
echo -e "${BLUE}╠════════════════════════════════════════════════════════════╣${NC}"
# Espaciado calculado: 60 - 10 (label) - 31 (url) = 19 espacios
echo -e "${BLUE}║${NC}  ${CYAN}🔗 URL:${NC} https://ktlerobot.a.pinggy.link                   ${BLUE}║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BOLD}Presiona Ctrl+C para apagar.${NC}"

# Esperar proceso
wait $FLASK_PID