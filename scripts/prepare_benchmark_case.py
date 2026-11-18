#!/usr/bin/env python3
"""Prepare a pinned Clang build cell and inventory its written source bodies.

This pilot records compiler evidence, not semantic CFG correctness. All output
is local; admission for redistribution or other compiler families is separate.
"""

from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import subprocess

from prepare_zlib import object_identity

FUNCTION_KINDS = {
    "FunctionDecl",
    "CXXMethodDecl",
    "CXXConstructorDecl",
    "CXXDestructorDecl",
    "CXXConversionDecl",
}
MARKER = re.compile(r'^\s*#\s*\d+\s+"')


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def resolve(directory: Path, path: str) -> Path:
    value = Path(path)
    return (value if value.is_absolute() else directory / value).resolve()


def command_for_source(database: Path, source: Path) -> tuple[Path, list[str]]:
    matches = []
    for entry in json.loads(database.read_text()):
        directory = resolve(database.parent, entry["directory"])
        if resolve(directory, entry["file"]) == source:
            matches.append((directory, entry))
    if len(matches) != 1:
        raise ValueError("source must have exactly one compile command")
    directory, entry = matches[0]
    if "arguments" in entry:
        argv = entry["arguments"]
    else:
        if os.name == "nt":
            raise ValueError("Windows command strings need a native argv decoder")
        argv = shlex.split(entry["command"])
    if (
        not isinstance(argv, list)
        or not argv
        or not all(isinstance(v, str) for v in argv)
    ):
        raise ValueError("invalid compile argv")
    if any(v.startswith("@") for v in argv):
        raise ValueError("response files are not supported in this pilot")
    if argv.count("-c") != 1 or argv.count("-o") != 1:
        raise ValueError("expected one compile action and one output")
    output = []
    i = 0
    while i < len(argv):
        token = argv[i]
        if token in {"-o", "-MF", "-MT", "-MQ"}:
            if i + 1 == len(argv):
                raise ValueError("missing compiler option argument")
            i += 2
            continue
        if token not in {"-c", "-MD", "-MMD"}:
            output.append(token)
        i += 1
    compiler = (
        resolve(directory, output[0])
        if "/" in output[0]
        else Path(shutil.which(output[0]) or output[0]).resolve(strict=True)
    )
    output[0] = str(compiler)
    return directory, output


def blank_markers(
    data: bytes, directory: Path
) -> tuple[bytes, dict[int, tuple[Path, int]]]:
    """Preserve physical lines; retain a separate compiler source-ownership map."""
    result, ownership = [], {}
    owner, logical = None, None
    for physical, line in enumerate(data.splitlines(keepends=True), 1):
        text = line.decode("utf-8")
        if MARKER.match(text):
            # Tokenize the quoted path as a JSON string, including escaped slashes/quotes.
            match = re.match(r'^\s*#\s*(\d+)\s+("(?:[^"\\]|\\.)*")', text)
            if match is None:
                raise ValueError("invalid compiler line marker")
            logical = int(match.group(1))
            filename = json.loads(match.group(2))
            owner = None if filename.startswith("<") else resolve(directory, filename)
            result.append(b"\n" if line.endswith(b"\n") else b"")
        else:
            result.append(line)
            if owner is not None:
                ownership[physical] = (owner, logical)
            if logical is not None:
                logical += 1
    return b"".join(result), ownership


def location_offset(location: dict) -> int | None:
    # Macro-expansion coordinates select the definition written in this TU.
    return location.get("expansionLoc", location).get("offset")


def validate_standard(command: list[str], requested: str) -> None:
    if [v for v in command if v.startswith("-std=")] != ["-std=" + requested]:
        raise ValueError(
            "compile argv must contain the exact explicit requested standard"
        )


