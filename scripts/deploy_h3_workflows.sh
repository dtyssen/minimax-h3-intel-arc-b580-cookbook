#!/usr/bin/env bash
# ============================================================
#  Deploy H3 Workflows — kopieer naar ComfyUI sidebar-map
# ============================================================
#  Kopieert workflows uit stacks/comfyui/workflows/ naar de
#  host user/default/workflows/ map, die via compose.h3.yaml
#  bind-mount naar /llm/ComfyUI/user/default/workflows/ gaat.
#  Daarna verschijnen ze in de ComfyUI sidebar.
#
#  Usage:
#    bash scripts/deploy_h3_workflows.sh
#
#  Daarna: ComfyUI herladen (F5 of container restart niet nodig).
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$SCRIPT_DIR/../stacks/comfyui/workflows"
DST_DIR="${USER_DIR_H3:-/home/dennis/docker/comfyui_h3/user}/default/workflows"

mkdir -p "$DST_DIR"

echo "Kopieer workflows:"
echo "  van: $SRC_DIR"
echo "  naar: $DST_DIR"
echo ""

shopt -s nullglob
count=0
for f in "$SRC_DIR"/*.json; do
    name=$(basename "$f")
    cp "$f" "$DST_DIR/$name"
    echo "  [OK] $name"
    count=$((count + 1))
done

echo ""
echo "$count workflow(s) gekopieerd. Herlaad ComfyUI (F5) om ze in de sidebar te zien."
