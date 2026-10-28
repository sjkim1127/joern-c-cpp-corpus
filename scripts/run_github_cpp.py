#!/usr/bin/env python3
"""Run a pinned GitHub C++ inventory without inferring ground truth."""

import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile


def run(row, binary, output, timeout, binary_hash):
    repo, spec = row
    path = output.parent / "inputs" / spec["local_id"]
    result = {
        "repository": repo["repository"],
        "commit": repo["commit"],
        "path": spec["path"],
        "sha256": spec["sha256"],
        "source_context": "raw, unpreprocessed",
        "standard": "unknown",
        "binary_sha256": binary_hash,
        "timeout_seconds": timeout,
    }
    out = output / "results" / f"{spec['local_id']}.json"
    graph = output / "graphs" / f"{spec['local_id']}.json"
    try:
        if hashlib.sha256(path.read_bytes()).hexdigest() != spec["sha256"]:
            raise ValueError("source hash mismatch")
        if out.is_file():
            prior = json.loads(out.read_text())
            keys = (
                "repository",
                "commit",
                "path",
                "sha256",
                "binary_sha256",
                "timeout_seconds",
            )
            if all(prior.get(k) == result.get(k) for k in keys) and (
                prior.get("status") not in ("output", "no_functions")
                or (
                    graph.is_file()
                    and hashlib.sha256(graph.read_bytes()).hexdigest()
                    == prior.get("graph_sha256")
                )
            ):
                return prior
        proc = subprocess.run(
            [
                str(binary),
                "analyze",
                str(path),
                "--language",
                "cpp",
                "--strict",
                "--output",
                str(graph),
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        result.update(returncode=proc.returncode, stderr_tail=proc.stderr[-3000:])
        if proc.returncode:
            result["status"] = "parse_error"
        elif not graph.is_file():
            result["status"] = "missing_output"
        else:
            obj = json.loads(graph.read_text())
            funcs = obj.get("functions", [])
            bad = 0
            for f in funcs:
                cfg = f.get("cfg", {})
                ids = {n["id"] for n in cfg.get("nodes", [])}
                if any(a not in ids or b not in ids for a, b in cfg.get("edges", [])):
                    bad += 1
            result.update(
                status="output" if funcs else "no_functions",
                function_count=len(funcs),
                bad_cfg_edges=bad,
                graph_sha256=hashlib.sha256(graph.read_bytes()).hexdigest(),
            )
    except subprocess.TimeoutExpired:
        result["status"] = "timeout"
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result.update(status="runner_error", error=str(exc))
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=out.parent, delete=False) as f:
        json.dump(result, f, indent=2)
        f.write("\n")
        temp = Path(f.name)
    temp.replace(out)
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inventory", type=Path, required=True)
    ap.add_argument("--binary", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--timeout", type=int, default=30)
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "graphs").mkdir(exist_ok=True)
    manifest = json.loads(args.inventory.read_text())
    tasks = [
        (r, f)
        for r in manifest["results"]
        if r["status"] == "ready"
        for f in r["files"]
    ]
    binary = args.binary.resolve()
    binary_hash = hashlib.sha256(binary.read_bytes()).hexdigest()
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [
            pool.submit(run, x, binary, args.output, args.timeout, binary_hash)
            for x in tasks
        ]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            results.append(result)
            if len(results) % 25 == 0:
                print(f"completed {len(results)}/{len(tasks)}", flush=True)
    summary = {
        "schema": "joern-cpp-raw-probe-v1",
        "inventory_sha256": hashlib.sha256(args.inventory.read_bytes()).hexdigest(),
        "binary_sha256": binary_hash,
        "timeout_seconds": args.timeout,
        "results": sorted(results, key=lambda x: (x["repository"], x["path"])),
    }
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")


if __name__ == "__main__":
    main()
