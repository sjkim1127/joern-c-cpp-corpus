#!/usr/bin/env python3
"""Recover hash-checked prepared requests without copying parser results.

The output is an experimental local replay input, not a qualified benchmark.
No compiler standard or original project provenance is inferred from filenames.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


def freeze(checkpoints: Path) -> dict[str, Any]:
    requests = sorted(
        checkpoints.glob("[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9].request.json")
    )
    if not requests:
        raise ValueError("no checkpoint requests found")
    contract = json.loads((checkpoints.parent / "contract.json").read_bytes())

    def encoded(value: Any) -> bytes:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()

    rows = []
    request_ids = set()
    for index, path in enumerate(requests):
        if path.name != f"{index:08d}.request.json":
            raise ValueError("checkpoint sequence is incomplete")
        request = json.loads(path.read_bytes())
        row = request["row"]
        if row["language"] not in ("c", "cpp", "c++"):
            raise ValueError(f"unsupported language in {path.name}")
        if hashlib.sha256(row["text"].encode("utf-8")).hexdigest() != row["sha256"]:
            raise ValueError(f"source hash mismatch in {path.name}")
        request_id = request["request_sha256"]
        expected = hashlib.sha256(
            encoded({"contract": contract, "row": row})
        ).hexdigest()
        if request_id != expected:
            raise ValueError(f"invalid request hash in {path.name}")
        record_path = checkpoints / f"{index:08d}.json"
        if not record_path.is_file():
            raise ValueError(f"missing completed record for {path.name}")
        envelope = json.loads(record_path.read_bytes())
        record = envelope["record"]
        if hashlib.sha256(encoded(record)).hexdigest() != envelope["sha256"]:
            raise ValueError(f"record hash mismatch for {path.name}")
        if record["request_sha256"] != request_id:
            raise ValueError(f"request and record disagree for {path.name}")
        request_ids.add(request_id)
        rows.append(row)
    return {
        "schema_version": 1,
        "purpose": "local parser replay; source validity and standard unverified",
        "source_contract_sha256": hashlib.sha256(encoded(contract)).hexdigest(),
        "requested": len(rows),
        "distinct_input_hashes": len({row["sha256"] for row in rows}),
        "distinct_request_hashes": len(request_ids),
        "languages": dict(sorted(Counter(row["language"] for row in rows).items())),
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoints", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = freeze(args.checkpoints)
    payload = (
        json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("xb") as stream:
        stream.write(payload)
    print(json.dumps({key: value for key, value in data.items() if key != "rows"}))
    print("sha256:", hashlib.sha256(payload).hexdigest())


if __name__ == "__main__":
    main()
