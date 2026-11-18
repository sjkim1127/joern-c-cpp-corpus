#!/usr/bin/env python3
"""Discover pinned public C++ source candidates; keep source payloads local."""

import argparse
import concurrent.futures
import hashlib
import json
import itertools
from pathlib import Path
import shutil
import subprocess
import tempfile
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
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "joern-corpus-research",
    }
    if urllib.parse.urlsplit(url).hostname == "api.github.com":
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(
        url,
        headers=headers,
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
                    "selection": (
                        "largest"
                        if p == largest["path"] and p != primary["path"]
                        else "primary"
                    ),
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
            "discovery_query": repo.get("discovery_query"),
            "topics": repo.get("topics", []),
            "tree_truncated": tree.get("truncated", False),
            "files": files,
        }
    except Exception as exc:
        return {"repository": name, "status": "error", "error": str(exc)}


def seed_rows(manifest, output):
    rows = json.loads(manifest.read_text())["results"]
    seen = set()
    ready = []
    for row in rows:
        if row["status"] != "ready":
            continue
        key = row["repository"].casefold()
        if key in seen:
            raise ValueError(f"duplicate seed repository {key}")
        seen.add(key)
        if not row["files"]:
            raise ValueError(f"empty seed repository {key}")
        for entry in row["files"]:
            local_id = entry["local_id"]
            if Path(local_id).name != local_id:
                raise ValueError(f"invalid seed filename {local_id}")
            source = manifest.parent / "inputs" / local_id
            if hashlib.sha256(source.read_bytes()).hexdigest() != entry["sha256"]:
                raise ValueError(f"seed hash mismatch: {source}")
            dest = output / "inputs" / local_id
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, dest)
        ready.append(row)
    return ready


def save_manifest(path, data):
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as stream:
        json.dump(data, stream, indent=2)
        stream.write("\n")
        temporary = Path(stream.name)
    temporary.replace(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--target", type=int, default=300)
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--seed", type=Path, help="Preserve an existing fixed inventory")
    ap.add_argument(
        "--query-file", type=Path, help="JSON array of GitHub search queries"
    )
    args = ap.parse_args()
    if args.target < 1 or args.workers < 1:
        ap.error("target and workers must be positive")
    queries = json.loads(args.query_file.read_text()) if args.query_file else QUERIES
    if (
        not isinstance(queries, list)
        or not queries
        or not all(isinstance(q, str) and q for q in queries)
    ):
        ap.error("expected a non-empty array of queries")
    if args.seed and args.seed.resolve().parent == args.output.resolve():
        ap.error("the seed and expansion must use separate directories")
    token = subprocess.check_output(["gh", "auth", "token"], text=True).strip()
    args.output.mkdir(parents=True, exist_ok=True)
    buckets = []
    for query in queries:
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
            if (
                not r.get("fork")
                and license.get("spdx_id") not in (None, "NOASSERTION", "NONE")
                and r["full_name"].lower()
                not in (
                    "google/snappy",
                    "ninja-build/ninja",
                    "google/double-conversion",
                )
            ):
                bucket.append(r | {"discovery_query": query})
        buckets.append(bucket)
    repos = {}
    for group in itertools.zip_longest(*buckets):
        for repo in group:
            if repo is not None:
                repos.setdefault(repo["full_name"].casefold(), repo)
    rows = seed_rows(args.seed, args.output) if args.seed else []
    seed_names = {r["repository"].casefold() for r in rows}
    old_path = args.output / "manifest.json"
    seed_sha = hashlib.sha256(args.seed.read_bytes()).hexdigest() if args.seed else None
    cached = {}
    if old_path.exists():
        previous = json.loads(old_path.read_text())
        if previous.get("seed_manifest_sha256") != seed_sha:
            ap.error("existing inventory uses a different seed manifest")
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
                cached[row["repository"].casefold()] = row
    for name, row in cached.items():
        if name not in seed_names:
            rows.append(row)
    admitted = len(rows)
    if admitted > args.target:
        ap.error("target is smaller than the existing ready inventory")
    ordered = [
        repo
        for name, repo in repos.items()
        if name not in seed_names and name not in cached
    ]

    def checkpoint():
        save_manifest(
            old_path,
            {
                "schema": "joern-github-cpp-inventory-v1",
                "queries": queries,
                "target": args.target,
                "seed_manifest_sha256": seed_sha,
                "results": rows,
            },
        )

    checkpoint()

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        cursor = 0
        while cursor < len(ordered) and admitted < args.target:
            wave = ordered[cursor : cursor + min(20, args.target - admitted)]
            batch = list(pool.map(lambda repo: inspect(repo, token, args.output), wave))
            cursor += len(wave)
            rows.extend(batch)
            admitted += sum(x["status"] == "ready" for x in batch)
            print(
                f"inspected={len(rows)} ready={admitted}",
                flush=True,
            )
            checkpoint()
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
    return 0 if admitted == args.target else 1


if __name__ == "__main__":
    raise SystemExit(main())
