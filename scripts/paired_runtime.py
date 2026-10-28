#!/usr/bin/env python3
"""Alternate two frozen Rust-Joern CLI builds on identical prepared inputs.

Wall time includes process startup and output serialization. This is not a
comparison with Joern's persistent JVM or a CFG correctness measurement.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import subprocess
import time
from pathlib import Path


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def run(binary: Path, source: Path, language: str, timeout: float) -> dict:
    env = os.environ.copy()
    env["RAYON_NUM_THREADS"] = "1"
    start = time.perf_counter()
    try:
        result = subprocess.run(
            [
                str(binary),
                "analyze",
                str(source),
                "--language",
                language,
                "--preprocessed",
                "--strict",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=timeout,
            env=env,
        )
        return {
            "seconds": time.perf_counter() - start,
            "status": "completed",
            "exit_code": result.returncode,
            "stderr_sha256": hashlib.sha256(result.stderr).hexdigest(),
        }
    except subprocess.TimeoutExpired:
        return {
            "seconds": time.perf_counter() - start,
            "status": "timeout",
            "exit_code": None,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--input", type=Path, action="append", required=True)
    parser.add_argument("--language", choices=("c", "cpp"), required=True)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.repeats < 1 or args.timeout <= 0:
        parser.error("repeats and timeout must be positive")
    baseline, candidate = args.baseline.resolve(strict=True), args.candidate.resolve(
        strict=True
    )
    binaries = {"baseline": baseline, "candidate": candidate}
    binary_hashes = {label: digest(path) for label, path in binaries.items()}
    rows = []
    for source in args.input:
        source = source.resolve(strict=True)
        input_hash = digest(source)
        samples = {"baseline": [], "candidate": []}
        for turn in range(args.repeats):
            order = (
                ("baseline", "candidate")
                if turn % 2 == 0
                else ("candidate", "baseline")
            )
            for label in order:
                samples[label].append(
                    run(binaries[label], source, args.language, args.timeout)
                )
        medians = {
            label: (
                statistics.median(x["seconds"] for x in values)
                if all(x["status"] == "completed" for x in values)
                else None
            )
            for label, values in samples.items()
        }
        if digest(source) != input_hash:
            raise ValueError(f"input changed during measurement: {source}")
        rows.append(
            {
                "source": str(source),
                "input_sha256": input_hash,
                "samples": samples,
                "median_seconds": medians,
            }
        )
    if any(digest(path) != binary_hashes[label] for label, path in binaries.items()):
        raise ValueError("binary changed during measurement")
    report = {
        "version": 1,
        "language": args.language,
        "repeats": args.repeats,
        "measurement": "wall time, process and serialization included, warm file cache, one Rayon thread",
        "binaries": {
            label: {"path": str(path), "sha256": binary_hashes[label]}
            for label, path in binaries.items()
        },
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(
        json.dumps(
            [
                {"source": r["source"], "median_seconds": r["median_seconds"]}
                for r in rows
            ],
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
