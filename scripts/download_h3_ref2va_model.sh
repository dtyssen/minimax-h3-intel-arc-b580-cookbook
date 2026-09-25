#!/usr/bin/env bash
# ============================================================
#  H3 Ref2VA Denoiser Download Script (R2V / "refmod")
# ============================================================
#  Downloadt de MiniMax H3 ref2va-denoiser (Reference-to-Video)
#  als ComfyUI-compatible GGUF van vantagewithai/MiniMax-H3-comfyUI-GGUF.
#
#  Deze denoiser is het ref2va-model (`MiniMaxH3ReferenceToVideo`
#  node) dat referenties (max. 9 afbeeldingen, 3 video's, 3 audio-clips)
#  in de generatie weeft. Gebruik de bijbehorende workflow
#  stacks/comfyui/workflows/H3-GGUF-R2V.json.
#
#  XPU-optimalisatie (Kitchen): alleen Q4_K en Q6_K hebben een
#  geoptimaliseerde route op de Arc B580. Andere quants (waaronder
#  Q3_K_M) vallen terug op trage PyTorch-dequantisatie. Zie
#  docs/lessons-learned.md probleem 5.
#
#  Usage:
#    ./download_h3_ref2va_model.sh                    # Denoiser Q4_K_M + turbo LoRA
#    ./download_h3_ref2va_model.sh --quant Q6_K       # Kwaliteits-target (26,3 GB)
#    ./download_h3_ref2va_model.sh --no-lora          # Alleen denoiser, geen turbo LoRA
#    ./download_h3_ref2va_model.sh --lora-only        # Alleen de turbo LoRA downloaden
#
#  Model directory override:
#    MODEL_DIR=/pad/naar/models ./download_h3_ref2va_model.sh
# ============================================================

set -euo pipefail

# ── Configuratie ─────────────────────────────────────────────
MODEL_DIR="${MODEL_DIR:-/home/dennis/docker/comfyui_h3/models/diffusion_models}"
LORAS_DIR="${LORAS_DIR:-/home/dennis/docker/comfyui_h3/models/loras}"
HF_REPO="vantagewithai/MiniMax-H3-comfyUI-GGUF"
REPO_SUBPATH="ref2va"
DEFAULT_QUANT="Q4_K_M"
LORA_URL="https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/loras/minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors"
LORA_FILE="minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors"

QUANT="$DEFAULT_QUANT"
WITH_LORA=1
LORA_ONLY=0

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --quant) QUANT="$2"; shift ;;
        --no-lora) WITH_LORA=0 ;;
        --lora-only) LORA_ONLY=1 ;;
        -h|--help)
            echo "Gebruik: $0 [--quant <Kwant>] [--no-lora] [--lora-only]"
            echo ""
            echo "Quants (XPU-geoptimaliseerd: Q4_K, Q6_K):"
            echo "  Q4_K_M  (18,5 GB, aanbevolen start)"
            echo "  Q4_K_S  (18,5 GB)"
            echo "  Q5_K_M  (22,3 GB)"
            echo "  Q5_K_S  (22,3 GB)"
            echo "  Q6_K    (26,3 GB, kwaliteits-target)"
            echo "  Q8_0    (33,6 GB, max kwaliteit)"
            echo "  Q4_0/Q4_1/Q5_0/Q5_1  (niet-voorkeursquants)"
            echo ""
            echo "Let op: Q3_K_M (14,5 GB) bestaat, maar heeft GEEN"
            echo "XPU/Küchen-route → trage PyTorch-fallback. Vermijden."
            exit 0
            ;;
        *) echo "Onbekende optie: $1"; exit 1 ;;
    esac
    shift
done

MODEL_FILE="minimax_h3_ref2va-${QUANT}.gguf"

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

# ── Download-hulp ────────────────────────────────────────────
download_file() {
    local url="$1" target="$2"
    mkdir -p "$(dirname "$target")"
    if command -v curl &> /dev/null; then
        curl -L --progress-bar -o "$target" "$url"
    elif command -v wget &> /dev/null; then
        wget --show-progress -O "$target" "$url"
    else
        error "Geen download tool gevonden (installeer curl of wget)."
    fi
}

# ── QC-check quant ───────────────────────────────────────────
case "$QUANT" in
    Q4_K_M|Q4_K_S|Q6_K)
        : ;;
    Q5_K_M|Q5_K_S|Q8_0)
        warning "XPU-Küchen-route voor ${QUANT} is niet gegarandeerd (enkel Q4_K/Q6_K zijn geoptimaliseerd)." ;;
    Q4_0|Q4_1|Q5_0|Q5_1)
        warning "Quant ${QUANT} heeft een niet-voorkeurs Khronos/Kitchen-route; controleer de performance." ;;
    Q3_K_M)
        warning "Q3_K_M heeft GEEN XPU-route → trage PyTorch-fallback. Verbreek zo mogelijk." ;;
    *)
        error "Onbekende quant: ${QUANT} (geldig: Q4_K_M, Q4_K_S, Q5_K_M, Q5_K_S, Q6_K, Q8_0, Q4_0, Q4_1, Q5_0, Q5_1)" ;;
esac

# ── Download denoiser ────────────────────────────────────────
if [ "$LORA_ONLY" -eq 0 ]; then
    TARGET_PATH="$MODEL_DIR/$MODEL_FILE"
    URL="https://huggingface.co/${HF_REPO}/resolve/main/${REPO_SUBPATH}/${MODEL_FILE}"

    log "Model directory: $MODEL_DIR"
    mkdir -p "$MODEL_DIR"

    if [ -f "$TARGET_PATH" ]; then
        success "Modelbestand bestaat al: $TARGET_PATH"
    else
        log "Downloaden van $MODEL_FILE van Hugging Face ($HF_REPO)..."
        download_file "$URL" "$TARGET_PATH"
        success "Model succesvol gedownload naar $TARGET_PATH"
    fi
fi

# ── Download turbo LoRA (optioneel) ──────────────────────────
if [ "$WITH_LORA" -eq 1 ]; then
    LORA_PATH="$LORAS_DIR/$LORA_FILE"
    mkdir -p "$LORAS_DIR"
    if [ -f "$LORA_PATH" ]; then
        success "Turbo LoRA bestaat al: $LORA_PATH"
    else
        log "Downloaden van turbo LoRA (ref2v 4-step)..."
        download_file "$LORA_URL" "$LORA_PATH"
        success "Turbo LoRA gedownload naar $LORA_PATH"
    fi
    echo ""
    echo "Turbo gebruiken: zet 'If/Else Switch (model)' en 'If/Else Switch (Steps)' op true"
    echo "in H3-GGUF-R2V.json (4 stappen in plaats van 20)."
fi

# ── Checklist ─────────────────────────────────────────────────
echo ""
echo "=================================================="
success "Ref2VA denoiser gereed! (${QUANT})"
echo ""
echo "Actieve configuratie:"
[ "$LORA_ONLY" -eq 0 ] && echo "  Model:   $MODEL_DIR/$MODEL_FILE"
[ "$WITH_LORA" -eq 1 ] && echo "  LoRA:    $LORAS_DIR/$LORA_FILE"
echo ""
echo "Workflow: stacks/comfyui/workflows/H3-GGUF-R2V.json"
echo "  -> deploy via: bash scripts/deploy_h3_workflows.sh"
echo ""
echo "Referenties die je zelf moet aanleveren, staan in"
echo "  /home/dennis/docker/comfyui_h3/input/"
echo "(frontale A-Team-foto's, medium-shot, scherp, goed belicht)"
echo "=================================================="