from __future__ import annotations

import json
import re
import time
import uuid
from collections import Counter
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__, static_folder=".")

HISTORY_FILE = Path(__file__).with_name("history.jsonl")
_history_count: int | None = None
_index_to_id: list[str | None] = []


def normalize_children(children: object) -> list[dict[str, float]]:
    if not isinstance(children, list) or not children:
        return []
    normalized: list[dict[str, float]] = []
    for child in children:
        if not isinstance(child, dict):
            return []
        child_id = child.get("id")
        child_ms = child.get("ms")
        if not isinstance(child_id, str) or not isinstance(child_ms, (int, float)):
            return []
        normalized.append({"id": child_id, "ms": float(child_ms)})
    by_id: dict[str, dict[str, float]] = {}
    for child in normalized:
        cid = child["id"]
        existing = by_id.get(cid)
        if existing is None or child["ms"] > existing["ms"]:
            by_id[cid] = child
    return sorted(by_id.values(), key=lambda item: (-item["ms"], item["id"]))


def upsert_child(children: list[dict[str, float]] | None, child_id: str, child_ms: float) -> list[dict[str, float]]:
    if not isinstance(child_id, str) or not isinstance(child_ms, (int, float)):
        return normalize_children(children or [])
    current = normalize_children(children or [])
    filtered = [child for child in current if child.get("id") != child_id]
    filtered.append({"id": child_id, "ms": float(child_ms)})
    return normalize_children(filtered)


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
    authorship: str | None = None,
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
        "authorship": authorship,
    }
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        if parent_id:
            append_child_action = {
                "action": "add_children",
                "child": entry["id"],
                "parent": parent_id,
                "ms": entry["ms"],
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
        "children": normalize_children(data.get("children")),
        "lastChildVisited": data.get("lastChildVisited") if isinstance(data.get("lastChildVisited"), str) else None,
        "authorship": data.get("authorship") if isinstance(data.get("authorship"), str) else None,
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
                child_ms = data.get("ms")
                if not isinstance(child_ms, (int, float)):
                    child_entry = entries_by_id.get(child_id)
                    child_ms = child_entry.get("ms") if isinstance(child_entry, dict) else None
                if child_ms is None:
                    continue
                parent_entry["children"] = upsert_child(parent_entry.get("children"), child_id, float(child_ms))
            elif action == "last_child_visited":
                parent_id = data.get("parent")
                child_id = data.get("child")
                if not isinstance(parent_id, str) or not isinstance(child_id, str):
                    continue
                parent_entry = entries_by_id.get(parent_id)
                if parent_entry is None:
                    continue
                parent_entry["lastChildVisited"] = child_id
                existing_children = normalize_children(parent_entry.get("children"))
                if any(child.get("id") == child_id for child in existing_children):
                    parent_entry["children"] = existing_children
                    continue
                child_ms = data.get("ms")
                if not isinstance(child_ms, (int, float)):
                    child_entry = entries_by_id.get(child_id)
                    child_ms = child_entry.get("ms") if isinstance(child_entry, dict) else None
                if child_ms is None:
                    parent_entry["children"] = existing_children
                    continue
                parent_entry["children"] = upsert_child(existing_children, child_id, float(child_ms))
    for entry in entries_by_index.values():
        entry["children"] = normalize_children(entry.get("children"))
        if not isinstance(entry.get("lastChildVisited"), str):
            entry["lastChildVisited"] = None
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


@app.route("/diff")
def diff_page():
    return send_from_directory(app.static_folder, "diff.html")


@app.route("/viewer")
def viewer_page():
    return send_from_directory(app.static_folder, "viewer.html")


@app.route("/wordcloud.js")
def wordcloud_js():
    return send_from_directory(app.static_folder, "wordcloud.js")


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
            payload.get("authorship"),
        )
        return jsonify({"ok": True, "entry": entry})
    entry_id = request.args.get("id")
    if entry_id:
        entry = read_entry_by_id(entry_id)
        if entry:
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
        keep = {"index", "id", "parent", "children", "pre_gen_index", "ts", "ms", "lastChildVisited"}
        entries = [{k: v for k, v in entry.items() if k in keep} for entry in entries]
    return jsonify({"entries": entries, "total": len(entries)})


