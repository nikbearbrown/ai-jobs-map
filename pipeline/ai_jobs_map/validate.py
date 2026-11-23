"""A small JSON Schema (2020-12 subset) validator, standard library only: $ref (to other files and #/$defs), allOf,
anyOf, oneOf, const, enum, type, required, properties, additionalProperties, items, minItems, maxItems, pattern,
minimum, maximum. Enough for the AI jobs map's own schemas; not a general implementation."""
import json
import os
import re

_CACHE = {}


def _load(path):
    path = os.path.abspath(path)
    if path not in _CACHE:
        _CACHE[path] = json.load(open(path))
    return _CACHE[path]


def _resolve(ref, base):
    file_part, _, frag = ref.partition("#")
    target = os.path.join(os.path.dirname(base), file_part) if file_part else base
    node = _load(target)
    for part in [p for p in frag.split("/") if p]:
        node = node[part]
    return node, target


def _type_ok(v, t):
    return {"object": isinstance(v, dict), "array": isinstance(v, list), "string": isinstance(v, str),
            "boolean": isinstance(v, bool), "null": v is None,
            "integer": isinstance(v, int) and not isinstance(v, bool),
            "number": isinstance(v, (int, float)) and not isinstance(v, bool)}[t]


def _check(v, s, base, path, errs):
    if s is True or s == {}:
        return
    if "$ref" in s:
        node, nbase = _resolve(s["$ref"], base)
        _check(v, node, nbase, path, errs)
    for sub in s.get("allOf", []):
        _check(v, sub, base, path, errs)
    if "anyOf" in s and not any(not _errs(v, sub, base, path) for sub in s["anyOf"]):
        errs.append(f"{path}: matches none of anyOf")
    if "oneOf" in s:
        ok = [sub for sub in s["oneOf"] if not _errs(v, sub, base, path)]
        if len(ok) != 1:
            detail = "" if ok else " | " + "; ".join(_errs(v, s["oneOf"][0], base, path)[:2])
            errs.append(f"{path}: matches {len(ok)} of oneOf (needs exactly 1){detail}")
    if "const" in s and v != s["const"]:
        errs.append(f"{path}: {v!r} != const {s['const']!r}")
    if "enum" in s and v not in s["enum"]:
        errs.append(f"{path}: {v!r} not in enum")
    if "type" in s:
        ts = s["type"] if isinstance(s["type"], list) else [s["type"]]
        if not any(_type_ok(v, t) for t in ts):
            errs.append(f"{path}: type {type(v).__name__} not in {ts}")
            return
    if isinstance(v, dict):
        for k in s.get("required", []):
            if k not in v:
                errs.append(f"{path}: missing required {k!r}")
        props = s.get("properties", {})
        for k, sub in props.items():
            if k in v:
                _check(v[k], sub, base, f"{path}.{k}", errs)
        ap = s.get("additionalProperties", True)
        for k in v:
            if k not in props:
                if ap is False:
                    errs.append(f"{path}: unexpected property {k!r}")
                elif isinstance(ap, dict):
                    _check(v[k], ap, base, f"{path}.{k}", errs)
    if isinstance(v, list):
        if "minItems" in s and len(v) < s["minItems"]:
            errs.append(f"{path}: fewer than {s['minItems']} items")
        if "maxItems" in s and len(v) > s["maxItems"]:
            errs.append(f"{path}: more than {s['maxItems']} items")
        if isinstance(s.get("items"), dict):
            for i, x in enumerate(v):
                _check(x, s["items"], base, f"{path}[{i}]", errs)
    if isinstance(v, str) and "pattern" in s and not re.search(s["pattern"], v):
        errs.append(f"{path}: {v!r} does not match {s['pattern']}")
    if _type_ok(v, "number"):
        if "minimum" in s and v < s["minimum"]:
            errs.append(f"{path}: {v} < minimum {s['minimum']}")
        if "maximum" in s and v > s["maximum"]:
            errs.append(f"{path}: {v} > maximum {s['maximum']}")


def _errs(v, s, base, path):
    e = []
    _check(v, s, base, path, e)
    return e


def validate(instance, schema_path):
    schema_path = os.path.abspath(schema_path)
    return _errs(instance, _load(schema_path), schema_path, "$")
