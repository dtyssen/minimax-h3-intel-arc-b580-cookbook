#!/usr/bin/env python3
"""
Generate H3-GGUF-T2V-Chain.json — twee-clip chaining workflow voor MiniMax H3.

Principe: genereer clip 1 (T2V 5s), decodeer, pak de last frame, voed die als
first_frame aan clip 2 (I2V 5s). Beide clips worden apart opgeslagen met eigen
audio. Samenvoegen met ffmpeg (zie scripts/chain_concat.sh).

VRAM: de twee samplers draaien sequentieel (ComfyUI voert nodes op volgorde
uit), dus VRAM wordt hergebruikt tussen clips — geen OOM bij 2x5s.

Usage:
    python3 scripts/generate_chain_workflow.py
    # -> stacks/comfyui/workflows/H3-GGUF-T2V-Chain.json
"""
import json
import os

# ── Node IDs ──────────────────────────────────────────────────
UNET    = 1   # UnetLoaderGGUF
CLIP    = 2   # CLIPLoader
VAE_V   = 3   # VAELoader (video)
VAE_A   = 4   # VAELoader (audio)
RES     = 5   # ResolutionSelector
DUR     = 6   # PrimitiveFloat (duration seconds)
MATH_L  = 7   # ComfyMathExpression (frame length)
I2V1    = 8   # MiniMaxH3ImageToVideo (clip 1, T2V)
GUID1   = 9   # BasicGuider (clip 1)
KS1     = 10  # KSamplerSelect (clip 1)
SCHED1  = 11  # BasicScheduler (clip 1)
NOISE1  = 12  # RandomNoise (clip 1)
SAMP1   = 13  # SamplerCustomAdvanced (clip 1)
VDEC1   = 14  # VAEDecode (clip 1)
VADEC1  = 15  # VAEDecodeAudio (clip 1)
CVID1   = 16  # CreateVideo (clip 1)
SVID1   = 17  # SaveVideo (clip 1)
IMGB    = 18  # ImageFromBatch (last frame)
MATH_I  = 19  # ComfyMathExpression (last index)
I2V2    = 20  # MiniMaxH3ImageToVideo (clip 2, I2V)
GUID2   = 21  # BasicGuider (clip 2)
KS2     = 22  # KSamplerSelect (clip 2)
SCHED2  = 23  # BasicScheduler (clip 2)
NOISE2  = 24  # RandomNoise (clip 2)
SAMP2   = 25  # SamplerCustomAdvanced (clip 2)
VDEC2   = 26  # VAEDecode (clip 2)
VADEC2  = 27  # VAEDecodeAudio (clip 2)
CVID2   = 28  # CreateVideo (clip 2)
SVID2   = 29  # SaveVideo (clip 2)

# ── Connections: (from_node, from_slot, to_node, to_slot, type) ──
CONNECTIONS = [
    (UNET, 0, GUID1, 0, "MODEL"),
    (UNET, 0, SCHED1, 0, "MODEL"),
    (UNET, 0, GUID2, 0, "MODEL"),
    (UNET, 0, SCHED2, 0, "MODEL"),
    (CLIP, 0, I2V1, 0, "CLIP"),
    (CLIP, 0, I2V2, 0, "CLIP"),
    (VAE_V, 0, I2V1, 1, "VAE"),
    (VAE_V, 0, VDEC1, 1, "VAE"),
    (VAE_V, 0, I2V2, 1, "VAE"),
    (VAE_V, 0, VDEC2, 1, "VAE"),
    (VAE_A, 0, VADEC1, 1, "VAE"),
    (VAE_A, 0, VADEC2, 1, "VAE"),
    (RES, 0, I2V1, 4, "INT"),       # width
    (RES, 1, I2V1, 5, "INT"),       # height
    (RES, 0, I2V2, 4, "INT"),       # width
    (RES, 1, I2V2, 5, "INT"),       # height
    (DUR, 0, MATH_L, 0, "FLOAT"),
    (MATH_L, 1, I2V1, 6, "INT"),    # length
    (MATH_L, 1, I2V2, 6, "INT"),    # length
    (MATH_L, 1, MATH_I, 0, "INT"),  # length -> last index calc
    (I2V1, 0, GUID1, 1, "CONDITIONING"),
    (I2V1, 1, SAMP1, 4, "LATENT"),
    (GUID1, 0, SAMP1, 1, "GUIDER"),
    (KS1, 0, SAMP1, 2, "SAMPLER"),
    (SCHED1, 0, SAMP1, 3, "SIGMAS"),
    (NOISE1, 0, SAMP1, 0, "NOISE"),
    (SAMP1, 0, VDEC1, 0, "LATENT"),
    (SAMP1, 0, VADEC1, 0, "LATENT"),
    (VDEC1, 0, CVID1, 0, "IMAGE"),
    (VDEC1, 0, IMGB, 0, "IMAGE"),
    (VADEC1, 0, CVID1, 1, "AUDIO"),
    (CVID1, 0, SVID1, 0, "VIDEO"),
    (MATH_I, 1, IMGB, 1, "INT"),     # batch_index = last frame
    (IMGB, 0, I2V2, 2, "IMAGE"),    # first_frame for clip 2
    (I2V2, 0, GUID2, 1, "CONDITIONING"),
    (I2V2, 1, SAMP2, 4, "LATENT"),
    (GUID2, 0, SAMP2, 1, "GUIDER"),
    (KS2, 0, SAMP2, 2, "SAMPLER"),
    (SCHED2, 0, SAMP2, 3, "SIGMAS"),
    (NOISE2, 0, SAMP2, 0, "NOISE"),
    (SAMP2, 0, VDEC2, 0, "LATENT"),
    (SAMP2, 0, VADEC2, 0, "LATENT"),
    (VDEC2, 0, CVID2, 0, "IMAGE"),
    (VADEC2, 0, CVID2, 1, "AUDIO"),
    (CVID2, 0, SVID2, 0, "VIDEO"),
]

