#!/usr/bin/env bash
# ============================================================
#  Extra LoRA / Model Downloads — Testbatch (8 sep 2026)
# ============================================================
# Downloadt de 3 extra modellen uit de StableDiffusionTutorials-artikel
# voor vergelijking met de huidige Q6_K 8-stappen baseline.
# ============================================================

set -euo pipefail

MODEL_DIR="${MODEL_DIR:-/home/dennis/docker/comfyui_h3/models}"
mkdir -p "$MODEL_DIR/loras"
mkdir -p "$MODEL_DIR/diffusion_models"
mkdir -p "$MODEL_DIR/model_patches"

log() { echo "[$(date +'%H:%M')] $1"; }
success() { echo "[OK] $1"; }

# ── 1. 8-step turbo LoRA (LightX2V) ───────────────────────────
FILE1="$MODEL_DIR/loras/minimax_h3_fl2v_turbo_8step_v1.0_768p_comfyui_bf16.safetensors"
if [ -f "$FILE1" ]; then
    success "8-step turbo al aanwezig: $FILE1"
else
    log "Download 8-step turbo LoRA (LightX2V)..."
    wget --show-progress -O "$FILE1" \
      'https://huggingface.co/lightx2v/Minimax-h3-Turbo/resolve/main/minimax_h3_fl2v_turbo_8step_v1.0_768p_comfyui_bf16.safetensors'
    success "8-step turbo gedownload"
fi

# ── 2. Audio-Video 20→8 NFE LoRA (Tutu) ────────────────────────
FILE2="$MODEL_DIR/loras/tutu_minimax_h3_audio_video_20to8.safetensors"
if [ -f "$FILE2" ]; then
    success "Audio-Video NFE al aanwezig: $FILE2"
else
    log "Download Audio-Video 20→8 NFE LoRA..."
    wget --show-progress -O "$FILE2" \
      'https://huggingface.co/tutututututu/Tutu-MiniMax-H3-AudioVideo-20to8-NFE-LoRA/resolve/main/minimax_h3_audio_video_acceleration_20to8_nfe_lora.safetensors' || echo "WARN: Tutu LoRA niet gevonden (404) — skip"
    if [ -f "$FILE2" ]; then
        success "Audio-Video NFE gedownload"
    else
        echo "  (Tutu LoRA niet beschikbaar — sla over)"
    fi
fi

# ── 3. Latent Upscaler (LBH-123-AI) ─────────────────────────────
# Vereist ook de custom node: zie scripts/setup_h3_custom_nodes.sh
# Bestand gaat naar models/latent_upscale_models/ (eigen subdir,
# zie https://huggingface.co/LBH-123-AI/Minimax_h3_latent_Upscaler)
mkdir -p "$MODEL_DIR/latent_upscale_models"
FILE3="$MODEL_DIR/latent_upscale_models/minimax_h3_latent_upscaler_3d_bf16.safetensors"
if [ -f "$FILE3" ]; then
    success "Latent Upscaler al aanwezig: $FILE3"
else
    log "Download Latent Upscaler (3D bf16, ~691 MB)..."
    wget --show-progress -O "$FILE3" \
      'https://huggingface.co/LBH-123-AI/Minimax_h3_latent_Upscaler/resolve/main/minimax_h3_latent_upscaler_3d_bf16.safetensors'
    success "Latent Upscaler gedownload"
fi

# ── 4. Larryvrh v4-step600-EMA turbo LoRA (10 sep 2026) ────────
# Winnaar van het turbo-LoRA-onderzoek (zie docs/lessons-learned.md,
# bevinding 15): beste checkpoint op 6-8 stappen, strength 1.0,
# scheduler simple. ~744 MB. Getest moet worden op Q4_K_M én Q6_K
# (GGUF-compatibiliteit is niet officieel bevestigd).
FILE4="$MODEL_DIR/loras/minimax_h3_turbo_v4_step600_ema.safetensors"
if [ -f "$FILE4" ]; then
    success "Larryvrh v4-step600-EMA al aanwezig: $FILE4"
else
    log "Download Larryvrh v4-step600-EMA turbo LoRA (~744 MB)..."
    wget --show-progress -O "$FILE4" \
      'https://huggingface.co/larryvrh/MiniMax-H3-Turbo-Lora/resolve/main/minimax_h3_turbo_v4_step600_ema.safetensors'
    success "Larryvrh v4-step600-EMA gedownload"
fi

# ── 5. TaoMate-H3 3-step LoRA (CZMartin22 / TaoLiveAIGC) ───────
# 3-stappen distillatie (step-3000 EMA, r=128, alpha=128, ~1,24 GB bf16).
# BELANGRIJK: alleen voor ComfyUI; vereist Euler sampler, scheduler
# simple of linear FlowMatch, CFG 1.0, strength 1.0, stappen = 3.
# Niet geschikt voor res_multistep sampler of CFG > 1.0.
FILE5="$MODEL_DIR/loras/TaoMate-H3-3step-ComfyUI.safetensors"
if [ -f "$FILE5" ]; then
    success "TaoMate 3-step al aanwezig: $FILE5"
else
    log "Download TaoMate-H3 3-step LoRA (~1,24 GB bf16)..."
    wget --show-progress -O "$FILE5" \
      'https://huggingface.co/CZMartin22/TaoMate-H3-3step-ComfyUI/resolve/main/TaoMate-H3-3step-ComfyUI.safetensors' || echo "WARN: TaoMate 3-step niet gevonden — skip"
    if [ -f "$FILE5" ]; then
        success "TaoMate 3-step gedownload"
    else
        echo "  (TaoMate 3-step niet beschikbaar — sla over)"
    fi
fi

echo ""
echo "=== Testplan ==="
echo "1) 8-step turbo: workflow -> LoraLoader (node 161) -> model: 8step-turbo, strength 1.0, scheduler 8 stappen"
echo "2) 20->8 NFE: workflow -> LoraLoader (node 161) -> model: tutu-audio-video, scheduler 8 stappen (Euler aanbevolen)"
echo "3) Latent Upscaler: custom node installeren (setup_h3_custom_nodes.sh),"
echo "   node 'Minimax H3 Latent Upscaler (3D)' tussen SamplerCustomAdvanced-uitgang"
echo "   en VAEDecode plaatsen, model kiezen, scale 2.0"
echo "4) Larryvrh v4-step600-EMA: gebruik workflows/H3-GGUF-T2V-v4turbo-test.json"
echo "   (LoRA actief op 6 stappen, simple, strength 1.0). A/B-testen tegen"
echo "   Q6_K 8-stappen-zonder-LoRA baseline; herhaal met Q4_K_M GGUF."
echo "5) TaoMate 3-step: gebruik workflows/H3-GGUF-T2V-3step-test.json"
echo "   (3 stappen, Euler sampler, scheduler simple, CFG 1.0, strength 1.0)."
echo "   Let op: CFG mag NOOIT > 1.0; res_multistep werkt niet met deze LoRA."
echo ""
echo "Baseline voor vergelijking: Q6_K, 8 stappen, geen LoRA (~230 s op B580)"
