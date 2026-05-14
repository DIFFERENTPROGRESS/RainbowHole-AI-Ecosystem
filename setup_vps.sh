#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# RainbowHole V0.4 — Full Autostart (Docker & VPS compatible)
# ═══════════════════════════════════════════════════════════════

set -euo pipefail

# ── Config ────────────────────────────────────────
APP_NAME="rainbowhole"
APP_DIR="/opt/${APP_NAME}"
VENV_DIR="${APP_DIR}/venv"
SERVICE_FILE="/etc/systemd/system/${APP_NAME}.service"
API_PORT=8000

# Colors
GREEN='\033[0;32m'
CYAN='\033[0;36m'
PURPLE='\033[0;35m'
NC='\033[0m'

log() { echo -e "${CYAN}[RainbowHole]${NC} $1"; }
ok()  { echo -e "${GREEN}[✓]${NC} $1"; }

# ── 1. System & Tools ─────────────────────────────
log "Installing System Tools..."
apt-get update -qq && apt-get install -y -qq \
    curl wget git nano zstd python3-venv > /dev/null
ok "Tools & zstd installed."

# ── 2. Ollama Setup ───────────────────────────────
if ! command -v ollama &>/dev/null; then
    log "Installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh > /dev/null
fi

# ── 3. App & Dummy-API ────────────────────────────
mkdir -p "${APP_DIR}/api" "${APP_DIR}/vault"
touch "${APP_DIR}/api/__init__.py"

cat << 'EOF' > "${APP_DIR}/api/routes.py"
from fastapi import FastAPI
app = FastAPI()
@app.get("/health")
def health_check(): return {"status": "ok", "node": "RainbowHole Autonomous Node"}
EOF

# ── 4. Python Environment ─────────────────────────
if [ ! -d "$VENV_DIR" ]; then
    log "Creating Virtual Environment..."
    python3 -m venv "$VENV_DIR"
    "$VENV_DIR/bin/pip" install --upgrade pip -q
    "$VENV_DIR/bin/pip" install fastapi uvicorn requests -q
fi

# ── 5. Der Autostart-Mechanismus ──────────────────
API_KEY_GEN=$(openssl rand -hex 12)

# Check: Sind wir in Docker?
if [ -f /.dockerenv ] || grep -q 'docker' /proc/1/cgroup; then
    log "Docker detected. Starting services in background..."
    
    # Ollama starten
    ollama serve > /var/log/ollama.log 2>&1 &
    
    # API starten
    cd "$APP_DIR"
    "$VENV_DIR/bin/python" -m uvicorn api.routes:app --host 0.0.0.0 --port "$API_PORT" > "$APP_DIR/server.log" 2>&1 &
    
    ok "Services are running in background."
else
    log "Standard VPS detected. Setting up systemd..."
    cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=RainbowHole AI Node
After=network.target
[Service]
WorkingDirectory=$APP_DIR
ExecStart=$VENV_DIR/bin/python -m uvicorn api.routes:app --host 0.0.0.0 --port $API_PORT
Restart=always
[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload && systemctl enable --now "$APP_NAME" || true
    ok "Systemd service created and started."
fi

echo -e "\n${GREEN}═══════════════════════════════════════════════════${NC}"
echo -e "  Node is ONLINE at port ${API_PORT}"
echo -e "  API-Key: ${PURPLE}${API_KEY_GEN}${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"