"""Provenance for branch runs: code state, who ran it, and the size and SHA-256 of every input file read."""
import getpass
import hashlib
import json
import os
import platform
import subprocess
import sys


def git(root, *args):
    r = subprocess.run(["git", "-C", root, *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout


def code_state(root):
    """The commit, and whether anything under pipeline/ differs from it (modified, staged or untracked)."""
    commit = git(root, "rev-parse", "HEAD").strip()
    dirty = [ln[3:] for ln in git(root, "status", "--porcelain", "--untracked-files=all", "--", "pipeline").splitlines() if ln.strip()]
    dirty = [d for d in dirty if "__pycache__" not in d and not d.endswith(".pyc")]
    return {"commit": commit, "dirty": bool(dirty), "dirty_paths": dirty}


def who_ran(root, roster_name):
    try:
        git_user = git(root, "config", "user.name").strip() or None
    except RuntimeError:
        git_user = None
    try:
        os_user = getpass.getuser()
    except Exception:
        os_user = None
    return {"roster_name": roster_name, "git_user": git_user, "os_user": os_user}


def environment():
    return {"python": sys.version.split()[0], "implementation": platform.python_implementation(), "platform": platform.platform()}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class HashCache:
    """SHA-256 by path, reused while size and modification time are unchanged. Kept in the git-ignored runs folder."""

    def __init__(self, path):
        self.path = path
        self.data = {}
        if os.path.exists(path):
            try:
                with open(path) as fh:
                    self.data = json.load(fh)
            except (OSError, ValueError):
                self.data = {}

    def record(self, path):
        st = os.stat(path)
        hit = self.data.get(path)
        if hit and hit["size"] == st.st_size and hit["mtime_ns"] == st.st_mtime_ns:
            sha = hit["sha256"]
        else:
            sha = sha256_file(path)
            self.data[path] = {"size": st.st_size, "mtime_ns": st.st_mtime_ns, "sha256": sha}
        return {"path": path, "size": st.st_size, "sha256": sha}

    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(self.data, fh, indent=0, sort_keys=True)
        os.replace(tmp, self.path)


def input_records(read_paths, root, cache):
    """Every file the build read, except the committed code under pipeline/ (the commit covers that)."""
    code = os.path.realpath(os.path.join(root, "pipeline")) + os.sep
    out = []
    for p in sorted(read_paths):
        if p.startswith(code) and p.endswith(".py"):
            continue
        if os.path.isfile(p):
            out.append(cache.record(p))
    return out
