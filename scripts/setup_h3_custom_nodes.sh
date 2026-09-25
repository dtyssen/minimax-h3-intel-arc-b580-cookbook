#!/usr/bin/env bash
# Installeer custom nodes voor de H3/SeedVR2 stacks in de host custom_nodes-map.
# De map wordt per-node bind-mounted in de containers (zie compose.h3.yaml /
# compose.seedvr2.yaml), dus installaties overleven container-recreates.
#
# Idempotent: slaat over wat al bestaat. Draaien na een git pull of bij
# het opzetten van een nieuwe server:
#
#   bash scripts/setup_h3_custom_nodes.sh
#
# Daarna de betreffende stack herstarten:
#   docker compose -f stacks/comfyui/compose.h3.yaml up -d --force-recreate
set -euo pipefail

CUSTOM_NODES_DIR="${CUSTOM_NODES_DIR_H3:-/home/dennis/docker/comfyui_h3/custom_nodes}"
mkdir -p "$CUSTOM_NODES_DIR"

# rgthree-comfy: vereist door de H3-GGUF-T2V workflow
# (Any Switch, Power Lora Loader, Fast Bypasser, Mute/Bypass Repeater, Label)
if [ -d "$CUSTOM_NODES_DIR/rgthree-comfy/.git" ]; then
  echo "rgthree-comfy al aanwezig — skip"
else
  echo "Cloning rgthree-comfy..."
  git clone --depth 1 https://github.com/rgthree/rgthree-comfy \
    "$CUSTOM_NODES_DIR/rgthree-comfy"
fi

# Comfyui_Minimax_h3_latent_Upscaler: vereist voor de Latent Upscaler-test
# (nodes "Minimax H3 Latent Upscaler (2D)/(3D)")
if [ -d "$CUSTOM_NODES_DIR/Comfyui_Minimax_h3_latent_Upscaler/.git" ]; then
  echo "Comfyui_Minimax_h3_latent_Upscaler al aanwezig — skip"
else
  echo "Cloning Comfyui_Minimax_h3_latent_Upscaler..."
  git clone --depth 1 https://github.com/LBH-123-AI/Comfyui_Minimax_h3_latent_Upscaler \
    "$CUSTOM_NODES_DIR/Comfyui_Minimax_h3_latent_Upscaler"
fi

# ComfyUI-MiniMax-H3-Turbo (Larryvrh): optioneel voor de v4-step600-EMA
# turbo-LoRA-test. De LoRA zelf werkt als gewone LoraLoaderModelOnly
# (de eval van jo-nike gebruikte vanilla ComfyUI-nodes), maar deze node
# levert de MiniMax-H3 Turbo Sampler (dual video/audio flow-schedule) en
# de Turbo LoRA-node met low_vram-switch als fallback als de gewone
# LoraLoader-route problemen geeft op GGUF/Kitchen-XPU.
if [ -d "$CUSTOM_NODES_DIR/ComfyUI-MiniMax-H3-Turbo/.git" ]; then
  echo "ComfyUI-MiniMax-H3-Turbo al aanwezig — skip"
else
  echo "Cloning ComfyUI-MiniMax-H3-Turbo..."
  git clone --depth 1 https://github.com/Larryvrh/ComfyUI-MiniMax-H3-Turbo \
    "$CUSTOM_NODES_DIR/ComfyUI-MiniMax-H3-Turbo"
fi

# Herrgotts-H3-Infinite-Continuation-Suite: native Masked AV-continuation
# (langere H3-video's uit naadloos geketende clips). Vereist ComfyUI met
# PR #15375 (v0.34.0+); onze b2-image (0.35.0) satisfies. Geen extra
# python-deps (gebruikt comfy/torch/safetensors/av — av zit al in de image).
if [ -d "$CUSTOM_NODES_DIR/Herrgotts-H3-Infinite-Continuation-Suite/.git" ]; then
  echo "Herrgotts-H3-Infinite-Continuation-Suite al aanwezig — skip"
else
  echo "Cloning Herrgotts-H3-Infinite-Continuation-Suite..."
  git clone --depth 1 https://github.com/HerrgottMargott/Herrgotts-H3-Infinite-Continuation-Suite \
    "$CUSTOM_NODES_DIR/Herrgotts-H3-Infinite-Continuation-Suite"
fi

# Patch de upscaler-nodes voor Intel Arc (XPU) + NestedTensor-ondersteuning.
# H3's sampler levert een NestedTensor (video+audio gecombineerd); de
# upstream-node-code verwacht een gewone torch.Tensor en crasht op .dim()/.clone().
# De patch voegt ook "xpu" toe als device-optie (gpu i.p.v. trage cpu-fallback).
echo "Patching upscaler nodes (XPU + NestedTensor)..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SCRIPT_DIR/patch_h3_upscaler.py" || echo "WARN: patch script faalde — handmatig uitvoeren: python3 scripts/patch_h3_upscaler.py"

echo "Klaar. Herstart de stack: docker compose -f stacks/comfyui/compose.h3.yaml up -d --force-recreate"
