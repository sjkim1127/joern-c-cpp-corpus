#!/usr/bin/env python3
"""Preprocess one explicitly selected TU from a clean pinned CMake checkout."""

import argparse
import hashlib
import json
from pathlib import Path
import shlex
import subprocess


def preprocess_argv(entry, destination):
    argv = entry.get("arguments") or shlex.split(entry["command"])
    if any(x.startswith("@") for x in argv):
        raise ValueError("response files are unsupported")
    if argv.count("-c") != 1 or argv.count("-o") != 1:
        raise ValueError("expected one -c and one -o")
    i = argv.index("-o")
    if i + 1 >= len(argv):
        raise ValueError("missing output argument")
    result = argv[:i] + argv[i + 2 :]
    result.remove("-c")
    result += ["-E", "-o", str(destination.resolve())]
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--checkout", type=Path, required=True)
    p.add_argument("--commit", required=True)
    p.add_argument("--database", type=Path, required=True)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    checkout = a.checkout.resolve()
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=checkout, text=True
    ).strip()
    dirty = subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=checkout,
        text=True,
    )
    if head != a.commit or dirty:
        raise ValueError("checkout is dirty or commit does not match")
    source = a.source.resolve()
    if not source.is_relative_to(checkout):
        raise ValueError("source outside checkout")
    matches = [
        e
        for e in json.loads(a.database.read_text())
        if Path(e["file"]).resolve() == source
    ]
    if len(matches) != 1:
        raise ValueError("compile command is not unique")
    a.output.mkdir(parents=True, exist_ok=True)
    out = a.output / "prepared.ii"
    entry = matches[0]
    command = preprocess_argv(entry, out)
    subprocess.run(command, cwd=entry["directory"], check=True, timeout=120)
    data = {
        "commit": head,
        "source": str(source.relative_to(checkout)),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "database_sha256": hashlib.sha256(a.database.read_bytes()).hexdigest(),
        "prepared_sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
        "original_command": entry,
        "preprocess_argv": command,
        "warning": "configured local build, not historical build or semantic CFG oracle",
    }
    (a.output / "provenance.json").write_text(json.dumps(data, indent=2) + "\n")


if __name__ == "__main__":
    main()
