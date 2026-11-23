"""Read and write guard for branch runs.

For the length of a branch run, Python's file functions are wrapped so that:
  * nothing under a locked path (the classifier study's data, the preregistration) can be opened or listed;
  * nothing can be written outside the run folder, so a branch can never change the main outputs or any
    private file the main build writes;
  * every file read is recorded, for the provenance.

It guards this code, not a sandbox: a subprocess or a C extension could get round it. The build is pure Python
and the tests prove the guard for the functions the build uses."""
import builtins
import gzip
import io
import os

from .common import under

WRITE_MODE_CHARS = set("wax+")


class GuardViolation(PermissionError):
    pass


class Guard:
    def __init__(self, locked_roots, write_roots):
        self.locked = [os.path.realpath(r) for r in locked_roots]
        self.write = [os.path.realpath(r) for r in write_roots]
        self.reads = set()
        self._saved = None

    # -- checks
    def _path(self, p):
        if isinstance(p, int):
            return None
        return os.path.realpath(os.fsdecode(os.fspath(p)))

    def check_read(self, p):
        rp = self._path(p)
        if rp is None:
            return
        if under(rp, self.locked):
            raise GuardViolation(f"branch runs may not read the locked path {rp}")
        if os.path.isfile(rp):
            self.reads.add(rp)

    def check_write(self, p):
        rp = self._path(p)
        if rp is None:
            return
        if under(rp, self.locked):
            raise GuardViolation(f"branch runs may not touch the locked path {rp}")
        if not under(rp, self.write):
            raise GuardViolation(f"branch runs may write only inside the run folder, not {rp}")

    # -- wrappers
    def _wrap(self):
        o = self._saved
        guard = self

        def g_open(file, mode="r", *a, **k):
            if WRITE_MODE_CHARS & set(mode):
                guard.check_write(file)
            else:
                guard.check_read(file)
            return o["open"](file, mode, *a, **k)

        def g_gzip_open(filename, mode="rb", *a, **k):
            if isinstance(filename, (str, bytes, os.PathLike)):
                if WRITE_MODE_CHARS & set(mode):
                    guard.check_write(filename)
                else:
                    guard.check_read(filename)
            return o["gzip_open"](filename, mode, *a, **k)

        def g_listdir(path="."):
            guard.check_read(path)
            return o["listdir"](path)

        def g_scandir(path="."):
            guard.check_read(path)
            return o["scandir"](path)

        def g_two(name):
            def f(src, dst, *a, **k):
                guard.check_write(src)
                guard.check_write(dst)
                return o[name](src, dst, *a, **k)
            return f

        def g_one_write(name):
            def f(path, *a, **k):
                guard.check_write(path)
                return o[name](path, *a, **k)
            return f

        def g_os_open(path, flags, *a, **k):
            if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC):
                guard.check_write(path)
            else:
                guard.check_read(path)
            return o["os_open"](path, flags, *a, **k)

        return {
            (builtins, "open"): g_open, (io, "open"): g_open, (gzip, "open"): g_gzip_open,
            (os, "listdir"): g_listdir, (os, "scandir"): g_scandir, (os, "open"): g_os_open,
            (os, "replace"): g_two("replace"), (os, "rename"): g_two("rename"),
            (os, "remove"): g_one_write("remove"), (os, "unlink"): g_one_write("unlink"),
            (os, "rmdir"): g_one_write("rmdir"), (os, "mkdir"): g_one_write("mkdir"),
        }

    def __enter__(self):
        self._saved = {"open": builtins.open, "gzip_open": gzip.open, "listdir": os.listdir, "scandir": os.scandir,
                       "os_open": os.open, "replace": os.replace, "rename": os.rename, "remove": os.remove,
                       "unlink": os.unlink, "rmdir": os.rmdir, "mkdir": os.mkdir}
        self._originals = {}
        for (mod, name), fn in self._wrap().items():
            self._originals[(mod, name)] = getattr(mod, name)
            setattr(mod, name, fn)
        return self

    def __exit__(self, *exc):
        for (mod, name), fn in self._originals.items():
            setattr(mod, name, fn)
        return False
