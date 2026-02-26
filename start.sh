#!/bin/bash
# ─── HR Capital — Start All Services ─────────────────────────────────────────
# Usage: ./start.sh

ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV="$ROOT/venv/bin/python"

echo ""
echo "  ██╗  ██╗██████╗      ██████╗ █████╗ ██████╗ ██╗████████╗ █████╗ ██╗"
echo "  ██║  ██║██╔══██╗    ██╔════╝██╔══██╗██╔══██╗██║╚══██╔══╝██╔══██╗██║"
echo "  ███████║██████╔╝    ██║     ███████║██████╔╝██║   ██║   ███████║██║"
echo "  ██╔══██║██╔══██╗    ██║     ██╔══██║██╔═══╝ ██║   ██║   ██╔══██║██║"
echo "  ██║  ██║██║  ██║    ╚██████╗██║  ██║██║     ██║   ██║   ██║  ██║███████╗"
echo "  ╚═╝  ╚═╝╚═╝  ╚═╝     ╚═════╝╚═╝  ╚═╝╚═╝     ╚═╝   ╚═╝   ╚═╝  ╚═╝╚══════╝"
echo ""
echo "  Starting services..."
echo ""

cleanup() {
    echo ""
    echo "  Shutting down..."
    kill $API_PID $DASH_PID 2>/dev/null
    wait $API_PID $DASH_PID 2>/dev/null
    echo "  All services stopped."
    exit 0
}
trap cleanup SIGINT SIGTERM

# 1) API Server (port 8000)
echo "  [1/2] API Server → http://localhost:8000"
cd "$ROOT/api" && $VENV main.py &
API_PID=$!

# 2) Dashboard (port 3000)
echo "  [2/2] Dashboard  → http://localhost:3000"
cd "$ROOT/dashboard" && npm run dev &
DASH_PID=$!

sleep 3
echo ""
echo "  ✅ All services running!"
echo "     API:       http://localhost:8000"
echo "     Dashboard: http://localhost:3000"
echo ""
echo "  Press Ctrl+C to stop everything."
echo ""

wait
