from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__, static_folder=".")

HISTORY_FILE = Path(__file__).with_name("history.jsonl")
_history_count: int | None = None


def history_count() -> int:
    global _history_count
    if _history_count is None:
        _history_count = 0
        if HISTORY_FILE.exists():
            with HISTORY_FILE.open("r", encoding="utf-8") as fh:
                for _ in fh:
                    _history_count += 1
    return _history_count


def append_entry(
    text: str,
    entry_id: str | None = None,
    ts: float | None = None,
    ms: float | None = None,
    params: dict | None = None,
    pre_gen_index: int | None = None,
) -> dict:
    global _history_count
    idx = history_count()
    if ms is None:
        ms = (ts if ts is not None else time.time()) * 1000.0
    if ts is None:
        ts = ms / 1000.0
    entry = {
        "index": idx,
        "ts": ts if ts is not None else time.time(),
        "ms": ms,
        "text": text,
        "id": entry_id or str(uuid.uuid4()),
        "params": params or {},
        "pre_gen_index": pre_gen_index,
    }
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    _history_count += 1
    return entry


def normalize_entry(data: dict, fallback_index: int) -> dict:
    return {
        "index": data.get("index", fallback_index),
        "ts": data.get("ts"),
        "ms": data.get("ms") if data.get("ms") is not None else (data.get("ts") or 0) * 1000.0,
        "text": data.get("text", ""),
        "id": data.get("id"),
        "params": data.get("params") or {},
        "pre_gen_index": data.get("pre_gen_index"),
    }


def read_entries() -> list[dict]:
    entries: list[dict] = []
    if not HISTORY_FILE.exists():
        return entries
    with HISTORY_FILE.open("r", encoding="utf-8") as fh:
        for fallback_idx, line in enumerate(fh):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            entries.append(normalize_entry(data, fallback_idx))
    return entries


def read_entry_by_id(entry_id: str) -> dict | None:
    if not HISTORY_FILE.exists():
        return None
    with HISTORY_FILE.open("r", encoding="utf-8") as fh:
        for fallback_idx, line in enumerate(fh):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if data.get("id") == entry_id:
                return normalize_entry(data, fallback_idx)
    return None


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "loomui.html")


@app.route("/calendar")
def calendar():
    return send_from_directory(app.static_folder, "calendar.html")


@app.route("/history", methods=["GET", "POST"])
def history():
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
        text = payload.get("text", "")
        entry = append_entry(
            text,
            payload.get("id"),
            payload.get("ts"),
            payload.get("ms"),
            payload.get("params"),
            payload.get("pre_gen_index"),
        )
        return jsonify({"ok": True, "entry": entry})
    entry_id = request.args.get("id")
    if entry_id:
        entry = read_entry_by_id(entry_id)
        if entry:
            return jsonify({"entry": entry})
        return jsonify({"error": "not found"}), 404
    entries = read_entries()
    return jsonify({"entries": entries})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
