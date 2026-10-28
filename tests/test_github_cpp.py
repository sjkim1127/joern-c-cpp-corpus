"""Offline guards for source selection and raw-input classification."""

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


discover = load("discover_github_cpp")
runner = load("run_github_cpp")
prepare = load("prepare_compile_command")
line_view = load("project_line_view")


class InventoryTests(unittest.TestCase):
    def test_line_view_keeps_only_proven_project_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            code = '# 1 "src/file.cpp"\nint f();\n# 1 "/usr/include/x.h"\nint hidden();\n# 3 "src/file.cpp"\nint g();\n'
            self.assertEqual(
                line_view.project_view(code, root, root), "int f();\nint g();\n"
            )
            with self.assertRaises(ValueError):
                line_view.project_view("int no_markers;", root, root)

    def test_preprocessor_command_keeps_flags_and_replaces_object_output(self):
        command = {
            "arguments": [
                "clang++",
                "-std=c++17",
                "-Iheaders",
                "-o",
                "x.o",
                "-c",
                "x.cpp",
            ]
        }
        actual = prepare.preprocess_argv(command, Path("/tmp/output.ii"))
        self.assertEqual(
            actual,
            [
                "clang++",
                "-std=c++17",
                "-Iheaders",
                "x.cpp",
                "-E",
                "-o",
                str(Path("/tmp/output.ii").resolve()),
            ],
        )

    def test_preprocessor_rejects_ambiguous_or_unexpanded_commands(self):
        for argv in (
            ["clang++", "@flags", "-o", "x.o", "-c", "x.cpp"],
            ["clang++", "-c", "x.cpp"],
        ):
            with self.subTest(argv=argv), self.assertRaises(ValueError):
                prepare.preprocess_argv({"arguments": argv}, Path("/tmp/output.ii"))

    def test_excludes_third_party_and_verifies_git_blob(self):
        content = b"int f() { return 42; }\n" + b" " * 300
        sha = hashlib.sha1(
            b"blob " + str(len(content)).encode() + b"\0" + content
        ).hexdigest()
        repo = {
            "full_name": "demo/project",
            "default_branch": "main",
            "license": {"spdx_id": "MIT"},
            "html_url": "https://example.invalid",
            "created_at": "2000",
            "description": "",
        }
        tree = {
            "tree": [
                {
                    "path": "3rdparty/ext.cpp",
                    "type": "blob",
                    "size": len(content),
                    "sha": sha,
                },
                {
                    "path": "src/main.cpp",
                    "type": "blob",
                    "size": len(content),
                    "sha": sha,
                },
            ]
        }

        def get(url, token):
            if "/commits/" in url:
                return json.dumps({"sha": "abc"}).encode()
            if "/git/trees/" in url:
                return json.dumps(tree).encode()
            return content

        with (
            tempfile.TemporaryDirectory() as temp,
            mock.patch.object(discover, "get", side_effect=get),
        ):
            row = discover.inspect(repo, "unused", Path(temp))
            self.assertEqual(row["status"], "ready")
            self.assertEqual([f["path"] for f in row["files"]], ["src/main.cpp"])
            self.assertEqual(row["files"][0]["git_blob_sha1"], sha)

    def test_source_hash_mismatch_fails_before_backend_execution(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "inputs").mkdir()
            (root / "inputs" / "x.cpp").write_text("altered")
            output = root / "probe"
            (output / "results").mkdir(parents=True)
            (output / "graphs").mkdir()
            spec = {"local_id": "x.cpp", "sha256": "wrong", "path": "x.cpp"}
            repo = {"repository": "demo/project", "commit": "abc"}
            with mock.patch.object(runner.subprocess, "run") as call:
                row = runner.run(
                    (repo, spec), Path("/nonexistent"), output, 2, "binhash"
                )
                call.assert_not_called()
            self.assertEqual(row["status"], "runner_error")
            self.assertIn("source hash mismatch", row["error"])

    def test_unpreprocessed_failure_is_not_counted_as_no_functions(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "inputs").mkdir()
            data = b"#include <x>\n"
            (root / "inputs" / "x.cpp").write_bytes(data)
            output = root / "probe"
            (output / "results").mkdir(parents=True)
            (output / "graphs").mkdir()
            spec = {
                "local_id": "x.cpp",
                "sha256": hashlib.sha256(data).hexdigest(),
                "path": "x.cpp",
            }
            repo = {"repository": "demo/project", "commit": "abc"}
            process = mock.Mock(
                returncode=1, stderr="unexpanded preprocessor directive"
            )
            with mock.patch.object(runner.subprocess, "run", return_value=process):
                row = runner.run(
                    (repo, spec), Path("/nonexistent"), output, 2, "binhash"
                )
            self.assertEqual(row["status"], "parse_error")
            self.assertEqual(row["source_context"], "raw, unpreprocessed")


if __name__ == "__main__":
    unittest.main()
