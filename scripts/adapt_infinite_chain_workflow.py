#!/usr/bin/env python3
"""
Adaptatie van Herrgott's H3 Infinite Continuation Suite showcase-workflow
naar onze B580/GGUF-stack, inclusief UI->API-conversie voor queueing.

Aanpassingen t.o.v. upstream (Herrgotts_H3_Infinite_v1.4_03_3Clip_Showcase_AutoStitch.json):
  - UNETLoader (fl2va_pruned_int8 safetensors) -> UnetLoaderGGUF Q4_K_M
  - PathchSageAttentionKJ + MiniMaxH3SigmaShift verwijderd (niet getest op
    XPU; onze 8-stap baseline gebruikt ze niet). Model-chain rechtstreeks.
  - BasicScheduler 15 -> 8 stappen (onze bewezen productiewaarde)
  - Clips 10 s -> 5 s (Net New Content), canvas 736x1280 -> 864x480
  - Sample-images (2 (6).png / 3 (5).png, niet in repo) -> first_frame_test.png
  - Prompts: eigen red-panda-scene conform docs/minimax-h3-prompting.md
  - SaveVideo -> MiniMax_H3/infinite/3clip_stitched

Usage:
    python3 scripts/adapt_infinite_chain_workflow.py <object_info.json>
        # -> stacks/comfyui/workflows/H3-GGUF-T2V-InfiniteChain-3Clip.json      (UI)
        # -> stacks/comfyui/workflows/H3-GGUF-T2V-InfiniteChain-3Clip.api.json  (API)
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WF_DIR = os.path.normpath(os.path.join(HERE, "..", "stacks", "comfyui", "workflows"))
UPSTREAM = os.path.join(WF_DIR, "upstream",
                        "Herrgotts_H3_Infinite_v1.4_03_3Clip_Showcase_AutoStitch.json")
OUT_UI = os.path.join(WF_DIR, "H3-GGUF-T2V-InfiniteChain-3Clip.json")
OUT_API = os.path.join(WF_DIR, "H3-GGUF-T2V-InfiniteChain-3Clip.api.json")

IMG = "first_frame_test.png"
MODEL = "minimax_h3_fl2va-Q4_K_M.gguf"
W, H = 864, 480
STEPS = 8
DUR = 5.0

PROMPT1 = (
    "Medium shot of a red panda with rust-orange fur, white face markings and a "
    "long ringed tail walking slowly left-to-right along a moss-covered fallen "
    "log in a misty pine forest. Soft morning light, shallow depth of field. The "
    "camera tracks sideways at slow speed with small amplitude, keeping the panda "
    "centered. The panda reaches a bright green fern, pauses and lifts its head, "
    "ending in a calm standing pose facing right. Photorealistic wildlife "
    "documentary look. Audio: quiet forest ambience, distant birdsong, soft paw "
    "steps on moss, no music. Keep the fog, log and ferns unchanged. No facial "
    "morphing, no extra animals, no watermark."
)
PROMPT2 = (
    "Continuation of the same scene: the red panda at the fern takes two slow "
    "steps forward, lowers its head to sniff the moss, then raises its head and "
    "looks calmly toward the second red panda standing at the right end of the "
    "log. Static camera, medium shot, identical misty pine forest, soft morning "
    "light. Both pandas remain in frame, ending in a still, balanced "
    "composition. Photorealistic wildlife documentary look. Audio: forest "
    "ambience, a soft sniff, faint wind through the pines, one distant bird "
    "call, no music. Keep fur colors, log position and fog density unchanged. "
    "No morphing, no duplicated limbs, no watermark."
)
PROMPT3 = (
    "Continuation of the same scene: the two red pandas on the mossy log face "
    "each other calmly; the smaller one on the right lifts its ringed tail once "
    "and settles, then both stay still, ears twitching slightly. Static camera, "
    "medium shot, same misty pine forest and soft morning light. The shot comes "
    "to rest on the balanced two-panda composition. Photorealistic wildlife "
    "documentary look. Audio: calm forest ambience, a soft churring call from "
    "the left panda, faint wind, no music. Keep identity, fur, fog and lighting "
    "unchanged. No facial morphing, no subtitles, no watermark."
)

# ── 1. UI-workflow transformeren ──────────────────────────────
wf = json.load(open(UPSTREAM, encoding="utf-8"))
nodes = {n["id"]: n for n in wf["nodes"]}

# 1a. Verwijder Sage (6) en SigmaShift (7): rewire alle links met origin 6/7
#     naar origin 2 slot 0 (de GGUF-loader).
DROP = {6, 7}
for ln in wf["links"]:
    if ln[1] in DROP:
        ln[1] = 2
        ln[2] = 0
wf["nodes"] = [n for n in wf["nodes"] if n["id"] not in DROP]
nodes = {n["id"]: n for n in wf["nodes"]}
n2 = nodes[2]
n2["outputs"][0]["links"] = sorted({ln[0] for ln in wf["links"] if ln[1] == 2})

# 1b. UNETLoader -> UnetLoaderGGUF
n2["type"] = "UnetLoaderGGUF"
n2["title"] = "H3 FL2VA Denoiser Q4_K_M (GGUF-XPU)"
n2["widgets_values"] = [MODEL]
n2["inputs"] = []
n2["properties"] = {"cnr_id": "comfyui-gguf", "ver": "1.1.10",
                    "Node name for S&R": "UnetLoaderGGUF"}
n2["size"] = [340, 58]

# 1c. Scheduler 8 stappen
nodes[9]["widgets_values"] = ["simple", STEPS, 1]

# 1d. LoadImage -> eerste beschikbare testframe (origines: '2 (6).png'/'3 (5).png'
#     zitten niet in de repo)
for nid in (11, 13, 14, 28, 41):
    nodes[nid]["widgets_values"][0] = IMG

# 1e. Start/Continue: prompts, canvas, duur
s = nodes[15]["widgets_values"]
nodes[15]["widgets_values"] = [PROMPT1, W, H, DUR, s[4]]
for nid, p in ((29, PROMPT2), (42, PROMPT3)):
    c = nodes[nid]["widgets_values"]
    # [prompt, width, height, duration, ctx, feather, aspect, mode, tail]
    nodes[nid]["widgets_values"] = [p, W, H, DUR, c[4], c[5], c[6], c[7], c[8]]

# 1f. Opschoonpad eigen subfolder
nodes[59]["widgets_values"][0] = "MiniMax_H3/infinite/3clip_stitched"

# 1g. Notities: upstream-markdown van de voorbeeldbeelden laten staan (id 1..60
#     MarkdownNotes zijn instructief), maar verwijder de Sage-note niet —
#     MarkdownNotes worden door de converter toch overgeslagen.

wf["last_node_id"] = max(n["id"] for n in wf["nodes"])
with open(OUT_UI, "w", encoding="utf-8") as f:
    json.dump(wf, f, indent=2, ensure_ascii=False)
print(f"UI-workflow: {OUT_UI}")

# ── 2. UI -> API-conversie (generic, object_info-gestuurd) ────
oi = json.load(open(sys.argv[1], encoding="utf-8"))

def widget_names(node_type):
    """Niet-forceInput widget-namen in volgorde required->optional."""
    spec = oi[node_type]["input"]
    names = []
    for sec in ("required", "optional"):
        for name, s2 in spec.get(sec, {}).items():
            if isinstance(s2, dict) and s2.get("forceInput"):
                continue
            if isinstance(s2, list) and s2 and isinstance(s2[0], str) and \
               s2[0] in ("LATENT", "MODEL", "CLIP", "VAE", "IMAGE", "CONDITIONING",
                         "AUDIO", "SAMPLER", "SIGMAS", "NOISE", "GUIDER", "VIDEO"):
                continue  # pure link-input zonder widget
            names.append(name)
    return names

links = {ln[0]: ln for ln in wf["links"]}
api = {}
skipped = []
for n in wf["nodes"]:
    t = n["type"]
    if t not in oi:
        skipped.append(t)
        continue
    inputs = {}
    wv = list(n.get("widgets_values") or [])
    wi = 0
    for slot in n.get("inputs", []):
        name = slot["name"]
        lid = slot.get("link")
        if lid is not None:
            src = links[lid]
            inputs[name] = [str(src[1]), src[2]]
        elif "widget" in slot and wi < len(wv):
            inputs[name] = wv[wi]
            wi += 1
    for name in widget_names(t):
        if name in inputs:
            continue
        if wi < len(wv):
            inputs[name] = wv[wi]
            wi += 1
    api[str(n["id"])] = {"class_type": t, "inputs": inputs}

# forceInput INT-slots die in `inputs` staan zonder link (unlinked optioneel):
# voor clip1 SaveLatent/StitchOutput is head_context_frames losgekoppeld ->
# node-defaults overnemen (0). ComfyUI lost dit zelf op; niets te doen.

with open(OUT_API, "w", encoding="utf-8") as f:
    json.dump(api, f, indent=2, ensure_ascii=False)
print(f"API-workflow: {OUT_API}")
print(f"  nodes: {len(api)}, overgeslagen (frontend-only): {sorted(set(skipped))}")
