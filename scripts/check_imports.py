#!/usr/bin/env python3
"""Compile every script in scripts/, and import the ones that can be imported safely.

WHY. The refresh scripts run only on their schedules, so a syntax error, a renamed import or
a module-level side effect in one of them waits days to be found, and is found as a red
scheduled job rather than a red push. That is exactly how the 19 Aug 2026 site-refresh
failure surfaced: scripts/monitor_root.py resolved the ai-monitor checkout at import,
build.py imported it for three constants and nothing exercised that import until the
schedule did, about thirty hours later.

TWO PASSES, because importing is not free of consequence.

  compile   every script. Catches syntax errors, and cannot run anything.
  import    only scripts that are safe to import: either they guard their work behind
            `if __name__ == "__main__"`, or something else here imports them, which makes
            being imported their normal use. Importing runs the module body and nothing
            else, which is the part that has to hold on a machine that is not Magnus's
            laptop.

That second clause is not a convenience. monitor_root.py is a library with no main guard and
no work of its own, so a guard-only rule left the one file whose import broke the site as the
one file the check did not import.

The guard is what makes the second pass safe, and the first version of this file did not
check for it: it imported everything, which RAN refresh_vocabulary.py and refresh_capability.py
and rewrote two data files. A check that edits the tree it is checking is worse than no check.

Scripts without the guard are listed rather than passed over in silence -- an unimportable
script is uncovered, and uncovered is a fact about this check, not a property of the script.
"""
from __future__ import annotations

import ast
import importlib.util
import py_compile
import sys
import traceback
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

SKIP = {"check_imports.py"}


def imported_by_others(names: set[str]) -> set[str]:
    """Module names that another script here imports, so importing them is their normal use.

    Reads build.py as well: it sits at the repository root and is the reason monitor_root.py
    has to be importable in the first place.
    """
    used: set[str] = set()
    sources = list(SCRIPTS.glob("*.py")) + [SCRIPTS.parent / "build.py"]
    for f in sources:
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                used.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                used.add(node.module.split(".")[0])
    return used & names


def has_main_guard(path: Path) -> bool:
    """True if the module's work sits behind `if __name__ == "__main__"`.

    Parsed rather than grepped: a string or a comment containing __main__ is not a guard.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return False
    for node in tree.body:
        if not isinstance(node, ast.If):
            continue
        for sub in ast.walk(node.test):
            if isinstance(sub, ast.Name) and sub.id == "__name__":
                return True
    return False


def main() -> int:
    broken: list[tuple[str, str]] = []
    unguarded: list[str] = []
    imported = 0
    library = imported_by_others({f.stem for f in SCRIPTS.glob("*.py")})

    for f in sorted(SCRIPTS.glob("*.py")):
        if f.name in SKIP:
            continue

        try:
            py_compile.compile(str(f), doraise=True, cfile=str(f.with_suffix(".pyc.check")))
        except py_compile.PyCompileError as e:
            broken.append((f.name, str(e).strip().splitlines()[-1]))
            print(f"  FAIL     {f.name}  (does not compile)")
            continue
        finally:
            f.with_suffix(".pyc.check").unlink(missing_ok=True)

        if not (has_main_guard(f) or f.stem in library):
            unguarded.append(f.name)
            print(f"  compiled {f.name}  (no main guard, imported by nothing)")
            continue

        spec = importlib.util.spec_from_file_location(f.stem, f)
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except BaseException:
            broken.append((f.name, traceback.format_exc().strip().splitlines()[-1]))
            print(f"  FAIL     {f.name}  (does not import)")
            continue
        imported += 1
        print(f"  ok       {f.name}")

    print(f"\n{imported} imported · {len(unguarded)} compiled only · {len(broken)} broken")
    if unguarded:
        print("\nNOT import-checked: their work runs at module level and nothing imports them.")
        for name in unguarded:
            print(f"  {name}")
        print("Importing one would run it. Move the work under a main guard to cover it here.")

    if broken:
        print(f"\nFAIL. {len(broken)} script(s):")
        for name, err in broken:
            print(f"  {name}: {err}")
        print("\nAn import must not depend on data, a network call or one machine's paths.")
        return 1

    print("\nOK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