_STOP_WORDS = set(
    "i,me,my,myself,we,our,ours,ourselves,you,your,yours,yourself,yourselves,"
    "he,him,his,himself,she,her,hers,herself,it,its,itself,they,them,their,"
    "theirs,themselves,what,which,who,whom,this,that,these,those,am,is,are,"
    "was,were,be,been,being,have,has,had,having,do,does,did,doing,a,an,the,"
    "and,but,if,or,because,as,until,while,of,at,by,for,with,about,against,"
    "between,into,through,during,before,after,above,below,to,from,up,down,"
    "in,out,on,off,over,under,again,further,then,once,here,there,when,where,"
    "why,how,all,any,both,each,few,more,most,other,some,such,no,nor,not,only,"
    "own,same,so,than,too,very,s,t,can,will,just,don,should,now,d,ll,m,o,re,"
    "ve,y,ain,aren,couldn,didn,doesn,hadn,hasn,haven,isn,ma,mightn,mustn,"
    "needn,shan,shouldn,wasn,weren,won,wouldn,also,would,could,said,like,one,"
    "know,get,go,well,way,got,much,even,make,say,think,see,come,take,want,"
    "give,use,find,tell,ask,seem,try,leave,call,keep,let,begin,show,hear,"
    "play,run,move,live,believe,hold,bring,happen,write,provide,sit,stand,"
    "lose,pay,meet,include,continue,set,learn,change,lead,understand,watch,"
    "follow,stop,create,speak,read,allow,add,spend,grow,open,walk,win,offer,"
    "remember,love,consider,appear,buy,wait,serve,die,send,expect,build,stay,"
    "fall,cut,reach,kill,remain,oh,im,thats,dont,ill,its,cant,didnt,hes,shes,"
    "youre,theyre,wont,isnt,ive,youve,id,heres,theres,whats,lets,whos,theyve,"
    "doesnt,wasnt,werent,havent,hasnt,hadnt,arent,couldnt,wouldnt,shouldnt,mustnt"
    .split(",")
)
_WORD_RE = re.compile(r"[a-zA-Z\u00C0-\u024F\u0400-\u04FF]+")
_wc_cache: dict[tuple[str, int], list] = {}


def _split_words(text: str) -> list[str]:
    return [w for w in (m.group().lower() for m in _WORD_RE.finditer(text)) if len(w) > 1 and w not in _STOP_WORDS]


@app.route("/history/wordcloud", methods=["POST"])
def history_wordcloud():
    payload = request.get_json(silent=True) or {}
    parent_id = payload.get("parent_id")
    if not isinstance(parent_id, str):
        return jsonify({"error": "parent_id required"}), 400

    entries = read_entries()
    by_id = {e["id"]: e for e in entries if e.get("id")}
    parent = by_id.get(parent_id)
    if not parent:
        return jsonify({"error": "parent not found"}), 404

    children = [by_id[c["id"]] for c in normalize_children(parent.get("children")) if c["id"] in by_id]
    cache_key = (parent_id, len(children))
    if cache_key in _wc_cache:
        return jsonify(_wc_cache[cache_key])

    base_text = parent.get("text", "")
    base_words = set(_split_words(base_text))
    freq: Counter[str] = Counter()

    for child in children:
        text = child.get("text", "")
        suffix = text[len(base_text):] if text.startswith(base_text) else text
        seen = set()
        for w in _split_words(suffix):
            if w not in base_words and w not in seen:
                seen.add(w)
                freq[w] += 1

    words = [[w, c] for w, c in freq.most_common(300) if c > 1]
    result = {"words": words, "children_count": len(children)}
    _wc_cache[cache_key] = result
    return jsonify(result)


