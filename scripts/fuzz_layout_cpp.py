#!/usr/bin/env python3
"""Reproducible layout-only perturbations of prepared project-owned snippets."""

import argparse
import collections
import hashlib
import json
from pathlib import Path
import random
import re
import networkx as nx
import rust_joern


def project(result):
    funcs = {}
    for f in result.functions:
        if f.fullname in funcs:
            raise ValueError("ambiguous duplicate function identity")
        calls = collections.Counter(
            n.get("name") for n in f.raw["cpg"]["nodes"] if n["kind"] == "CALL"
        )
        funcs[f.fullname] = (f.cfg, calls)
    return funcs


def equal(a, b):
    if a.keys() != b.keys():
        return False

    def match(x, y):
        u, v = x["node"], y["node"]
        return (u.is_entrypoint, u.is_exitpoint) == (v.is_entrypoint, v.is_exitpoint)

    return all(
        a[k][1] == b[k][1] and nx.is_isomorphic(a[k][0], b[k][0], node_match=match)
        for k in a
    )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("inputs", nargs="+", type=Path)
    p.add_argument("--seed", type=int, default=20261029)
    p.add_argument("--variants", type=int, default=8)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    rng = random.Random(args.seed)
    rows = []
    for path in args.inputs:
        text = path.read_text()
        row = {
            "input": path.name,
            "sha256": hashlib.sha256(text.encode()).hexdigest(),
            "variants": [],
        }
        # Newlines inside raw string literals and escaped line continuations are not layout-only.
        if re.search(r'(?:u8|u|U|L)?R"', text) or any(
            x.rstrip().endswith("\\") for x in text.splitlines()
        ):
            row["status"] = "excluded_unsafe_newline_mutation"
            rows.append(row)
            continue
        try:
            base = project(
                rust_joern.parse_code(
                    text,
                    filename="input.cpp",
                    language="cpp",
                    preprocessed=True,
                    strict=True,
                    joern_loop_conditions=True,
                )
            )
            for i in range(args.variants):
                mutated = "".join(
                    line + ("\n" if rng.randrange(5) == 0 else "")
                    for line in text.splitlines(keepends=True)
                )
                if i % 2:
                    mutated = mutated.replace("\n", "\r\n")
                try:
                    cand = project(
                        rust_joern.parse_code(
                            mutated,
                            filename="input.cpp",
                            language="cpp",
                            preprocessed=True,
                            strict=True,
                            joern_loop_conditions=True,
                        )
                    )
                    row["variants"].append(
                        {
                            "index": i,
                            "sha256": hashlib.sha256(mutated.encode()).hexdigest(),
                            "same": equal(base, cand),
                        }
                    )
                except Exception as exc:
                    row["variants"].append({"index": i, "error": str(exc)[:500]})
            row["status"] = "tested"
            row["function_count"] = len(base)
        except Exception as exc:
            row.update(status="baseline_failure", error=str(exc)[:500])
        rows.append(row)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            {
                "seed": args.seed,
                "scope": "layout metamorphism only; not an original-Joern or semantic oracle",
                "results": rows,
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
