#!/usr/bin/env python3
"""
Queue een API-workflow op een ComfyUI-server en wacht tot het klaar is.

Usage:
    python3 scripts/queue_comfyui_workflow.py <api.json> [--server URL] [--timeout SEC]
Voorbeelden:
    --server http://192.168.2.223:8389
"""
import argparse
import json
import sys
import time
import urllib.request


def post(url, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=60).read())


def get(url):
    return json.loads(urllib.request.urlopen(url, timeout=60).read())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("api_json")
    ap.add_argument("--server", default="http://192.168.2.223:8389")
    ap.add_argument("--timeout", type=int, default=3600)
    args = ap.parse_args()

    wf = json.load(open(args.api_json, encoding="utf-8"))
    try:
        resp = post(f"{args.server}/prompt", {"prompt": wf})
    except urllib.error.HTTPError as e:
        print("PROMPT AFWEZEN:", e.code)
        print(e.read().decode("utf-8", "replace")[:4000])
        sys.exit(1)
    pid = resp["prompt_id"]
    print("prompt_id:", pid, flush=True)

    start = time.time()
    last_print = 0
    while time.time() - start < args.timeout:
        time.sleep(15)
        hist = get(f"{args.server}/history/{pid}")
        if pid in hist:
            entry = hist[pid]
            status = entry.get("status", {})
            print(f"KLAAR na {int(time.time()-start)}s — status:",
                  status.get("status_str", "?"),
                  "completed" if status.get("completed") else "NOT-COMPLETED",
                  flush=True)
            for nid, out in entry.get("outputs", {}).items():
                for key in ("images", "videos", "gifs", "audio"):
                    for item in out.get(key, []):
                        print(f"  output[{nid}].{key}:", item.get("filename"))
            sys.exit(0 if status.get("completed") else 2)
        q = get(f"{args.server}/queue")
        running = q.get("queue_running") or []
        pending = len(q.get("queue_pending") or [])
        msg = f"running={len(running)} pending={pending} elapsed={int(time.time()-start)}s"
        if msg != last_print:
            print(msg, flush=True)
            last_print = msg
    print("TIMEOUT na", args.timeout, "s")
    sys.exit(3)


if __name__ == "__main__":
    main()