def inventory(
    ast: dict,
    prepared: bytes,
    ownership: dict,
    source: Path,
    checkout: Path | None = None,
) -> dict:
    starts = [0] + [i + 1 for i, byte in enumerate(prepared) if byte == 10]
    records = {}
    omitted = {}

    def line(offset):
        if not isinstance(offset, int) or not 0 <= offset < len(prepared):
            raise ValueError("compiler AST offset outside prepared source")
        return bisect.bisect_right(starts, offset)

    def walk(node):
        if node.get("kind") in FUNCTION_KINDS and not node.get("isImplicit", False):
            bodies = [
                n
                for n in node.get("inner", [])
                if n.get("kind") in {"CompoundStmt", "CXXTryStmt"}
            ]
            if len(bodies) > 1:
                raise ValueError("ambiguous compiler function body")
            if bodies:
                begin = location_offset(node.get("range", {}).get("begin", {}))
                name = location_offset(node.get("loc", {}))
                end = location_offset(bodies[0].get("range", {}).get("end", {}))
                if None not in (begin, name, end):
                    first, named, last = line(begin), line(name), line(end)
                    owned = [ownership.get(v) for v in (first, named, last)]
                    file = owned[1][0] if owned[1] else None
                    eligible = file is not None and (
                        file == source
                        if checkout is None
                        else file.is_relative_to(checkout)
                    )
                    if eligible and all(v is not None and v[0] == file for v in owned):
                        key = (begin, name, end)
                        # AST template clones can share one written body. Preserve their
                        # evidence together; conflicting spellings remain ambiguous.
                        row = records.setdefault(
                            key,
                            {
                                "name": node["name"],
                                "kind": node["kind"],
                                "start": first,
                                "name_line": named,
                                "end": last,
                                "source_start": owned[0][1],
                                "source_name_line": owned[1][1],
                                "source_end": owned[2][1],
                                "offsets": list(key),
                                "source_file": (
                                    str(file.relative_to(checkout))
                                    if checkout
                                    else str(file)
                                ),
                                "ownership_role": (
                                    "primary"
                                    if file == source
                                    else (
                                        "project_implementation"
                                        if file.suffix in {".cc", ".cpp", ".cxx", ".C"}
                                        else "project_header"
                                    )
                                ),
                                "ast_record_count": 0,
                                "representations": [],
                            },
                        )
                        if (row["name"], row["kind"]) != (node["name"], node["kind"]):
                            omitted[key] = (
                                "conflicting_declarations_at_one_written_body"
                            )
                        row["ast_record_count"] += 1
                        representation = {
                            k: node[k] for k in ("mangledName", "type") if k in node
                        }
                        if representation not in row["representations"]:
                            row["representations"].append(representation)
        for child in node.get("inner", []):
            walk(child)

    walk(ast)
    return {
        "population": "compiler-observed explicit written bodies",
        "ownership_scope": "project" if checkout else "primary",
        "implicit_functions_included": False,
        "template_ast_clones_grouped_by_written_offsets": True,
        "complete_language_or_semantic_cfg_oracle": False,
        "functions": [records[k] for k in sorted(records) if k not in omitted],
        "exclusions": [
            {"offsets": list(k), "reason": v} for k, v in sorted(omitted.items())
        ],
    }


