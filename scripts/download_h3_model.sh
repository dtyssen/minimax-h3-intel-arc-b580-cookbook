#!/usr/bin/env bash
# ============================================================
#  H3 Denoiser GGUF Download Script
# ============================================================
#  Downloadt de MiniMax H3 fl2va-denoiser (T2V/I2V) als ComfyUI-
#  compatible GGUF van vantagewithai/MiniMax-H3-comfyUI-GGUF.
#
#  De Q6_K-quant is het kwaliteits-target (28,2 GB volgens de upstream-repo);
#  past niet volledig in 12 GB VRAM, maar AIMDO sliding-window lost dat op
#  (meer staging naar RAM = trager per stap, hogere detailkwaliteit).
#  LET OP: Q6_K is ~40% GROTER dan Q4_K_M — de eerder in dit script
#  vermelde groottes (Q4_K_M 10,64 GiB / Q6_K 15,45 GiB) waren fout.
#  GGUF-XPU heeft een geoptimaliseerde route voor Q6_K (samen met
#  Q4_0/Q4_1/Q8_0/Q4_K) — geen trage PyTorch-fallback. Zie
#  docs/ideas/minimax-h3-b580-setup.md sectie 2 en
#  docs/lessons-learned.md probleem 5.
#
#  Usage:
#    ./download_h3_model.sh                  # Download Q6_K (28,2 GB, kwaliteits-target)
#    ./download_h3_model.sh --quant Q4_K_M   # Download Q4_K_M (19,9 GB, start-config)
#    ./download_h3_model.sh --quant Q8_0     # Download Q8_0 (36 GB, max kwalit.)
#
#  Model directory override:
#    MODEL_DIR=/pad/naar/models ./download_h3_model.sh
# ============================================================

set -euo pipefail

# ── Configuratie ─────────────────────────────────────────────
MODEL_DIR="${MODEL_DIR:-/home/dennis/docker/comfyui_h3/models/diffusion_models}"
HF_REPO="vantagewithai/MiniMax-H3-comfyUI-GGUF"
SUBPATH="fl2va"
DEFAULT_QUANT="Q6_K"

QUANT="$DEFAULT_QUANT"
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --quant) QUANT="$2"; shift ;;
        -h|--help)
            echo "Gebruik: $0 [--quant <Q6_K|Q4_K_M|Q4_K_S|Q5_K_M|Q5_K_S|Q8_0|Q4_0|Q4_1|Q5_0|Q5_1|Q3_K_M>]"
            echo ""
            echo "XPU-geoptimaliseerde quants (Kitchen/XPU-route): Q4_0, Q4_1, Q8_0, Q4_K, Q6_K"
            echo "Andere quants vallen terug op trage PyTorch-dequantisatie."
            exit 0
            ;;
        *) echo "Onbekende optie: $1"; exit 1 ;;
    esac
    shift
done

MODEL_FILE="minimax_h3_fl2va-${QUANT}.gguf"

# ── Kleuren ──────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${BLUE}[$(date +'%H:%M:%S')]${NC} $1"; }
success() { echo -e "${GREEN}[✓]${NC} $1"; }
warning() { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[✗]${NC} $1"; exit 1; }

# ── Maak model directory ─────────────────────────────────────
log "Model directory: $MODEL_DIR"
mkdir -p "$MODEL_DIR"

# ── Download Model ───────────────────────────────────────────
# Volgorde: hf -> curl -> wget (i.v.m. huggingface-cli deprecation)
TARGET_PATH="$MODEL_DIR/$MODEL_FILE"
URL="https://huggingface.co/${HF_REPO}/resolve/main/${SUBPATH}/${MODEL_FILE}"

if [ -f "$TARGET_PATH" ]; then
    success "Modelbestand bestaat al: $TARGET_PATH"
else
    log "Downloaden van $MODEL_FILE van Hugging Face ($HF_REPO)..."

    if command -v hf &> /dev/null; then
        hf download "$HF_REPO" "${SUBPATH}/${MODEL_FILE}" --local-dir "$MODEL_DIR"
    elif command -v curl &> /dev/null; then
        curl -L --progress-bar -o "$TARGET_PATH" "$URL"
    elif command -v wget &> /dev/null; then
        wget --show-progress -O "$TARGET_PATH" "$URL"
    else
        error "Geen download tool gevonden (installeer hf, curl of wget)."
    fi

    success "Model succesvol gedownload naar $TARGET_PATH"
fi

# ── Checklist ─────────────────────────────────────────────────
echo ""
echo "=================================================="
success "Denoiser gereed!"
echo ""
echo "Actieve configuratie:"
echo "  Quant:       $QUANT"
echo "  Bestand:     $TARGET_PATH"
echo ""
echo "Workflow bijwerken (indien gewenst):"
echo "  In stacks/comfyui/workflows/H3-GGUF-T2V.json -> UnetLoaderGGUF node:"
echo "    widgets_values: [\"$MODEL_FILE\"]"
echo ""
echo "Herstart de stack (alle andere GPU-stacks moeten gestopt zijn):"
echo "  docker compose -f stacks/comfyui/compose.h3.yaml up -d --force-recreate"
echo "=================================================="
