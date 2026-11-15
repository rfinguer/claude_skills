#!/usr/bin/env python3
"""
Look up the exact Sigma workbook-spec schema for a set of YAML keys, using Sigma's PUBLIC OpenAPI file
(no credentials needed). Use it before guessing a key: the importer rejects unknown keys / enum values.

usage:
  python sigma_schema_probe.py download                       # saves sigma_openapi.json next to this script
  python sigma_schema_probe.py keys conditionalFormats,yAxis2  # where each key appears + its compact schema
  python sigma_schema_probe.py controls                        # every controlType variant and its fields
  python sigma_schema_probe.py elements                        # every element kind and its fields
"""
import json, os, sys, urllib.request

URL = "https://assets.sigmacomputing.com/openapi/public-rest-api/sigma-computing-public-rest-api.json"
HERE = os.path.dirname(os.path.abspath(__file__))
FILE = os.path.join(HERE, "sigma_openapi.json")


def load():
    if not os.path.exists(FILE):
        sys.exit("run 'download' first")
    return json.load(open(FILE, encoding="utf-8"))


def comp(s, d, dep=0, maxd=5):
    if dep > maxd or not isinstance(s, dict):
        return "..."
    if "$ref" in s:
        return "$" + s["$ref"].split("/")[-1]
    if "enum" in s:
        return "enum" + json.dumps(s["enum"])
    for k in ("allOf", "oneOf", "anyOf"):
        if k in s:
            return k + "[" + " | ".join(comp(x, d, dep + 1, maxd) for x in s[k]) + "]"
    if s.get("type") == "array":
        return "array<" + comp(s.get("items", {}), d, dep + 1, maxd) + ">"
    if "properties" in s:
        req = s.get("required", [])
        return "{" + ", ".join(p + ("*" if p in req else "") + ": " + comp(v, d, dep + 1, maxd)
                               for p, v in s["properties"].items()) + "}"
    return s.get("type", "?")


def root(d):
    return d["paths"]["/v2/workbooks/{workbookId}/spec"]["put"]["requestBody"]["content"]["application/json"]["schema"]


def keys(d, want):
    seen, refs = set(), set()

    def walk(s, path):
        if isinstance(s, dict) and "$ref" in s:
            n = s["$ref"].split("/")[-1]
            if n not in refs:
                refs.add(n)
                walk(d["components"]["schemas"].get(n, {}), path + "/$" + n)
            return
        if isinstance(s, dict):
            for p, v in (s.get("properties") or {}).items():
                if p in want:
                    k = (p, json.dumps(v, sort_keys=True)[:300])
                    if k not in seen:
                        seen.add(k)
                        print(f"### {p} @ {path[-100:]}\n  siblings: {sorted(s['properties'])}\n  {comp(v, d)[:3000]}\n")
            for k, v in s.items():
                walk(v, path + "/" + k if k not in ("allOf", "oneOf", "anyOf", "items") else path)
        elif isinstance(s, list):
            for v in s:
                walk(v, path)
    walk(root(d), "")


def variants(s):
    if isinstance(s, dict) and "oneOf" in s:
        for x in s["oneOf"]:
            yield from variants(x)
    elif isinstance(s, dict) and "allOf" in s and any(isinstance(x, dict) and "oneOf" in x for x in s["allOf"]):
        base = [x for x in s["allOf"] if not (isinstance(x, dict) and "oneOf" in x)]
        for o in [x for x in s["allOf"] if isinstance(x, dict) and "oneOf" in x]:
            for v in variants(o):
                yield {"allOf": base + [v]}
    else:
        yield s


def flat(s, acc, req):
    if isinstance(s, dict) and "$ref" not in s:
        for x in s.get("allOf", []):
            flat(x, acc, req)
        for p, v in s.get("properties", {}).items():
            acc.setdefault(p, v)
        req.update(s.get("required", []))


def dump_variants(d, schema_names, tag):
    for name in schema_names:
        for v in variants(d["components"]["schemas"][name]):
            acc, req = {}, set()
            flat(v, acc, req)
            t = acc.get(tag, {}).get("enum")
            if not t:
                continue
            print(f"==== {tag} {t}")
            for p, val in acc.items():
                if p != tag:
                    print(f"   {p}{'*' if p in req else ''}: {comp(val, d, maxd=4)[:700]}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    if sys.argv[1] == "download":
        urllib.request.urlretrieve(URL, FILE)
        print("saved", FILE, os.path.getsize(FILE), "bytes")
    elif sys.argv[1] == "keys":
        keys(load(), set(sys.argv[2].split(",")))
    elif sys.argv[1] == "controls":
        dump_variants(load(), ["Control"], "controlType")
    elif sys.argv[1] == "elements":
        dump_variants(load(), ["CommonElement", "Table"], "kind")
    else:
        sys.exit(__doc__)
