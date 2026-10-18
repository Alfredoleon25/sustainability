#!/usr/bin/env python3
"""Local Chalk query API for the Upstairs demo. Secret stays on the server."""
from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
PORT = int(os.environ.get("CHALK_PORT", "8766"))


def load_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip())


load_env()

CLIENT = None
try:
    from chalk.client import ChalkClient
    from features import Block

    if os.environ.get("CHALK_CLIENT_ID") and os.environ.get("CHALK_CLIENT_SECRET"):
        CLIENT = ChalkClient(
            client_id=os.environ["CHALK_CLIENT_ID"],
            client_secret=os.environ["CHALK_CLIENT_SECRET"],
            branch=os.environ.get("CHALK_BRANCH", "upstairs"),
        )
except Exception as exc:
    print("Chalk client not ready:", exc)


def local_features(q: dict) -> dict:
    rain = float(q.get("rain", 0))
    sewer = float(q.get("sewer", 1.2))
    past = int(float(q.get("past", 0)))
    depth = float(q.get("depth", 0))
    walk = float(q.get("walk", 0))
    cap = sewer / (1 + 0.18 * min(past, 10))
    flood = round(max(0.0, rain - cap) * 0.35, 3)
    starlink = flood >= 0.2 or depth >= 0.3
    rescue = flood >= 0.5 or depth >= 0.5 or walk < 0
    call = flood >= 0.35 or depth >= 0.3
    if rescue:
        action = "rescue"
    elif call:
        action = "call"
    else:
        action = "none"
    return {
        "source": "local",
        "goes19_rain_in_hr": rain,
        "flood_30min_ft": flood,
        "starlink_reachable": starlink,
        "reach_path": "starlink" if starlink else "cellular",
        "should_call": call,
        "should_rescue": rescue,
        "action": action,
    }


def chalk_features(q: dict) -> dict:
    if CLIENT is None:
        raise RuntimeError("no chalk client")
    lat = float(q.get("lat", 0))
    lng = float(q.get("lng", 0))
    rain = float(q.get("rain", 0))
    sewer = float(q.get("sewer", 1.2))
    past = int(float(q.get("past", 0)))
    depth = float(q.get("depth", 0))
    walk = float(q.get("walk", 0))
    elev = float(q.get("elev", 0))
    res = CLIENT.query(
        input={
            Block.id: f"{lat:.4f},{lng:.4f}",
            Block.lat: lat,
            Block.lng: lng,
            Block.elevation_ft: elev,
            Block.rain_in_hr: rain,
            Block.sewer_in_hr: sewer,
            Block.past_floods: past,
            Block.depth_now_ft: depth,
            Block.walk_minutes: walk,
        },
        output=[
            Block.goes19_rain_in_hr,
            Block.flood_30min_ft,
            Block.starlink_reachable,
            Block.reach_path,
            Block.should_call,
            Block.should_rescue,
            Block.action,
        ],
        branch=os.environ.get("CHALK_BRANCH", "upstairs"),
    )
    data = res.get_feature_value if hasattr(res, "get_feature_value") else None

    def val(feat, fallback=None):
        try:
            if data:
                v = res.get_feature_value(feat)
                return fallback if v is None else v
            name = str(feat).split(".")[-1]
            return getattr(res, name, fallback)
        except Exception:
            return fallback

    out = {
        "source": "chalk",
        "goes19_rain_in_hr": val(Block.goes19_rain_in_hr, rain),
        "flood_30min_ft": val(Block.flood_30min_ft, 0),
        "starlink_reachable": bool(val(Block.starlink_reachable, False)),
        "reach_path": val(Block.reach_path, "cellular"),
        "should_call": bool(val(Block.should_call, False)),
        "should_rescue": bool(val(Block.should_rescue, False)),
        "action": val(Block.action, "none"),
    }
    return out


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print("[chalk]", fmt % args)

    def _send(self, code: int, body: dict):
        raw = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._send(200, {"ok": True, "chalk": CLIENT is not None})
            return
        if parsed.path != "/block":
            self._send(404, {"error": "not found"})
            return
        q = {k: v[0] for k, v in parse_qs(parsed.query).items() if v}
        try:
            self._send(200, chalk_features(q))
        except Exception as exc:
            body = local_features(q)
            body["chalk_error"] = str(exc)
            self._send(200, body)


if __name__ == "__main__":
    print(f"Chalk query server on http://127.0.0.1:{PORT}  (client={'yes' if CLIENT else 'no'})")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
