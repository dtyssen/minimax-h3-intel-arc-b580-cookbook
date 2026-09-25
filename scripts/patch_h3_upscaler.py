#!/usr/bin/env python3
"""
Patch Comfyui_Minimax_h3_latent_Upscaler voor Intel Arc (XPU) + NestedTensor.

Twee fixes:
1. NestedTensor: H3's sampler levert een NestedTensor (video+audio gecombineerd).
   De upscaler-code verwacht een gewone torch.Tensor met .dim()/.clone().
   Fix: unbind de NestedTensor, upscale alleen de video-component, return als
   gewone tensor. De audio-tak (VAEDecodeAudio) loopt direct vanaf de sampler
   en wordt niet beïnvloed.

2. XPU: de node biedt alleen cuda/rocm/cpu. Op Intel Arc valt cuda terug naar
   cpu (traag). Fix: voeg "xpu" toe als device-optie met torch.xpu.is_available()
   check en torch.xpu.empty_cache() voor VRAM-cleanup.

Usage:
    python3 scripts/patch_h3_upscaler.py
    # of: CUSTOM_NODES_DIR_H3=/pad python3 scripts/patch_h3_upscaler.py
"""
import os
import sys

NODES_DIR = os.environ.get(
    "CUSTOM_NODES_DIR_H3",
    "/home/dennis/docker/comfyui_h3/custom_nodes/Comfyui_Minimax_h3_latent_Upscaler",
)


def patch_3d(path):
    with open(path, "r", encoding="utf-8") as f:
        code = f.read()

    applied = []

    # --- Fix 1: XPU in _resolve_device ---
    old = 'def _resolve_device(backend):\n    if backend == "cpu":\n        return torch.device("cpu")'
    new = (
        'def _resolve_device(backend):\n'
        '    if backend == "xpu":\n'
        '        if hasattr(torch, "xpu") and torch.xpu.is_available():\n'
        '            return torch.device("xpu")\n'
        '        return torch.device("cpu")\n'
        '    if backend == "cpu":\n'
        '        return torch.device("cpu")'
    )
    if old in code:
        code = code.replace(old, new)
        applied.append("XPU in _resolve_device")
    else:
        print("  WARN: _resolve_device string niet gevonden (al gepatcht?)")

    # --- Fix 2: XPU in device dropdown ---
    old = 'io.Combo.Input("device", options=["cuda", "rocm", "cpu"], default="cuda")'
    new = 'io.Combo.Input("device", options=["cuda", "rocm", "xpu", "cpu"], default="cuda")'
    if old in code:
        code = code.replace(old, new)
        applied.append("XPU in device dropdown")
    else:
        print("  WARN: device dropdown string niet gevonden")

    # --- Fix 3: NestedTensor handling in execute ---
    # NestedTensor is NOT a torch.Tensor subclass in PyTorch 2.11 (class is _NestedTensor,
    # torch.nested.NestedTensor doesn't exist as attribute). Use isinstance(torch.Tensor)
    # negation — robust across PyTorch versions.
    old = (
        '        src = latent["samples"]\n'
        '        orig_dtype = src.dtype\n'
        '        was_4d = (src.dim() == 4)'
    )
    new = (
        '        src = latent["samples"]\n'
        '        if not isinstance(src, torch.Tensor):\n'
        '            _parts = src.unbind() if hasattr(src, "unbind") else [src]\n'
        '            src = _parts[0] if len(_parts) >= 1 else src\n'
        '        orig_dtype = src.dtype\n'
        '        was_4d = (src.dim() == 4)'
    )
    if old in code:
        code = code.replace(old, new)
        applied.append("NestedTensor unbind in execute")
    else:
        # Al eerder gepatcht met oude (foutieve) isinstance check — fix die.
        old_bad = (
            '        src = latent["samples"]\n'
            '        _is_nested = hasattr(torch, "nested") and isinstance(src, torch.nested.NestedTensor)\n'
            '        if _is_nested:\n'
            '            _parts = src.unbind()\n'
            '            src = _parts[0] if len(_parts) >= 1 else src\n'
            '        orig_dtype = src.dtype\n'
            '        was_4d = (src.dim() == 4)'
        )
        if old_bad in code:
            code = code.replace(old_bad, new)
            applied.append("NestedTensor fix v2 (was foutieve isinstance)")
        else:
            print("  WARN: execute string niet gevonden (al correct gepatcht?)")

    # --- Fix 4: XPU in VRAM management + cuda/xpu check ---
    old = (
        '        if dev.type == "cuda":\n'
        '            if force_unload:\n'
        '                model.to("cpu", non_blocking=True)\n'
        '                print("[MinimaxH3-3D] \u2705 Model offloaded to CPU. VRAM released.")\n'
        '            if HAS_COMFY_MM:\n'
        '                mm.soft_empty_cache()\n'
        '            else:\n'
        '                torch.cuda.empty_cache()\n'
        '            gc.collect()'
    )
    new = (
        '        if dev.type in ("cuda", "xpu"):\n'
        '            if force_unload:\n'
        '                model.to("cpu", non_blocking=True)\n'
        '                print("[MinimaxH3-3D] Model offloaded to CPU. VRAM released.")\n'
        '            if HAS_COMFY_MM:\n'
        '                mm.soft_empty_cache()\n'
        '            else:\n'
        '                if dev.type == "cuda":\n'
        '                    torch.cuda.empty_cache()\n'
        '                elif dev.type == "xpu":\n'
        '                    torch.xpu.empty_cache()\n'
        '            gc.collect()'
    )
    if old in code:
        code = code.replace(old, new)
        applied.append("XPU in VRAM management")
    else:
        print("  WARN: VRAM management string niet gevonden")

    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    print(f"  3D node gepatcht: {', '.join(applied)}")


