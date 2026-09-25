# MiniMax H3 Video on an Intel Arc B580 (12 GB) — A ComfyUI Cookbook

> Run **MiniMax H3** (text-to-video, image-to-video, video-to-video,
> reference-to-video — all with native stereo audio) on a single
> **Intel Arc B580 with 12 GB VRAM**, using Intel's official
> `llm-scaler-omni` image with **DynamicVRAM (AIMDO)**, GGUF quantization
> and ComfyUI. **No NVIDIA card required.**
>
> **Verified on:** Intel Arc B580 (Xe2 Battlemage, 12 GB, 192 GB/s),
> AMD Ryzen 5 7600, 32 GB DDR5, **Ubuntu 26.04 LTS**, Docker + Compose v2,
> Intel GPU driver + Level Zero runtime.
>
> This is a hands-on cookbook from production use. Everything in the
> benchmark and "lessons learned" sections is measured or observed on that
> rig; anything that is *not* from our own testing is labelled as such.

---

## TL;DR

- H3 runs fine on a 12 GB Arc card **because** Intel's Omni image enables
  **DynamicVRAM (AIMDO)**: the ~20 GB GGUF denoiser and the 15 GB text
  encoder are staged between VRAM and RAM. Without that flag nothing loads.
- Use the **GGUF** denoiser from `vantagewithai/MiniMax-H3-comfyUI-GGUF`
  (`fl2va/minimax_h3_fl2va-Q4_K_M.gguf`) and the **safetensors** text
  encoder from `Comfy-Org/MiniMax-H3`
  (`qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors`). Unsloth's H3 GGUFs are
  formatted for stable-diffusion.cpp / llama.cpp and do **not** load in
  ComfyUI.
