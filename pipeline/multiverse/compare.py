"""Compare two output folders file by file, byte for byte, after blanking values that are expected to differ
(the run time, and for code-change checks the config hash). Used to show that BR-0000 reproduces the main build
and that a refactor left every output unchanged.

    python3 -I pipeline/multiverse/compare.py A B [--mask computed_at --mask config_sha256]
"""
import os
import re
import sys


def _masked(data, keys):
    for k in keys:
        data = re.sub(rb'("' + k.encode() + rb'": )"[^"]*"', rb'\1"<masked>"', data)
    return data


def compare_trees(a, b, mask=("computed_at",)):
    """Returns {"identical": [...], "different": [(path, first differing line no, line in a, line in b)],
    "only_in_a": [...], "only_in_b": [...]} with paths relative to each folder."""
    def files(root):
        out = set()
        for d, _, fs in os.walk(root):
            for f in fs:
                out.add(os.path.relpath(os.path.join(d, f), root))
        return out
    fa, fb = files(a), files(b)
    res = {"identical": [], "different": [], "only_in_a": sorted(fa - fb), "only_in_b": sorted(fb - fa)}
    for rel in sorted(fa & fb):
        with open(os.path.join(a, rel), "rb") as fh:
            x = _masked(fh.read(), mask)
        with open(os.path.join(b, rel), "rb") as fh:
            y = _masked(fh.read(), mask)
        if x == y:
            res["identical"].append(rel)
            continue
        xl, yl = x.splitlines(), y.splitlines()
        n = next((i for i in range(min(len(xl), len(yl))) if xl[i] != yl[i]), min(len(xl), len(yl)))
        res["different"].append((rel, n + 1, (xl[n] if n < len(xl) else b"<end>")[:200].decode(errors="replace"),
                                 (yl[n] if n < len(yl) else b"<end>")[:200].decode(errors="replace")))
    return res


def summary(res):
    lines = [f"identical: {len(res['identical'])} files; different: {len(res['different'])}; "
             f"only in first: {len(res['only_in_a'])}; only in second: {len(res['only_in_b'])}"]
    for rel, n, x, y in res["different"][:20]:
        lines += [f"  {rel} line {n}:", f"    first:  {x}", f"    second: {y}"]
    for k in ("only_in_a", "only_in_b"):
        lines += [f"  {k}: {p}" for p in res[k][:20]]
    return "\n".join(lines)


if __name__ == "__main__":
    args = sys.argv[1:]
    mask = [args[i + 1] for i, x in enumerate(args) if x == "--mask"] or ["computed_at"]
    paths = [x for i, x in enumerate(args) if x != "--mask" and (i == 0 or args[i - 1] != "--mask")]
    r = compare_trees(paths[0], paths[1], mask)
    print(summary(r))
    sys.exit(0 if not (r["different"] or r["only_in_a"] or r["only_in_b"]) else 1)