# ── Build links + input/output references ─────────────────────
links = []
link_counter = 0
node_in_links = {}   # (node_id, slot) -> link_id
node_out_links = {}  # (node_id, slot) -> [link_ids]

for fn, fs, tn, ts, ty in CONNECTIONS:
    link_counter += 1
    lid = link_counter
    links.append([lid, fn, fs, tn, ts, ty])
    node_in_links[(tn, ts)] = lid
    node_out_links.setdefault((fn, fs), []).append(lid)

# ── Node factory ──────────────────────────────────────────────
def node(nid, ntype, pos, order, inputs_spec, outputs_spec, widgets, title=None, mode=0, size=None, props=None):
    inputs = []
    for slot, name, ty, has_link in inputs_spec:
        inp = {"name": name, "type": ty}
        key = (nid, slot)
        if key in node_in_links:
            inp["link"] = node_in_links[key]
        elif has_link is not None:
            inp["link"] = None
        if has_link == "widget":
            inp["widget"] = {"name": name}
        inputs.append(inp)

    outputs = []
    for slot, name, ty in outputs_spec:
        key = (nid, slot)
        out = {"name": name, "type": ty, "links": node_out_links.get(key, [])}
        if slot == 0 and len(outputs_spec) > 1:
            out["slot_index"] = 0
        outputs.append(out)

    n = {
        "id": nid, "type": ntype, "pos": pos,
        "size": size or [300, 100],
        "flags": {}, "order": order, "mode": mode,
        "inputs": inputs, "outputs": outputs,
        "properties": props or {"cnr_id": "comfy-core", "ver": "0.31.0",
                        "Node name for S&R": ntype},
        "widgets_values": widgets,
    }
    if title:
        n["title"] = title
    return n

# ── Node input specs: (slot, name, type, link_status) ──────────
# link_status: None=no link (pure widget), "widget"=widget override, True=linked
NO_IN = []
MODEL_IN = [(0, "model", "MODEL", True)]
GUIDER_IN = [(0, "model", "MODEL", True), (1, "conditioning", "CONDITIONING", True)]
VAE_DECODE_IN = [(0, "samples", "LATENT", True), (1, "vae", "VAE", True)]
CLIP_VAE_IN = [(0, "clip", "CLIP", True), (1, "vae", "VAE", True)]
SAMPLER_IN = [
    (0, "noise", "NOISE", True), (1, "guider", "GUIDER", True),
    (2, "sampler", "SAMPLER", True), (3, "sigmas", "SIGMAS", True),
    (4, "latent_image", "LATENT", True),
]

PROMPT1 = (
    "Cinematic 5-second scene: a red panda stepping along a mossy log "
    "in a misty forest, soft morning light, shallow depth of field, "
    "cinematic camera following the panda. Audio: forest ambience, "
    "birds, soft footsteps on moss."
)
PROMPT2 = (
    "Continuation: the red panda reaches the end of the log, pauses to "
    "look around alertly, then leaps gracefully to the next branch. "
    "Same misty forest, same lighting. Audio: rustling leaves, a soft "
    "thud on landing, continued forest ambience."
)

