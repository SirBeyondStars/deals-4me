# analyze_mb_json.py
import json, os, collections
PATH = "mb_items.json"

if not os.path.exists(PATH):
    print("mb_items.json not found next to this script.")
    raise SystemExit(1)

data = json.load(open(PATH, "r", encoding="utf-8"))

def walk(node, path=(), samples=5, freq=None, rows=None):
    if freq is None: freq = collections.Counter()
    if rows is None: rows = []
    if isinstance(node, dict):
        for k, v in node.items():
            freq["/".join(path + (k,))] += 1
            walk(v, path + (k,), samples, freq, rows)
    elif isinstance(node, list):
        for i, v in enumerate(node[:samples]):  # sample a few
            walk(v, path + (f"[{i}]",), samples, freq, rows)
        rows.append(("/".join(path) + "  (list_len)", len(node)))
    else:
        rows.append(("/".join(path), str(node)[:120]))
    return freq, rows

def top_freq(freq, n=30):
    print("\n=== Top key paths (by frequency) ===")
    for k, c in freq.most_common(n):
        print(f"{c:5}  {k}")

def show_price_like(rows):
    print("\n=== Sample fields that look like titles/prices ===")
    for p, v in rows:
        pl = p.lower()
        if any(w in pl for w in ["title","name","description","price","sale","promo","offer"]) and not p.endswith("(list_len)"):
            print(f"{p}: {v}")

freq, rows = walk(data)
top_freq(freq, 40)
show_price_like(rows)
print("\nTip: if you see a path like '.../items/[0]/name' and '.../items/[0]/price', tell me both paths.")
