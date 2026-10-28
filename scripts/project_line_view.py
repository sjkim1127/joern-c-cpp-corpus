#!/usr/bin/env python3
"""Make a diagnostic project-owned view using compiler line markers.

Removing external declarations can change bindings. This is never a complete
translation unit or semantic CFG oracle.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re

MARKER = re.compile(r'^#\s+\d+\s+"([^\"]+)"')


def project_view(source, project, cwd):
    selected = []
    keep = False
    marker_count = 0
    for line in source.splitlines():
        match = MARKER.match(line)
        if match:
            marker_count += 1
            name = match.group(1)
            if name.startswith("<"):
                keep = False
            else:
                location = Path(name)
                if not location.is_absolute():
                    location = cwd / location
                keep = location.resolve().is_relative_to(project)
            continue
        if keep:
            selected.append(line)
    if not marker_count:
        raise ValueError("input contains no compiler line markers")
    return "\n".join(selected) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--compile-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = args.input.read_bytes()
    view = project_view(
        payload.decode("utf-8"), args.project_root.resolve(), args.compile_dir.resolve()
    )
    args.output.write_text(view)
    info = {
        "input_sha256": hashlib.sha256(payload).hexdigest(),
        "output_sha256": hashlib.sha256(view.encode()).hexdigest(),
        "scope": "project marker paths only; external declarations absent; diagnostic, not a complete TU",
    }
    args.output.with_suffix(args.output.suffix + ".json").write_text(
        json.dumps(info, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
