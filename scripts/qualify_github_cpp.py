#!/usr/bin/env python3
"""Qualify standalone C++17 files with Clang before strict CFG extraction."""

import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile


def one(task, args, compiler, cli):
    repo, spec = task
    src = args.inventory.parent / "inputs" / spec["local_id"]
    stem = spec["local_id"]
    result = {
        "repository": repo["repository"],
        "commit": repo["commit"],
        "path": spec["path"],
        "source_sha256": spec["sha256"],
        "experiment_standard": "gnu++17",
        "original_standard": "unknown",
    }
    try:
        if hashlib.sha256(src.read_bytes()).hexdigest() != spec["sha256"]:
            raise ValueError("source hash mismatch")
        # Standalone source experiment; no guessed headers or macros.
        run = subprocess.run(
            [str(compiler), "-std=gnu++17", "-fsyntax-only", "-x", "c++", str(src)],
            capture_output=True,
            text=True,
            timeout=args.timeout,
        )
        if run.returncode:
            result.update(
                status="compiler_rejected_or_missing_context",
                stderr_tail=run.stderr[-1500:],
            )
        else:
            prepared = args.output / "prepared" / f"{stem}.ii"
            pre = subprocess.run(
                [
                    str(compiler),
                    "-std=gnu++17",
                    "-E",
                    "-x",
                    "c++",
                    str(src),
                    "-o",
                    str(prepared),
                ],
                capture_output=True,
                text=True,
                timeout=args.timeout,
            )
            if pre.returncode:
                result.update(
                    status="preprocess_failure", stderr_tail=pre.stderr[-1500:]
                )
            else:
                graph = args.output / "graphs" / f"{stem}.json"
                result["prepared_sha256"] = hashlib.sha256(
                    prepared.read_bytes()
                ).hexdigest()
                native = subprocess.run(
                    [
                        str(cli),
                        "analyze",
                        str(prepared),
                        "--language",
                        "cpp",
                        "--preprocessed",
                        "--strict",
                        "--output",
                        str(graph),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=args.timeout,
                )
                if native.returncode:
                    result.update(
                        status="native_parse_rejected",
                        stderr_tail=native.stderr[-1500:],
                    )
                elif not graph.exists():
                    result["status"] = "missing_graph"
                else:
                    obj = json.loads(graph.read_text())
                    funcs = obj.get("functions", [])
                    bad = 0
                    for f in funcs:
                        cfg = f.get("cfg", {})
                        ids = {n["id"] for n in cfg.get("nodes", [])}
                        if any(
                            a not in ids or b not in ids
                            for a, b in cfg.get("edges", [])
                        ):
                            bad += 1
                    result.update(
                        status="native_output" if funcs else "no_functions",
                        function_count=len(funcs),
                        bad_cfg_edges=bad,
                        graph_sha256=hashlib.sha256(graph.read_bytes()).hexdigest(),
                    )
    except subprocess.TimeoutExpired:
        result["status"] = "timeout"
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result.update(status="runner_error", error=str(exc))
    path = args.output / "results" / f"{stem}.json"
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as f:
        json.dump(result, f, indent=2)
        temp = Path(f.name)
    temp.replace(path)
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--inventory", type=Path, required=True)
    p.add_argument("--binary", type=Path, required=True)
    p.add_argument("--compiler", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--timeout", type=int, default=20)
    p.add_argument("--all-files", action="store_true")
    a = p.parse_args()
    for sub in ("prepared", "graphs", "results"):
        (a.output / sub).mkdir(parents=True, exist_ok=True)
    m = json.loads(a.inventory.read_text())
    tasks = [
        (r, f)
        for r in m["results"]
        if r["status"] == "ready"
        for f in (r["files"] if a.all_files else r["files"][:1])
    ]
    compiler = a.compiler.resolve()
    cli = a.binary.resolve()
    rows = []
    version = subprocess.check_output(
        [str(compiler), "--version"], text=True
    ).splitlines()[0]
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:
        for n, f in enumerate(
            concurrent.futures.as_completed(
                [pool.submit(one, t, a, compiler, cli) for t in tasks]
            ),
            1,
        ):
            rows.append(f.result())
            if n % 25 == 0:
                print(f"completed {n}/{len(tasks)}", flush=True)
    summary = {
        "schema": "joern-cpp-standalone-qualification-v1",
        "inventory_sha256": hashlib.sha256(a.inventory.read_bytes()).hexdigest(),
        "compiler": version,
        "compiler_sha256": hashlib.sha256(compiler.read_bytes()).hexdigest(),
        "binary_sha256": hashlib.sha256(cli.read_bytes()).hexdigest(),
        "timeout": a.timeout,
        "results": sorted(rows, key=lambda r: (r["repository"], r["path"])),
    }
    (a.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")


if __name__ == "__main__":
    main()