# ── Build all nodes ───────────────────────────────────────────
nodes = [
    node(UNET, "UnetLoaderGGUF", [-2400, 400], 1, NO_IN,
         [(0, "MODEL", "MODEL")], ["minimax_h3_fl2va-Q6_K.gguf"],
         title="H3 Denoiser Q6_K", size=[300, 58],
         props={"cnr_id": "comfyui-gguf", "ver": "1.1.10", "Node name for S&R": "UnetLoaderGGUF"}),

    node(CLIP, "CLIPLoader", [-2400, 500], 2, NO_IN,
         [(0, "CLIP", "CLIP")],
         ["qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors", "minimax", "default"],
         title="Text Encoder", size=[320, 106]),

    node(VAE_V, "VAELoader", [-2400, 650], 3, NO_IN,
         [(0, "VAE", "VAE")], ["minimax_h3_video_vae_fp16.safetensors"],
         title="Video VAE", size=[300, 58]),

    node(VAE_A, "VAELoader", [-2400, 750], 4, NO_IN,
         [(0, "VAE", "VAE")], ["minimax_h3_audio_vae_fp32.safetensors"],
         title="Audio VAE", size=[300, 58]),

    node(RES, "ResolutionSelector", [-2400, 870], 5, NO_IN,
         [(0, "width", "INT"), (1, "height", "INT")],
         ["16:9 (Widescreen)", 0.4, 32], title="Resolution", size=[270, 126]),

    node(DUR, "PrimitiveFloat", [-2400, 1030], 6, NO_IN,
         [(0, "FLOAT", "FLOAT")], [5], title="Duration (s)", size=[270, 60]),

    node(MATH_L, "ComfyMathExpression", [-2050, 1030], 7,
         [(0, "values.a", "FLOAT,INT,BOOLEAN", True)],
         [(0, "FLOAT", "FLOAT"), (1, "INT", "INT"), (2, "BOOL", "BOOLEAN")],
         ["max(5, round(a * 24)) + (5 - (max(5, round(a * 24)) % 17)) % 17"],
         title="Frame Length", size=[360, 160]),

    # ── Clip 1 (T2V) ──────────────────────────────────────────
    node(I2V1, "MiniMaxH3ImageToVideo", [-1650, 400], 8,
         [(0, "clip", "CLIP", True), (1, "vae", "VAE", True),
          (2, "first_frame", "IMAGE", None), (3, "last_frame", "IMAGE", None),
          (4, "width", "INT", "widget"), (5, "height", "INT", "widget"),
          (6, "length", "INT", "widget")],
         [(0, "positive", "CONDITIONING"), (1, "LATENT", "LATENT")],
         [PROMPT1, 864, 480, 73],
         title="Clip 1 — T2V (5s)", size=[500, 200]),

    node(GUID1, "BasicGuider", [-1650, 650], 9, GUIDER_IN,
         [(0, "GUIDER", "GUIDER")], []),

    node(KS1, "KSamplerSelect", [-1650, 730], 10, NO_IN,
         [(0, "SAMPLER", "SAMPLER")], ["res_multistep"], size=[280, 58]),

    node(SCHED1, "BasicScheduler", [-1650, 810], 11, MODEL_IN,
         [(0, "SIGMAS", "SIGMAS")], ["simple", 8, 1], size=[280, 106]),

    node(NOISE1, "RandomNoise", [-1650, 950], 12, NO_IN,
         [(0, "NOISE", "NOISE")], [0, "randomize"], size=[280, 82]),

    node(SAMP1, "SamplerCustomAdvanced", [-1250, 650], 13, SAMPLER_IN,
         [(0, "output", "LATENT"), (1, "denoised_output", "LATENT")], [],
         title="Sampler 1", size=[270, 106]),

    node(VDEC1, "VAEDecode", [-850, 500], 14, VAE_DECODE_IN,
         [(0, "IMAGE", "IMAGE")], [],
         title="VAEDecode 1", size=[230, 60]),

    node(VADEC1, "VAEDecodeAudio", [-850, 600], 15,
         [(0, "samples", "LATENT", True), (1, "vae", "VAE", True)],
         [(0, "AUDIO", "AUDIO")], [], title="VAEDecodeAudio 1", size=[230, 60]),

    node(CVID1, "CreateVideo", [-450, 550], 16,
         [(0, "images", "IMAGE", True), (1, "audio", "AUDIO", True)],
         [(0, "VIDEO", "VIDEO")], [24, 8], title="CreateVideo 1", size=[270, 102]),

    node(SVID1, "SaveVideo", [-50, 550], 17,
         [(0, "video", "VIDEO", True)], [],
         ["MiniMax_H3/chain/clip1", "auto", "auto"],
         title="Save Clip 1", size=[300, 106]),

    # ── Last frame bridge ─────────────────────────────────────
    node(IMGB, "ImageFromBatch", [-850, 750], 18,
         [(0, "image", "IMAGE", True), (1, "batch_index", "INT", "widget"),
          (2, "length", "INT", "widget")],
         [(0, "IMAGE", "IMAGE")], [0, 1],
         title="Last Frame (clip 1)", size=[250, 80]),

    node(MATH_I, "ComfyMathExpression", [-850, 870], 19,
         [(0, "values.a", "FLOAT,INT,BOOLEAN", True)],
         [(0, "FLOAT", "FLOAT"), (1, "INT", "INT"), (2, "BOOL", "BOOLEAN")],
         ["a - 1"], title="Last Frame Index", size=[360, 160]),

    # ── Clip 2 (I2V) ──────────────────────────────────────────
    node(I2V2, "MiniMaxH3ImageToVideo", [-450, 750], 20,
         [(0, "clip", "CLIP", True), (1, "vae", "VAE", True),
          (2, "first_frame", "IMAGE", True), (3, "last_frame", "IMAGE", None),
          (4, "width", "INT", "widget"), (5, "height", "INT", "widget"),
          (6, "length", "INT", "widget")],
         [(0, "positive", "CONDITIONING"), (1, "LATENT", "LATENT")],
         [PROMPT2, 864, 480, 73],
         title="Clip 2 — I2V (5s, first_frame from clip 1)", size=[500, 200]),

    node(GUID2, "BasicGuider", [-450, 1000], 21, GUIDER_IN,
         [(0, "GUIDER", "GUIDER")], []),

    node(KS2, "KSamplerSelect", [-450, 1080], 22, NO_IN,
         [(0, "SAMPLER", "SAMPLER")], ["res_multistep"], size=[280, 58]),

    node(SCHED2, "BasicScheduler", [-450, 1160], 23, MODEL_IN,
         [(0, "SIGMAS", "SIGMAS")], ["simple", 8, 1], size=[280, 106]),

    node(NOISE2, "RandomNoise", [-450, 1300], 24, NO_IN,
         [(0, "NOISE", "NOISE")], [1, "randomize"], size=[280, 82]),

    node(SAMP2, "SamplerCustomAdvanced", [-50, 1000], 25, SAMPLER_IN,
         [(0, "output", "LATENT"), (1, "denoised_output", "LATENT")], [],
         title="Sampler 2", size=[270, 106]),

    node(VDEC2, "VAEDecode", [350, 850], 26,
         [(0, "samples", "LATENT", True), (1, "vae", "VAE", True)],
         [(0, "IMAGE", "IMAGE")], [], title="VAEDecode 2", size=[230, 60]),

    node(VADEC2, "VAEDecodeAudio", [350, 950], 27,
         [(0, "samples", "LATENT", True), (1, "vae", "VAE", True)],
         [(0, "AUDIO", "AUDIO")], [], title="VAEDecodeAudio 2", size=[230, 60]),

    node(CVID2, "CreateVideo", [750, 900], 28,
         [(0, "images", "IMAGE", True), (1, "audio", "AUDIO", True)],
         [(0, "VIDEO", "VIDEO")], [24, 8], title="CreateVideo 2", size=[270, 102]),

    node(SVID2, "SaveVideo", [1150, 900], 29,
         [(0, "video", "VIDEO", True)], [],
         ["MiniMax_H3/chain/clip2", "auto", "auto"],
         title="Save Clip 2", size=[300, 106]),
]

# ── Assemble workflow ─────────────────────────────────────────
wf = {
    "id": "h3-gguf-t2v-chain-001",
    "revision": 0,
    "last_node_id": 29,
    "last_link_id": link_counter,
    "nodes": nodes,
    "links": links,
    "groups": [],
    "config": {},
    "extra": {},
    "version": 0.4,
}

# ── Write ─────────────────────────────────────────────────────
out = os.path.join(os.path.dirname(__file__), "..", "stacks", "comfyui", "workflows",
                    "H3-GGUF-T2V-Chain.json")
out = os.path.normpath(out)
with open(out, "w", encoding="utf-8") as f:
    json.dump(wf, f, indent=2, ensure_ascii=False)

print(f"Workflow geschreven: {out}")
print(f"  Nodes: {len(nodes)}, Links: {len(links)}")
print(f"  Clip 1: T2V 5s -> SaveVideo (MiniMax_H3/chain/clip1)")
print(f"  Bridge: last frame clip 1 -> first_frame clip 2")
print(f"  Clip 2: I2V 5s -> SaveVideo (MiniMax_H3/chain/clip2)")
print(f"  Samenvoegen: bash scripts/chain_concat.sh")
