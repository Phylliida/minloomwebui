from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__, static_folder=".")

HISTORY_FILE = Path(__file__).with_name("history.jsonl")
_history_count: int | None = None
_index_to_id: list[str | None] = []


def history_count() -> int:
    global _history_count, _index_to_id
    if _history_count is None:
        _history_count = 0
        _index_to_id = []
        if HISTORY_FILE.exists():
            with HISTORY_FILE.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(data, dict) and data.get("action"):
                        continue
                    _history_count += 1
                    _index_to_id.append(data.get("id"))
    return _history_count


def append_entry(
    text: str,
    entry_id: str | None = None,
    ts: float | None = None,
    ms: float | None = None,
    params: dict | None = None,
    pre_gen_index: int | None = None,
    parent: str | int | None = None,
) -> dict:
    global _history_count, _index_to_id
    idx = history_count()
    parent_id: str | None = None
    if parent is not None:
        parent_id = str(parent)
        if parent_id == "":
            parent_id = None
    elif pre_gen_index is not None:
        try:
            parent_idx = int(pre_gen_index)
            if 0 <= parent_idx < idx:
                parent_id = _index_to_id[parent_idx] if parent_idx < len(_index_to_id) else None
        except (TypeError, ValueError):
            parent_id = None
    elif idx > 0:
        previous_idx = idx - 1
        parent_id = _index_to_id[previous_idx] if previous_idx < len(_index_to_id) else None
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
        "parent": parent_id,
    }
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        if parent_id:
            append_child_action = {
                "action": "add_children",
                "child": entry["id"],
                "parent": parent_id,
            }
            fh.write(json.dumps(append_child_action, ensure_ascii=False) + "\n")
    _history_count += 1
    _index_to_id.append(entry["id"])
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
        "parent": data.get("parent") if isinstance(data.get("parent"), str) else None,
        "children": data.get("children") if isinstance(data.get("children"), list) else [],
    }


def read_entries() -> list[dict]:
    entries_by_index: dict[int, dict] = {}
    entries_by_id: dict[str, dict] = {}
    if not HISTORY_FILE.exists():
        return []
    with HISTORY_FILE.open("r", encoding="utf-8") as fh:
        for fallback_idx, line in enumerate(fh):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(data, dict):
                continue
            if "action" not in data:
                entry = normalize_entry(data, fallback_idx)
                try:
                    idx_key = int(entry["index"])
                except (TypeError, ValueError):
                    idx_key = fallback_idx
                entry["index"] = idx_key
                entries_by_index[idx_key] = entry
                if entry.get("id"):
                    entries_by_id[entry["id"]] = entry
                continue
            action = data.get("action")
            if action == "add_children":
                parent_id = data.get("parent")
                child_id = data.get("child")
                if not isinstance(parent_id, str) or not isinstance(child_id, str):
                    continue
                parent_entry = entries_by_id.get(parent_id)
                if parent_entry is None:
                    continue
                parent_entry.setdefault("children", [])
                if child_id not in parent_entry["children"]:
                    parent_entry["children"].append(child_id)
    for entry in entries_by_index.values():
        entry.setdefault("children", [])
        entry["children"] = sorted([c for c in entry["children"] if isinstance(c, str)])
    return [entries_by_index[idx] for idx in sorted(entries_by_index)]


def read_entry_by_id(entry_id: str) -> dict | None:
    if not HISTORY_FILE.exists():
        return None
    target = str(entry_id)
    for entry in read_entries():
        entry_id_value = entry.get("id")
        if entry_id_value is None:
            continue
        if str(entry_id_value) == target:
            return entry
    return None


def read_entry_by_index(idx: int) -> dict | None:
    if idx is None or idx < 0:
        return None
    for entry in read_entries():
        try:
            if int(entry.get("index")) == idx:
                return entry
        except (TypeError, ValueError):
            continue
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
            payload.get("parent"),
        )
        return jsonify({"ok": True, "entry": entry})
    entry_id = request.args.get("id")
    print(entry_id)
    if entry_id:
        entry = read_entry_by_id(entry_id)
        if entry:
            print(entry)
            return jsonify({"entry": entry, "total": history_count()})
        return jsonify({"error": "not found"}), 404
    if "index" in request.args:
        try:
            idx = int(request.args.get("index"))
        except (TypeError, ValueError):
            idx = None
        entry = read_entry_by_index(idx) if idx is not None else None
        if entry:
            return jsonify({"entry": entry, "total": history_count()})
        return jsonify({"error": "not found"}), 404
    if request.args.get("latest"):
        total = history_count()
        entry = read_entry_by_index(total - 1)
        if entry:
            return jsonify({"entry": entry, "total": total})
        return jsonify({"error": "not found"}), 404
    entries = read_entries()
    if request.args.get("meta"):
        keep = {"index", "id", "parent", "children", "pre_gen_index", "ts", "ms"}
        entries = [{k: v for k, v in entry.items() if k in keep} for entry in entries]
    return jsonify({"entries": entries, "total": len(entries)})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