def patch_2d(path):
    with open(path, "r", encoding="utf-8") as f:
        code = f.read()

    applied = []

    # --- Fix 1: XPU in device dropdown ---
    old = '"device": (["cuda", "cpu"], {"default": "cuda"})'
    new = '"device": (["cuda", "xpu", "cpu"], {"default": "cuda"})'
    if old in code:
        code = code.replace(old, new)
        applied.append("XPU in device dropdown")
    else:
        print("  WARN: 2D device dropdown string niet gevonden")

    # --- Fix 2: device resolution + NestedTensor handling ---
    old = (
        '        dev = torch.device(device if torch.cuda.is_available() else "cpu")\n'
        '        model = load_model(model_name, dev, precision)\n'
        '\n'
        '        s = latent["samples"].clone()\n'
        '        orig_dtype = s.dtype\n'
    )
    new = (
        '        if device == "xpu" and hasattr(torch, "xpu") and torch.xpu.is_available():\n'
        '            dev = torch.device("xpu")\n'
        '        elif device == "cuda" and torch.cuda.is_available():\n'
        '            dev = torch.device("cuda")\n'
        '        else:\n'
        '            dev = torch.device("cpu")\n'
        '        model = load_model(model_name, dev, precision)\n'
        '\n'
        '        _src = latent["samples"]\n'
        '        if not isinstance(_src, torch.Tensor):\n'
        '            _parts = _src.unbind() if hasattr(_src, "unbind") else [_src]\n'
        '            _src = _parts[0] if len(_parts) >= 1 else _src\n'
        '        s = _src.clone()\n'
        '        orig_dtype = s.dtype\n'
        '        _was_4d = (s.dim() == 4)\n'
    )
    if old in code:
        code = code.replace(old, new)
        applied.append("device resolution + NestedTensor")
    else:
        old_bad = (
            '        _src = latent["samples"]\n'
            '        _is_nested = hasattr(torch, "nested") and isinstance(_src, torch.nested.NestedTensor)\n'
            '        if _is_nested:\n'
            '            _parts = _src.unbind()\n'
            '            _src = _parts[0] if len(_parts) >= 1 else _src\n'
            '        s = _src.clone()\n'
            '        orig_dtype = s.dtype\n'
            '        _was_4d = (s.dim() == 4)\n'
        )
        if old_bad in code:
            code = code.replace(old_bad, new)
            applied.append("2D NestedTensor fix v2 (was foutieve isinstance)")
        else:
            print("  WARN: 2D run() string niet gevonden")

    # --- Fix 3: shape check was using latent["samples"].shape ---
    old = '        if len(latent["samples"].shape) == 4:\n            out = out.squeeze(2)'
    new = '        if _was_4d:\n            out = out.squeeze(2)'
    if old in code:
        code = code.replace(old, new)
        applied.append("shape check fix")
    else:
        print("  WARN: 2D shape check string niet gevonden")

    # --- Fix 4: XPU empty_cache ---
    old = (
        '        if dev.type == "cuda":\n'
        '            torch.cuda.empty_cache()\n'
        '\n'
        '        return ({"samples": out},)'
    )
    new = (
        '        if dev.type == "cuda":\n'
        '            torch.cuda.empty_cache()\n'
        '        elif dev.type == "xpu":\n'
        '            torch.xpu.empty_cache()\n'
        '\n'
        '        return ({"samples": out},)'
    )
    if old in code:
        code = code.replace(old, new)
        applied.append("XPU empty_cache")
    else:
        print("  WARN: 2D empty_cache string niet gevonden")

    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    print(f"  2D node gepatcht: {', '.join(applied)}")


if __name__ == "__main__":
    print(f"Patching upscaler nodes in: {NODES_DIR}")
    f3d = os.path.join(NODES_DIR, "nodes", "minimax_h3_latent_upscaler_3d.py")
    f2d = os.path.join(NODES_DIR, "nodes", "minimax_h3_latent_upscaler_2d.py")

    if os.path.exists(f3d):
        patch_3d(f3d)
    else:
        print(f"  3D node niet gevonden: {f3d}")

    if os.path.exists(f2d):
        patch_2d(f2d)
    else:
        print(f"  2D node niet gevonden: {f2d}")

    print("\nKlaar. Herstart de ComfyUI container:")
    print("  docker compose -f stacks/comfyui/compose.h3.yaml up -d --force-recreate")