- **Turbo LoRA recommendation: the 4-step 768p LoRA**
  (`minimax_h3_fl2v_turbo_4step_v1.0_768p_comfyui_bf16.safetensors`,
  strength 1.0, scheduler `simple`). In our A/B tests it is the sharpest,
  the most prompt-faithful and the most robust of every turbo LoRA we tried.
  See [Which turbo LoRA?](#5-which-turbo-lora-should-you-actually-use).
- Q4_K_M is the **workhorse** (largest clip/quality envelope).
  Q6_K gives more detail but is a *bigger* file (28.2 GB vs 19.9 GB), needs
  more staging, and turbo LoRAs visibly degraded quality in our tests.
- **CUTE attention kernels do run on the B580** (BMG) — we see the route
  enabled in the container logs, not just on B60/B70.
- SeedVR2 2× upscale works, but in a **separate stack without
  DynamicVRAM** (3.3 GB model fits resident; per-chunk re-staging kills
  AIMDO).
- Only **one GPU-intensive stack at a time** — 12 GB is the hard limit.

Reference timings (Q4_K_M + 4-step 768p turbo, 16:9, 24 fps):

| Resolution | Duration (frames) | Time |
|---|---|---|
| 864×480 (0.4 MP) | 5 s (124 f) | ~1 min 53 s |
| 1.0 MP | 8 s (192 f) | ~8 min 34 s |
| 1.0 MP | 10 s (243 f) | ~12 min 9 s |
| 1.0 MP | 14 s (345 f) | ~23 min 28 s |
| 1.2 MP | 10 s (243 f) | ~16 min 8 s |

---

## 1. Hardware & software

| Component | Spec |
|---|---|
| GPU | Intel Arc B580, 12 GB GDDR6, 192 GB/s, Xe2 (Battlemage / BMG) |
| CPU | AMD Ryzen 5 7600 (6C/12T) |
| RAM | 32 GB DDR5 |
| OS | **Ubuntu 26.04 LTS** |
| Container engine | Docker + Docker Compose v2 |
| GPU stack | Intel GPU kernel driver (i915/Xe) + Level Zero user-mode runtime |
| ComfyUI image | `llm-scaler-omni:0.2.0-b2-comfyui-bmg` (source build, ComfyUI **v0.35.0**) |

**Driver notes (both matter):**

- The PyTorch/Comfy wheels ship the SYCL runtime and Level Zero *loader*,
  but **not** the user-mode GPU driver. Without a working
  `libze_loader.so` the XPU device count is 0 and ComfyUI falls over.
- The Intel GPU apt repository **suite must match your Ubuntu release**
  (`repositories.intel.com/gpu/ubuntu <codename>`). A host configured for
  `jammy` while running a much newer release is a silent trap — we hit it.
  Check what is actually installed:
  ```bash
  apt list --installed | grep -iE 'intel-opencl|intel-media|level-zero|libze'
  clinfo | head -20
  ```

**Image tags — read this before you copy a compose file:**

| Tag | ComfyUI | Model/output paths | Notes |
|---|---|---|---|
| `intel/llm-scaler-omni:0.2.0-b1` | 0.31 | `/llm/ComfyUI/models`, `/llm/ComfyUI/output` | Published bare-version tag. No sparse-attention (SolAttn) nodes. |
| `llm-scaler-omni:0.2.0-b2-comfyui-bmg` (local build) | **0.35.0** | `/models/host:ro` + `--extra-model-paths-config`, `/data/input`, `/data/output`, `/data/user` | **Source build only** — `0.2.0-b2` was never published to Docker Hub. Adds native SOL/SLA/VSA sparse attention, `MiniMaxH3AddGuide` (V2V), and updated `comfy-kitchen` / `comfy-aimdo`. |

The GitHub README of `intel/llm-scaler` describes the **b2** source build;
only bare version tags are published. Always verify what is really running:

```bash
docker exec comfyui_h3 sh -c 'ps -ef | grep main.py'
docker exec comfyui_h3 sh -c 'cat /llm/manifests/comfyui-python-freeze.txt | head'
```

## 2. Build the image (b2 / ComfyUI 0.35)

```bash
git clone https://github.com/intel/llm-scaler.git /tmp/llm-scaler
cd /tmp/llm-scaler/omni
OMNI_IMAGE_REPOSITORY=llm-scaler-omni XPU_TARGET=bmg bash build.sh
```

This produces the local tag `llm-scaler-omni:0.2.0-b2-comfyui-bmg`
(AOT-compiled for BMG). If your compose file references the image with an
`intel/` prefix, retag it or set `H3_IMAGE` accordingly.

Validate before you trust it:

```bash
IMAGE=llm-scaler-omni:0.2.0-b2-comfyui-bmg
docker run --rm --device=/dev/dri "$IMAGE" /llm/entrypoints/validate_comfyui_image.sh
```

The acceptance script checks package identity, Torch ABI, native AOT target,
XPU availability and required Kitchen capabilities.

**b2 run shape** (from Intel's own docs — note the external mounts):

```bash
docker run -itd --device=/dev/dri --network=host --shm-size=16g \
  --name=comfyui_h3 --workdir=/llm/ComfyUI \
  -v /path/models:/models/host:ro \
  -v /path/input:/data/input \
  -v /path/output:/data/output \
  -v /path/user:/data/user \
  "$IMAGE" \
  /llm/entrypoints/start_comfyui.sh
```

Two things to know about the entrypoint:

- `start_comfyui.sh` enables **DynamicVRAM** (`--enable-dynamic-vram`),
  reserves 4 GiB (`--reserve-vram`) and turns on Node Manager. Intel's docs
  are explicit that this costs some performance and is meant for workloads
  with a real OOM risk. **H3 is exactly that workload** — the denoiser does
  not fit in 12 GB, so we use the entrypoint.
- Keep host models and mutable data **outside** `/llm/ComfyUI`. Mounting over
  its `models/`, `input/` or `output/` hides upstream-tracked files and breaks
  `tools/update_comfyui.sh`. Use `/models/host:ro` + the extra-model-paths
  config (b2) or `/llm/ComfyUI/models` (b1).

## 3. Model files

Sizes below are the **upstream** figures (decimal GB, as shown on Hugging
Face). Check `ls -lh` after downloading — re-quantizations do happen.

### 3.1 Denoisers — `vantagewithai/MiniMax-H3-comfyUI-GGUF`

There are **two model families**, in two subfolders. Pick per task:

| Task | File | Size | Folder |
|---|---|---|---|
| T2V / I2V / V2V | `minimax_h3_fl2va-Q4_K_M.gguf` | 19.9 GB | `fl2va/` |
| T2V / I2V / V2V, more detail | `minimax_h3_fl2va-Q6_K.gguf` | 28.2 GB | `fl2va/` |
| Reference-to-video (R2V) | `minimax_h3_ref2va-Q4_K_M.gguf` | 19.9 GB | `ref2va/` |
| Reference-to-video, more detail | `minimax_h3_ref2va-Q6_K.gguf` | 28.2 GB | `ref2va/` |

Other quants in those folders: `Q4_0` 19.9 GB, `Q4_1` 21.9 GB,
`Q5_K_M` 23.9 GB, `Q5_K_S` 23.9 GB, `Q8_0` 36 GB, `Q3_K_M` 15.6 GB.

**Quant routing matters on XPU.** `ComfyUI-GGUF-XPU` registers optimized
Kitchen/XPU routes for **Q4_0, Q4_1, Q8_0, Q4_K, Q6_K** only. Q2/Q3/Q5
variants fall back to generic PyTorch dequantization — dramatically slower.
Stick to **Q4_K_M** (default) or **Q6_K** (quality target). Verify after the
first load with `gguf qtypes:` in the container logs.

### 3.2 Text encoder and VAEs — `Comfy-Org/MiniMax-H3`

| Role | File | Size |
|---|---|---|
| Text encoder | `text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` | 15 GB |
| Video VAE | `vae/minimax_h3_video_vae_fp16.safetensors` | 4.9 GB |
| Audio VAE | `vae/minimax_h3_audio_vae_fp32.safetensors` | 578 MB |
| Fallback denoiser (bf16/int8, no GGUF) | `diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors` | 19.5 GB |
| Fallback R2V denoiser | `diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors` | 19.5 GB |

ComfyUI layout:

```
models/diffusion_models/  minimax_h3_fl2va-Q4_K_M.gguf
                          minimax_h3_ref2va-Q4_K_M.gguf
models/text_encoders/     qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors
models/vae/               minimax_h3_video_vae_fp16.safetensors
                          minimax_h3_audio_vae_fp32.safetensors
models/loras/             minimax_h3_fl2v_turbo_4step_v1.0_768p_comfyui_bf16.safetensors
                          minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors
```

### 3.3 Turbo LoRAs

| LoRA | Size | Source | Our verdict |
|---|---|---|---|
| `minimax_h3_fl2v_turbo_4step_v1.0_768p_comfyui_bf16.safetensors` | 1.96 GB | `Comfy-Org/MiniMax-H3` (loras), mirror of LightX2V | **Default.** 4 steps, strength 1.0, scheduler `simple` |
| `minimax_h3_fl2v_turbo_4step_v1.1_768p_comfyui_bf16.safetensors` | 1.96 GB | `lightx2v/Minimax-h3-Turbo` | Newer revision of the same 768p 4-step recipe. Not tested by us — A/B it against v1.0 |
| `minimax_h3_fl2v_turbo_4step_v1.2_768p_comfyui_bf16.safetensors` | 1.96 GB | `lightx2v/Minimax-h3-Turbo` | Newest 768p revision upstream. Not tested by us |
| `minimax_h3_fl2v_turbo_8step_v1.0_768p_comfyui_bf16.safetensors` | 1.96 GB | `Comfy-Org/MiniMax-H3` | 8-step variant; what LightX2V's own Studio runs. Higher quality ceiling, ~2× the time. Not benchmarked by us |
| `minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors` | 1.96 GB | `Comfy-Org/MiniMax-H3` | **The R2V turbo LoRA** (separate model family, so a separate LoRA) |
| `minimax_h3_turbo_v4_step600_ema.safetensors` | ~744 MB | `larryvrh/MiniMax-H3-Turbo-Lora` | Works, but see below — not our default |
| `TaoMate-H3-3step-ComfyUI.safetensors` | 1.24 GB | `CZMartin22/TaoMate-H3-3step-ComfyUI` (from `TaoLiveAIGC/TaoMate-H3`) | Fastest option, different trade-offs |

**The "768p" in the name is the short edge.** Those LoRAs are distilled for a
768 px short edge (e.g. 1344×768 ≈ 1.0 MP at 16:9). At 1.2 MP you are
slightly outside that distilled range — our 1.2 MP tests still looked fine,
but treat it as untested territory rather than a guarantee.

**Do not** use Unsloth's `MiniMax-H3-GGUF` (formatted for
stable-diffusion.cpp / llama.cpp; ComfyUI fails with
`Unknown model architecture!`), and do not use GGUF text encoders — load the
Comfy-Org safetensors with a regular `CLIPLoader` (`type: minimax`).

## 4. The stack (Docker Compose)

Full file: `stacks/comfyui/compose.h3.yaml`. The essentials for the b2 image:

```yaml
services:
  comfyui_h3:
    image: llm-scaler-omni:0.2.0-b2-comfyui-bmg
    container_name: comfyui_h3
    restart: unless-stopped
    devices:
      - /dev/dri:/dev/dri
    group_add:
      - "${VIDEO_GID:-44}"    # video
      - "${RENDER_GID:-109}"   # render
    ports:
      - "${H3_PORT:-8389}:8188"
    environment:
      - ONEAPI_DEVICE_SELECTOR=level_zero:0
      - ZES_ENABLE_SYSMAN=1
      - OMNI_COMFYUI_RESERVE_VRAM_GB=4
      - OMNIXPU_PROVIDER_BOOTSTRAP=auto
      - OMNI_ATTN_BACKEND=auto
    volumes:
      - ./models:/models/host:ro          # b2: external model mount + config
      - ./input:/data/input
      - ./output:/data/output
      - ./user:/data/user
      # custom nodes: mount per node, never the whole custom_nodes dir
      - ./custom_nodes/rgthree-comfy:/llm/ComfyUI/custom_nodes/rgthree-comfy
      - ./custom_nodes/ComfyUI-MiniMax-H3-Turbo:/llm/ComfyUI/custom_nodes/ComfyUI-MiniMax-H3-Turbo
      - ./custom_nodes/Herrgotts-H3-Infinite-Continuation-Suite:/llm/ComfyUI/custom_nodes/Herrgotts-H3-Infinite-Continuation-Suite
    entrypoint: ["sh", "-c", "umask 000 && exec /llm/entrypoints/start_comfyui.sh"]
    shm_size: 16g
```

**Why the details matter:**

- **DynamicVRAM** comes from the entrypoint
  (`start_comfyui.sh` → `--enable-dynamic-vram`). `OMNI_COMFYUI_RESERVE_VRAM_GB`
  is the AIMDO reserve (default 4 GiB; raise in 2 GiB steps on OOM).
- **`umask 000`**: the image runs as root, so outputs are root-owned. `umask 000`
  makes them world-writable (0666) so a non-root file browser can delete them
  without `chown`. Don't set `user:` on this image — it can break GPU detection.
- **Custom nodes must be host bind-mounts.** `docker exec ... git clone` is
  ephemeral: it disappears on `compose down/up`. Mount each node's subfolder
  individually; mounting the whole `custom_nodes` directory shadows the nodes
  bundled in the image (ComfyUI-GGUF-XPU, OmniXPU, nunchaku-XPU, KJNodes,
  Easy-Use, VideoHelperSuite, ControlNet-aux, Node Manager).
- **One GPU stack at a time.** Stop every other GPU container first.
- **Workflows live in the user directory**: with b2 that is
  `user/default/workflows/` on the host (mounted at `/data/user`). `docker cp`
  into `/llm/ComfyUI/user/...` does *not* show up in the b2 UI.

Custom nodes used by the workflows in this repo:

| Node pack | Why |
|---|---|
| `rgthree-comfy` | Any Switch / Power Lora Loader in the reference workflows |
| `ComfyUI-MiniMax-H3-Turbo` (larryvrh) | Optional: Turbo Sampler + Turbo LoRA node, fallback if the plain LoRA loader misbehaves on GGUF |
| `Herrgotts-H3-Infinite-Continuation-Suite` | Seamless long-video chaining (latent-level masked AV continuation; needs ComfyUI ≥ 0.34) |
| `Comfyui_Minimax_h3_latent_Upscaler` | Latent-space upscale alternative to SeedVR2 (patched for XPU/NestedTensor) |

## 5. Which turbo LoRA should you actually use?

This is where most guides get it wrong, so here is our measured A/B — same
prompt, same seed, Q4_K_M, 1.0 MP, 24 fps:

| LoRA / schedule | Time (8 s / 192 f) | Prompt adherence | Look | Verdict |
|---|---|---|---|---|
| No LoRA, 8 steps (baseline) | 229 s @ 0.4 MP / 5 s | reference | reference | quality reference, 2× slower at equal settings |
| **4-step 768p (v1.0), 4 steps** | **514 s** | **best** — follows framing instructions | **sharpest**, no artifacts | **our default** |
| larryvrh v4-step600-EMA, 6 steps | 744 s | weaker — character drifts further from camera | "dreamier", softer | good micro-detail, different composition; experiment |
| TaoMate-H3 3-step, 3 steps (Euler) | **432 s** | acceptable | acceptable | fastest; strict settings required |

**Recommendation: the 4-step 768p LoRA** (`..._4step_v1.0_768p_comfyui_bf16...`),
strength **1.0**, scheduler **`simple`**, **4 steps**, on **Q4_K_M**. It gave
the sharpest images, the most faithful framing and the largest clip envelope
(we rendered 14 s @ 1.0 MP with it). The "768p" variants are also the ones
LightX2V keeps iterating on (v1.1, v1.2 upstream), so they are the line to
track.

Two alternatives, with honest caveats:

- **larryvrh `v4_step600_ema`** (6–8 steps) is the community favourite — a
  25-config × 10-scene comparison arena exists at
  `jo-nike.github.io/h3-turbo-eval/`, and the model card calls it the
  strongest checkpoint. In *our* A/B it changed the composition at identical
  prompt/seed and brought back a dreamy look we had deliberately eliminated.
  Great if you want its micro-detail; not our default.
- **TaoMate-H3 3-step** is the fastest thing we ran (0.4 MP / 8 s in 131 s on
  Q4_K_M) and the results looked fine. It is strict though: **exactly 3
  steps, Euler sampler, CFG 1.0, strength 1.0** — CFG above 1.0 burns the
  distilled ODE, and `res_multistep` is not the intended sampler.

**Q6_K + turbo LoRA: our results say don't.** With Q6_K the 4-step turbo
visibly degraded quality (drowsy, over-animated look) compared to plain
8-step sampling. The 6-step and 3-step LoRAs both **crashed** Q6_K at
1.0 MP / 8 s. Use Q6_K without a turbo LoRA at 8 steps, or stay on Q4_K_M
with the 4-step turbo.

## 6. Workflows

The repo ships these ComfyUI workflows (UI format unless noted):

| Workflow | What it does |
|---|---|
| `H3-GGUF-T2V.json` | T2V + I2V on the fl2va denoiser, 4-step 768p turbo (default workhorse) |
| `H3-GGUF-R2V.json` | Reference-to-video on the **ref2va** denoiser, 3 reference images, ref2v 4-step turbo behind a switch (off by default) |
| `H3-GGUF-R2V-Turbo-Larryvrh.json` | R2V variant with the larryvrh turbo LoRA (experiment) |
| `H3-GGUF-V2V-Continue.json` | Video-to-video continuation via `MiniMaxH3AddGuide` (needs ComfyUI ≥ 0.34) |
| `H3-GGUF-T2V-InfiniteChain-3Clip.json` | 3 seamlessly chained 5 s clips (Herrgott suite); `.api.json` variant for headless queueing |
| `H3-GGUF-T2V-v4turbo-test.json` | larryvrh v4-step600-EMA @ 6 steps (A/B reference) |
| `H3-GGUF-T2V-3step-test.json` | TaoMate 3-step @ Euler / 3 steps (A/B reference) |
| `H3-SeedVR2-Upscale.json` | SeedVR2 2× video upscale (separate stack, see below) |
| `Krea2-T2I.json` | Krea2 Turbo image generation on the same stack |

Deploy them into the sidebar library (`user/default/workflows/` on the host,
`/data/user/default/workflows/` in the b2 container) with
`bash scripts/deploy_h3_workflows.sh`.

Headless queueing: `scripts/queue_comfyui_workflow.py` POSTs an API prompt
to `:8389` and waits for completion.

**Frame grid:** H3 samples on a `17k+5` frame grid. At 24 fps that means
3 s → 73, 5 s → 124, 8 s → 192, 10 s → 243, 12 s → 294, 15 s → 362 frames.
The `Duration (Seconds)` node in the workflows snaps to this automatically.

## 7. Benchmarks

Measured on the rig above, wall-clock for a complete generation (model load
+ sampling + VAE decode + mux).

### 7.1 FL2VA (T2V/I2V) — Q4_K_M + 4-step 768p turbo

| Resolution | Duration | Frames | Time | s/frame | Note |
|---|---|---|---|---|---|
| 864×480 (0.4 MP) | 5 s | 124 | 113 s | 0.91 | 2.03× faster than the 8-step no-LoRA baseline (229 s) |
| 864×480 (0.4 MP) | 5 s (I2V) | 124 | 140 s | 1.13 | first-frame conditioning adds ~27 s |
| 1.0 MP | 8 s | 192 | 514 s | 2.68 | sweet spot for iteration |
| 1.0 MP | 8 s | 192 | 544 s | 2.83 | repeat after the b2/0.35 upgrade (cold container) |
| 1.0 MP | 10 s | 243 | 729 s | 3.00 | recommended production config |
| 1.0 MP | 14 s | 345 | 1408 s | 4.08 | +40% frames → +93% time |
| 1.2 MP | 10 s | 243 | 968 s | 3.98 | −25% time vs 1.2 MP @ 12 s; max res at 10 s |
| 1.2 MP | 12 s | 294 | 1423 s | 4.84 | near the staging ceiling |

Scaling is **non-linear**: temporal 3D attention is ~O(N²) and longer
sequences trigger more AIMDO RAM↔VRAM staging. Dropping 1.2 MP → 1.0 MP
saves ~25% of the time for ~17% fewer pixels. Practical production range:
**8–10 s at 1.0–1.2 MP**.

### 7.2 Turbo LoRA / step comparison (Q4_K_M, 1.0 MP, 8 s / 192 f)

| Configuration | Time | s/frame | Notes |
|---|---|---|---|
| 4-step 768p turbo | 514 s | 2.68 | default; sharpest, most faithful |
| TaoMate 3-step (Euler) | 432 s | 2.25 | fastest; strict sampler/CFG requirements |
| larryvrh v4-step600-EMA @ 6 steps | 744 s | 3.88 | more detail, different composition, "dreamier" |

### 7.3 Q6_K limits (12 GB)

Q6_K is a **larger** file than Q4_K_M (28.2 GB vs 19.9 GB upstream), so it
needs more AIMDO staging. It has an optimized XPU route and gives more
detail, but the headroom is visibly smaller:

| Configuration | Result |
|---|---|
| Q6_K, no turbo LoRA, 8 steps, 0.4 MP / 5 s | ~2 min (≈14 s/step) — our quality reference on Q6 |
| Q6_K + 4-step turbo | runs, but quality degraded (drowsy look) — bypass the LoRA, keep 8 steps |
| Q6_K + larryvrh 6-step, 1.0 MP / 8 s | 770 s |
| Q6_K + larryvrh 6-step, 1.0 MP / 10 s | **crash** (OOM / staging) |
| Q6_K + TaoMate 3-step, 1.0 MP / 8 s | **crash** |
| Q6_K + TaoMate 3-step, 0.4 MP / 8 s | 188 s — works |

**Rule of thumb: Q4_K_M for turbo workflows, Q6_K for non-turbo 8-step
quality runs.**

### 7.4 Reference-to-video (ref2va denoiser, 3 reference images)

Q4_K_M, no turbo LoRA (20 steps, `beta` scheduler):

| Resolution | Duration | Frames | Time | s/frame | Note |
|---|---|---|---|---|---|
| 0.4 MP | 5 s | 124 | 411 s | 3.31 | |
| 0.4 MP | 10 s | 243 | 826 s | 3.40 | near-linear in duration |
| 1.0 MP | 10 s | 243 | — | — | **crash** — 3 reference images + 1.0 MP + 20 steps exceeds the B580 envelope |

R2V is materially more expensive than T2V at the same settings (reference
tokens ride along every sampling step). Use `ref_image_size: match`, and
test the ref2v 4-step turbo before committing to long R2V renders.

### 7.5 Other models on the same hardware

| Model | Config | Time | Notes |
|---|---|---|---|
| SeedVR2 3B Int8 convrot | 2× upscale 864×480 → 1728×960, 5 s | 311 s | separate stack, **no** DynamicVRAM |
| Krea2 Turbo Int8 | 1024², 8 steps | 200 s cold / 45 s warm | needs DynamicVRAM (13 GB model) |
| 3× chained 5 s clips (Herrgott suite) | ≈13 s output, seamless | ~11 min total | needs ComfyUI ≥ 0.34 |

### 7.6 What we saw in the logs

Observed in our container logs (b1 image; the b2 build ships the same
OmniXPU/Kitchen stack with newer versions):

```
Intel(R) Arc(TM) B580 Graphics (VRAM: 12216 MB)
comfy-aimdo inited ... DynamicVRAM support detected and enabled
[OmniXPU] experimental capability-driven BMG D128 CUTE route enabled
[OmniXPU] attention CUTE_BHLD_D128 #1: heads=56
[OmniXPU] attention CUTE_H3_VAE_D64 #1: heads=32
Native ops: convrot_w4a4, int8_tensorwise
```

Takeaways: **CUTE attention does run on the B580** (the release notes only
mention B60/B70), and INT8 convrot kernels are active. Image models
(Krea2) fall back to torch attention — CUTE targets video attention
patterns, so that log line is normal, not a problem. BMG has no native FP8
XMX; Kitchen emulates FP8 via dequant → BF16 (log:
`fp8_gemm first use: dtype=torch.float8_e4m3fn`), which works but is slower.

## 8. Lessons learned (the hard part)

1. **Published tags ≠ README.** Only bare version tags are published;
   `0.2.0-b2` (ComfyUI 0.35, sparse attention, `/data/...` paths) is a
   **source build**. Verify what is really running with `ps -ef | grep main.py`.
2. **The Intel GPU apt suite must match your Ubuntu release.** A `jammy`
   repo on a newer host is a silent trap.
3. **Unsloth GGUF ≠ ComfyUI GGUF.** Use `vantagewithai` for the denoiser and
   Comfy-Org safetensors for the text encoder.
4. **Q2/Q3/Q5 GGUF quants fall back to slow PyTorch** on XPU. Use Q4_K_M or Q6_K.
5. **`docker exec ... git clone` is ephemeral.** Bind-mount custom nodes from the host.
6. **SageAttention is CUDA-only.** Bypass `PatchSageAttentionKJ`, FlashAttention
   and xFormers nodes when porting CUDA workflows; the b2 image has native
   SOL/SLA/VSA sparse attention and OmniXPU routing instead.
7. **SeedVR2 + DynamicVRAM = crash.** The 3.3 GB model fits resident;
   per-chunk AIMDO re-staging killed the process. Run it in a stack **without**
   `--enable-dynamic-vram`.
8. **Root-owned output.** Use `umask 000` in the entrypoint instead of a `user:`
   directive (which can break GPU detection).
9. **RAM caching between runs.** Staged weights (~30 GB) linger in RAM cache.
   Call `POST /free {"unload_models": true, "free_memory": true}` before the next
   heavy run, or bounce the stack.
10. **Check GGUF quant routing** after the first load (`gguf qtypes:` in the logs).
11. **Turbo LoRAs do work on GGUF** — all three we tested (4-step 768p,
    larryvrh 6-step, TaoMate 3-step) applied fine to the quantized denoiser on
    both Q4_K_M and Q6_K. But *which* turbo LoRA matters more than whether it
    works: see [section 5](#5-which-turbo-lora-should-you-actually-use).
12. **Q6_K is not "the small one".** It is ~40% larger than Q4_K_M, needs more
    staging, and its turbo-LoRA headroom is much smaller. Measure, don't assume.
13. **Long videos: chain clips, don't extend.** The Herrgott suite chains clips
    at the latent level with native per-token denoise masks (ComfyUI PR #15375,
    needs ComfyUI ≥ 0.34). 3 clips ≈ 13 s in ~11 min. Audio drift is the known
    weakness past ~60–90 s.
14. **Node titles lie; links don't.** In a working workflow, trace `links[]` and
    downstream node types before swapping model files. A `VAELoader` feeding
    `VAEDecodeAudio` must load the audio VAE, whatever its title says.
15. **b2 moved the user directory.** With `/data/user`, `docker cp` into
    `/llm/ComfyUI/user/` silently does nothing. Copy to the host's
    `user/default/workflows/` instead.

## 9. Prompting tips for H3

H3 has **one prompt field** (positive) and **no negative prompt field**; keep
a short avoid-list inline at the end (`No facial morphing, no subtitles, no
watermark.` — one line, 3–6 items).

- **Shot size is the #1 constraint.** H3 distorts faces that are far from the
  camera, and upscaling does not fix it. Keep character shots at
  **medium shot / medium-wide**; go wide only when identity is not critical.
- **One camera move per shot**, described as a path with amplitude and speed
  (`the camera pushes in with small amplitude at slow speed`).
- **Describe audio explicitly** — H3 generates sound natively and will invent a
  soundtrack if you don't. Layer it: ambient → action sounds → music. Dialogue
  via `<d>[English] ...</d>`, speaker close to camera and facing it.
- **Clips 5–15 s**, shots 2–5 s, explicit sequential timestamps for multi-shot
  prompts. 8–10 s is the sweet spot on this hardware.
- **One visual style**, no meta-words ("4K", "best quality"). Describe what you
  see: grain, bokeh, light falloff.
- **Prompt in English** even when the dialogue is in another language.
- **I2V is the safest route for character consistency**: generate a good still
  first (e.g. with Krea2 on the same stack), then animate it — and describe
  motion, camera and sound rather than re-describing the source image.
- **R2V:** reference the inputs by tag in connection order (`<Picture 1>`,
  `<Video 1>`, `<Audio 1>`); use `ref_image_size: match` for speed.

Example (T2V, 6 s, one shot):

```
Medium shot of a woman in her 30s with short black hair and a rust-red
coat standing on a rain-soaked Tokyo street at night. She looks over her
shoulder, then slowly turns three-quarter toward the camera. Static camera,
shallow depth of field. Photorealistic, shot on 35mm film, neon reflections
in puddles, soft frontal key light on her face. She says calmly:
<d>[English] I knew you would follow me.</d>
Rain patters on umbrellas, distant traffic, footsteps in puddles, low
atmospheric synthesizer pad. The shot ends on her face clearly lit under a
neon sign. No facial morphing, no subtitles, no watermark.
```

Full guide: `docs/minimax-h3-prompting.md` in the repo.

## 10. Scripts in this repo

```
scripts/
  download_h3_model.sh          # fl2va GGUF denoiser (--quant Q4_K_M|Q6_K|...)
  download_h3_ref2va_model.sh   # ref2va GGUF denoiser + ref2v 4-step turbo LoRA
  download_extra_loras.sh       # optional: 8-step turbo, TaoMate 3-step, larryvrh v4, latent upscaler
  setup_h3_custom_nodes.sh      # idempotent custom-node install (host bind-mounts)
  deploy_h3_workflows.sh        # copy workflows into the sidebar library
  queue_comfyui_workflow.py     # headless API queueing + wait
  generate_chain_workflow.py    # build the 3-clip infinite-chain workflow
  adapt_infinite_chain_workflow.py  # port the upstream showcase to GGUF/XPU
  patch_h3_upscaler.py          # XPU + NestedTensor patch for the latent upscaler
  health-check.sh / stop-all.sh
```

## 11. License note

MiniMax H3 is released under the **MiniMax H3 Community License Agreement**
(see `MiniMaxAI/MiniMax-H3` on Hugging Face), and the GGUF conversions carry
the same license. It restricts commercial use of the generated output. This
guide shares technical knowledge only — check the license yourself before any
commercial use.

## 12. Related resources

- Intel Omni image source + docs: `github.com/intel/llm-scaler` (`omni/`)
- Published image: `hub.docker.com/r/intel/llm-scaler-omni`
- ComfyUI H3 tutorial: `docs.comfy.org/tutorials/video/minimax/minimax-h3`
- GGUF denoiser: `huggingface.co/vantagewithai/MiniMax-H3-comfyUI-GGUF`
- Reference files + turbo LoRAs: `huggingface.co/Comfy-Org/MiniMax-H3`
- LightX2V turbo LoRAs (newest 768p revisions): `huggingface.co/lightx2v/Minimax-h3-Turbo`
- larryvrh turbo LoRA + nodes: `huggingface.co/larryvrh/MiniMax-H3-Turbo-Lora`
- TaoMate 3-step LoRA: `huggingface.co/CZMartin22/TaoMate-H3-3step-ComfyUI`
- Turbo LoRA comparison arena: `jo-nike.github.io/h3-turbo-eval/`
- Infinite continuation: `github.com/HerrgottMargott/Herrgotts-H3-Infinite-Continuation-Suite`

**Intel Arc compatibility tracker:** if you run H3 on a different Arc card
(A770, B60/B70, dual B70), please contribute your timings. Verified
engine/model/driver combinations — including this B580 + H3 config — are
logged in the Intel Arc AI Stack Compatibility Tracker (Apify actor
`buxQINgvy5isSHiGf`); the link is in the repo's Resources section.

## Repo structure

```
stacks/comfyui/
  compose.h3.yaml           # H3 stack (this guide)
  compose.seedvr2.yaml      # SeedVR2 stack (no DynamicVRAM)
  workflows/                # UI + .api.json workflows (section 6)
scripts/                    # downloads, custom nodes, deploy, queueing (section 10)
docs/
  benchmarks.md             # full dated benchmark log
  lessons-learned.md        # every problem + fix, dated
  minimax-h3-prompting.md   # complete prompting guide
```

---

*Cookbook based on the my rig (September 2026). Timings
are wall-clock on that specific machine — treat them as an order of
magnitude, not a guarantee for your host.*
