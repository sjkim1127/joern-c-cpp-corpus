#!/usr/bin/env python3
"""Discover pinned public C++ source candidates; keep source payloads local."""

import argparse
import concurrent.futures
import hashlib
import json
import itertools
from pathlib import Path
import subprocess
import urllib.parse
import urllib.request

API = "https://api.github.com"
EXCLUDE = (
    "vendor/",
    "third_party/",
    "third-party/",
    "thirdparty/",
    "3rdparty/",
    "external/",
    "deps/",
    "node_modules/",
    "build/",
    "generated/",
)
SUFFIX = (".cpp", ".cc", ".cxx", ".C")
QUERIES = [
    "language:C++ stars:>100 size:<100000 created:<2012-01-01",
    "language:C++ stars:>100 size:<100000 created:2012-01-01..2016-12-31",
    "language:C++ stars:>100 size:<100000 created:2017-01-01..2020-12-31",
    "language:C++ stars:>100 size:<100000 created:2021-01-01..2026-10-28",
    "language:C++ stars:>20 size:<100000 created:<2015-01-01 topic:compiler",
]


def get(url, token):
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json",
            "User-Agent": "joern-corpus-research",
        },
    )
    with urllib.request.urlopen(req, timeout=45) as res:
        return res.read()


def inspect(repo, token, root):
    name = repo["full_name"]
    try:
        commit = json.loads(
            get(
                f"{API}/repos/{name}/commits/{urllib.parse.quote(repo['default_branch'], safe='')}",
                token,
            )
        )["sha"]
        tree = json.loads(
            get(f"{API}/repos/{name}/git/trees/{commit}?recursive=1", token)
        )
        candidates = []
        for e in tree.get("tree", []):
            p = e["path"]
            lo = p.lower()
            if (
                e["type"] != "blob"
                or not p.endswith(SUFFIX)
                or any(x in lo for x in EXCLUDE)
                or not 256 <= e.get("size", 0) <= 200000
            ):
                continue
            candidates.append(e)
        if not candidates:
            return {"repository": name, "status": "no_eligible_cpp", "commit": commit}

        # Stable selection: production-oriented path and a separate largest stress input.
        def key(e):
            p = e["path"].lower()
            return (
                ("test" in p or "example" in p or "benchmark" in p),
                not (p.startswith("src/") or "/src/" in p),
                len(p),
                p,
            )

        primary = min(candidates, key=key)
        largest = max(candidates, key=lambda x: (x["size"], x["path"]))
        selected = {e["path"]: e for e in (primary, largest)}
        files = []
        for p, e in selected.items():
            raw = f"https://raw.githubusercontent.com/{name}/{commit}/{urllib.parse.quote(p, safe='/')}"
            data = get(raw, token)
            blob = hashlib.sha1(
                b"blob " + str(len(data)).encode() + b"\0" + data
            ).hexdigest()
            if blob != e["sha"] or len(data) != e["size"]:
                raise ValueError("git blob mismatch")
            path = (
                root
                / "inputs"
                / f"{hashlib.sha256((name + commit + p).encode()).hexdigest()}.cpp"
            )
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            files.append(
                {
                    "path": p,
                    "git_blob_sha1": blob,
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "size": len(data),
                    "raw_url": raw,
                    "local_id": path.name,
                    "selection": "largest"
                    if p == largest["path"] and p != primary["path"]
                    else "primary",
                }
            )
        return {
            "repository": name,
            "status": "ready",
            "commit": commit,
            "license_spdx": repo["license"]["spdx_id"],
            "license_url": repo["license"].get("url"),
            "html_url": repo["html_url"],
            "created_at": repo["created_at"],
            "description": repo.get("description"),
            "tree_truncated": tree.get("truncated", False),
            "files": files,
        }
    except Exception as exc:
        return {"repository": name, "status": "error", "error": str(exc)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--target", type=int, default=300)
    ap.add_argument("--workers", type=int, default=5)
    args = ap.parse_args()
    token = subprocess.check_output(["gh", "auth", "token"], text=True).strip()
    args.output.mkdir(parents=True, exist_ok=True)
    buckets = []
    for query in QUERIES:
        url = (
            API
            + "/search/repositories?"
            + urllib.parse.urlencode(
                {"q": query, "per_page": 100, "sort": "stars", "order": "desc"}
            )
        )
        data = json.loads(get(url, token))
        bucket = []
        for r in data["items"]:
            license = r.get("license") or {}
            if license.get("spdx_id") not in (None, "NOASSERTION", "NONE") and r[
                "full_name"
            ].lower() not in (
                "google/snappy",
                "ninja-build/ninja",
                "google/double-conversion",
            ):
                bucket.append(r)
        buckets.append(bucket)
    repos = {}
    for group in itertools.zip_longest(*buckets):
        for repo in group:
            if repo is not None:
                repos.setdefault(repo["full_name"], repo)
    ordered = list(repos.values())
    rows = []
    old_path = args.output / "manifest.json"
    cached = {}
    if old_path.exists():
        previous = json.loads(old_path.read_text())
        for row in previous.get("results", []):
            if row.get("status") == "ready" and all(
                not any(excluded in item["path"].lower() for excluded in EXCLUDE)
                and (args.output / "inputs" / item["local_id"]).is_file()
                and hashlib.sha256(
                    (args.output / "inputs" / item["local_id"]).read_bytes()
                ).hexdigest()
                == item["sha256"]
                for item in row["files"]
            ):
                cached[row["repository"]] = row

    def obtain(repo):
        return cached.get(repo["full_name"]) or inspect(repo, token, args.output)

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        # Bounded waves keep retries and failures explicit and allow collecting 300 successes.
        for start in range(0, len(ordered), 20):
            if sum(x["status"] == "ready" for x in rows) >= args.target:
                break
            batch = list(pool.map(obtain, ordered[start : start + 20]))
            rows.extend(batch)
            print(
                f"inspected={len(rows)} ready={sum(x['status'] == 'ready' for x in rows)}",
                flush=True,
            )
            (args.output / "manifest.json").write_text(
                json.dumps(
                    {
                        "schema": "joern-github-cpp-inventory-v1",
                        "queries": QUERIES,
                        "target": args.target,
                        "results": rows,
                    },
                    indent=2,
                )
                + "\n"
            )
    print(
        json.dumps(
            {
                "candidates": len(ordered),
                "inspected": len(rows),
                "ready": sum(x["status"] == "ready" for x in rows),
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
