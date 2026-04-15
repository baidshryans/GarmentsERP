import re, json, sys

src = open(r"D:/Jewel India ERP/frontend/src/App.jsx", encoding="utf-8").read()
# Match: { path: "...", heading: ..., component: ... }
pattern = re.compile(r'\{\s*path:\s*"([^"]+)"\s*,\s*heading:\s*([^,]+?)\s*,', re.M)
routes = []
for m in pattern.finditer(src):
    path = m.group(1)
    # skip parameterized routes (need real ids) and ones with wildcards
    if ":" in path or "*" in path:
        continue
    routes.append(path)
routes = sorted(set(routes))
print(f"Extracted {len(routes)} static routes", file=sys.stderr)
json.dump(routes, open(r"D:/Jewel India ERP/test-runs/routes.json","w"), indent=2)
