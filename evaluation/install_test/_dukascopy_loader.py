"""Read-only loader for the Trading Intelligence Engine's raw Dukascopy hourly tick JSON samples.

Decodes the jetta JSON tick format independently of the engine's own code (times/bids/asks arrays are
CUMULATIVE deltas). Cross-checked against the engine's python/dukascopy_audit/client.py::decode_tick_json on
2026-07-10T12 (first tick t=1783684800094 bid=1.14311 ask=1.14313; 3610 ticks in the hour).
Nothing is written to the source directory.
"""
import json
import os
from pathlib import Path

TICK_DIR = Path(os.environ["TIE_DUKASCOPY_TICK_DIR"])  # required: directory of hourly jetta tick JSON files (read-only)


def decode_tick_json(payload: dict) -> list[dict]:
    t = payload["timestamp"]
    bid_off = ask_off = 0
    out = []
    for i in range(len(payload["times"])):
        t += payload["times"][i]
        bid_off += payload["bids"][i]
        ask_off += payload["asks"][i]
        out.append({
            "ts_ms": t,
            "bid": round(payload["bid"] + bid_off * payload["multiplier"], 5),
            "ask": round(payload["ask"] + ask_off * payload["multiplier"], 5),
        })
    return out


def load_all_ticks() -> list[dict]:
    ticks: list[dict] = []
    for f in sorted(TICK_DIR.glob("*.json")):
        ticks.extend(decode_tick_json(json.loads(f.read_text())))
    ticks.sort(key=lambda r: r["ts_ms"])
    return ticks


if __name__ == "__main__":
    ticks = load_all_ticks()
    assert ticks[0]["ts_ms"] == 1783684800094 and ticks[0]["bid"] == 1.14311 and ticks[0]["ask"] == 1.14313
    print(f"loaded {len(ticks)} ticks from {TICK_DIR}; first={ticks[0]} last={ticks[-1]}")