def _compute_all_freqs(parent_id: str) -> tuple[Counter, int] | None:
    """Return (full_freq_counter, children_count) for a parent, or None."""
    entries = read_entries()
    by_id = {e["id"]: e for e in entries if e.get("id")}
    parent = by_id.get(parent_id)
    if not parent:
        return None
    children = [by_id[c["id"]] for c in normalize_children(parent.get("children")) if c["id"] in by_id]
    if not children:
        return Counter(), 0
    base_text = parent.get("text", "")
    base_words = set(_split_words(base_text))
    freq: Counter[str] = Counter()
    for child in children:
        text = child.get("text", "")
        suffix = text[len(base_text):] if text.startswith(base_text) else text
        seen = set()
        for w in _split_words(suffix):
            if w not in base_words and w not in seen:
                seen.add(w)
                freq[w] += 1
    return freq, len(children)


_diff_cache: dict[tuple[str, str, int, int], dict] = {}


@app.route("/history/wordcloud/diff", methods=["POST"])
def history_wordcloud_diff():
    payload = request.get_json(silent=True) or {}
    id_a = payload.get("id_a")
    id_b = payload.get("id_b")
    if not isinstance(id_a, str) or not isinstance(id_b, str):
        return jsonify({"error": "id_a and id_b required"}), 400

    res_a = _compute_all_freqs(id_a)
    if res_a is None:
        return jsonify({"error": "parent A not found"}), 404
    res_b = _compute_all_freqs(id_b)
    if res_b is None:
        return jsonify({"error": "parent B not found"}), 404

    freq_a, count_a = res_a
    freq_b, count_b = res_b

    cache_key = (id_a, id_b, count_a, count_b)
    if cache_key in _diff_cache:
        return jsonify(_diff_cache[cache_key])

    all_words = set(freq_a) | set(freq_b)
    diffs = []
    for w in all_words:
        pct_a = freq_a.get(w, 0) / max(count_a, 1)
        pct_b = freq_b.get(w, 0) / max(count_b, 1)
        d = pct_b - pct_a
        if abs(d) > 0.001:
            diffs.append([w, round(d, 6)])

    diffs.sort(key=lambda x: abs(x[1]), reverse=True)
    diffs = diffs[:300]

    result = {
        "diffs": diffs,
        "count_a": count_a,
        "count_b": count_b,
        "words_a": len(freq_a),
        "words_b": len(freq_b),
    }
    _diff_cache[cache_key] = result
    return jsonify(result)


@app.route("/history/bulk", methods=["POST"])
def history_bulk():
    payload = request.get_json(silent=True) or {}
    ids = payload.get("ids", [])
    if not isinstance(ids, list):
        return jsonify({"error": "ids must be a list"}), 400
    entries = read_entries()
    by_id = {e["id"]: e for e in entries if e.get("id")}
    results = {}
    for entry_id in ids:
        if isinstance(entry_id, str) and entry_id in by_id:
            results[entry_id] = by_id[entry_id]
    return jsonify({"entries": results})


@app.route("/history/action", methods=["POST"])
def history_action():
    payload = request.get_json(silent=True) or {}
    action = payload.get("action")
    if action != "last_child_visited":
        return jsonify({"error": "unknown action"}), 400
    parent_id = payload.get("parent")
    child_id = payload.get("child")
    if not isinstance(parent_id, str) or not isinstance(child_id, str):
        return jsonify({"error": "invalid ids"}), 400
    ms_value = payload.get("ms")
    action_ms = float(ms_value) if isinstance(ms_value, (int, float)) else time.time() * 1000.0
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY_FILE.open("a", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "action": "last_child_visited",
                    "parent": parent_id,
                    "child": child_id,
                    "ms": action_ms,
                },
                ensure_ascii=False,
            )
            + "\n"
        )
    return jsonify(
        {"ok": True, "action": "last_child_visited", "parent": parent_id, "child": child_id, "ms": action_ms}
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