def prepare(args) -> dict:
    checkout = args.checkout.resolve(strict=True)
    source = resolve(checkout, args.source)
    database = args.database.resolve(strict=True)
    output = args.output.resolve()
    if not source.is_relative_to(checkout):
        raise ValueError("source outside checkout")

    def git(*argv):
        return subprocess.check_output(
            ["git", "-C", str(checkout), *argv], text=True
        ).strip()

    if git("rev-parse", "HEAD") != args.commit or git(
        "status", "--porcelain", "--untracked-files=all"
    ):
        raise ValueError("checkout must be clean at the exact requested commit")
    if git("submodule", "status", "--recursive"):
        raise ValueError("submodule evidence is not supported in this pilot")
    directory, command = command_for_source(database, source)
    version = subprocess.check_output([command[0], "--version"], text=True)
    if "clang" not in version.lower():
        raise ValueError("this pilot requires a direct Clang driver")
    validate_standard(command, args.standard)
    source_indices = [
        i
        for i, token in enumerate(command[1:], 1)
        if not token.startswith("-") and resolve(directory, token) == source
    ]
    if len(source_indices) != 1:
        raise ValueError("compile argv must contain exactly one source operand")
    output.mkdir(parents=True, exist_ok=False)
    provenance = {
        "schema": "joern-clang-build-cell-v1",
        "status": "preparing",
        "revision": args.commit,
        "source": str(source.relative_to(checkout)),
        "source_sha256": digest(source),
        "database_sha256": digest(database),
        "compiler_sha256": digest(Path(command[0])),
        "compiler_version": version,
        "directory": str(directory),
        "compile_argv_without_outputs": command,
        "execution_host": {"os": platform.system(), "architecture": platform.machine()},
        "ownership_scope": args.scope,
        "standard": args.standard,
        "standard_origin": "explicit local build configuration",
        "semantic_cfg_correctness": None,
        "redistribution_qualified": False,
    }

    def run(label, argv, destination=None):
        provenance.setdefault("steps", []).append({"label": label, "argv": argv})
        with (output / (label + ".stderr")).open("wb") as errors:
            with (destination or output / (label + ".stdout")).open("wb") as stdout:
                subprocess.run(
                    argv,
                    cwd=directory,
                    stdout=stdout,
                    stderr=errors,
                    check=True,
                    timeout=args.timeout,
                )

    try:
        run("syntax", command + ["-fsyntax-only"])
        original = output / "original.ii"
        run("preprocess", command + ["-E", "-o", str(original)])
        prepared, ownership = blank_markers(original.read_bytes(), directory)
        prepared_path = output / "prepared.cpp"
        prepared_path.write_bytes(prepared)
        prepared_command = command.copy()
        prepared_command[source_indices[0]] = str(prepared_path)
        run("prepared-syntax", prepared_command + ["-fsyntax-only"])
        ast_path = output / "ast.json"
        run(
            "ast",
            prepared_command + ["-fsyntax-only", "-Xclang", "-ast-dump=json"],
            ast_path,
        )
        index = inventory(
            json.loads(ast_path.read_bytes()),
            prepared,
            ownership,
            source,
            checkout if args.scope == "project" else None,
        )
        index_path = output / "functions.json"
        index_path.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n")
        obj = output / "target.o"
        run("object", command + ["-c", "-o", str(obj)])
        identity = object_identity(obj)
        if (
            identity is None
            or identity["format"] != args.expected_format
            or identity["architecture"] != args.expected_arch
        ):
            raise ValueError(
                "object format or architecture disagrees with requested profile"
            )
        if (
            digest(source) != provenance["source_sha256"]
            or digest(database) != provenance["database_sha256"]
        ):
            raise ValueError("source or compile database changed during preparation")
        if digest(Path(command[0])) != provenance["compiler_sha256"] or git(
            "status", "--porcelain", "--untracked-files=all"
        ):
            raise ValueError("compiler or source checkout changed during preparation")
        provenance.update(
            status="compiler_indexed",
            original_sha256=digest(original),
            prepared_sha256=digest(prepared_path),
            function_inventory_sha256=digest(index_path),
            written_functions=len(index["functions"]),
            inventory_exclusions=len(index["exclusions"]),
            object_identity=identity,
            object_sha256=digest(obj),
        )
    except Exception as error:
        provenance.update(
            status="preparation_failed", error=f"{type(error).__name__}: {error}"
        )
        raise
    finally:
        (output / "provenance.json").write_text(
            json.dumps(provenance, indent=2, sort_keys=True) + "\n"
        )
    return provenance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("checkout", "database", "output"):
        parser.add_argument("--" + option, type=Path, required=True)
    for option in ("commit", "source", "standard"):
        parser.add_argument("--" + option, required=True)
    parser.add_argument(
        "--expected-format", choices=["Mach-O", "ELF", "COFF"], required=True
    )
    parser.add_argument(
        "--expected-arch", choices=["aarch64", "x86_64", "x86"], required=True
    )
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("--scope", choices=["primary", "project"], default="primary")
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("timeout must be positive")
    result = prepare(args)
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "status",
                    "written_functions",
                    "object_identity",
                    "prepared_sha256",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
