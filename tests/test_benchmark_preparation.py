import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location(
    "prepare_benchmark_case", SCRIPTS / "prepare_benchmark_case.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PreparationTests(unittest.TestCase):
    def test_actual_standard_override_and_conflicting_flags_are_rejected(self):
        module.validate_standard(["clang++", "-std=c++20"], "c++20")
        for argv in (
            ["clang++", "-std=c++20"],
            ["clang++", "-std=c++17", "-std=c++20"],
            ["clang++"],
        ):
            with self.assertRaisesRegex(ValueError, "exact explicit"):
                module.validate_standard(argv, "c++17")

    def test_relative_database_paths_and_dependencies(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            database = root / "compile_commands.json"
            source = root / "src.cc"
            entry = {
                "directory": "build",
                "file": "../src.cc",
                "arguments": [
                    sys.executable,
                    "-std=c++17",
                    "-MMD",
                    "-MF",
                    "output.d",
                    "-o",
                    "output.o",
                    "-c",
                    "../src.cc",
                ],
            }
            database.write_text(json.dumps([entry]))
            directory, command = module.command_for_source(database, source)
            self.assertEqual(directory, root / "build")
            self.assertEqual(command[1:], ["-std=c++17", "../src.cc"])

    def test_ambiguous_commands_and_response_files_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            path = root / "compile_commands.json"
            entry = {
                "directory": str(root),
                "file": "s.cc",
                "arguments": [
                    sys.executable,
                    "-c",
                    "s.cc",
                    "-o",
                    "s.o",
                ],
            }
            path.write_text(json.dumps([entry, entry]))
            with self.assertRaisesRegex(ValueError, "exactly one"):
                module.command_for_source(path, root / "s.cc")
            entry["arguments"].append("@flags.rsp")
            path.write_text(json.dumps([entry]))
            with self.assertRaisesRegex(ValueError, "response"):
                module.command_for_source(path, root / "s.cc")

    def test_marker_paths_and_physical_lines_are_preserved(self):
        data = b'# 30 "src/main file.cc"\nint f() {}\n# 1 "<built-in>"\n\n'
        prepared, owners = module.blank_markers(data, Path("/project"))
        self.assertEqual(prepared, b"\nint f() {}\n\n\n")
        self.assertEqual(owners, {2: (Path("/project/src/main file.cc"), 30)})

    @staticmethod
    def declaration(name, begin, named, end, mangled="_Zf"):
        return {
            "kind": "FunctionDecl",
            "name": name,
            "mangledName": mangled,
            "loc": {"offset": named},
            "range": {"begin": {"offset": begin}},
            "inner": [{"kind": "CompoundStmt", "range": {"end": {"offset": end}}}],
        }

    def test_overloads_survive_and_template_clones_keep_evidence(self):
        prepared = b"int f() {}\nint f(int) {}\n"
        ast = {
            "inner": [
                self.declaration("f", 0, 4, 9),
                self.declaration("f", 11, 15, 23, "_Zfi"),
                self.declaration("f", 0, 4, 9, "_Zftemplate"),
            ]
        }
        owners = {1: (Path("/p/s.cc"), 1), 2: (Path("/p/s.cc"), 2)}
        result = module.inventory(ast, prepared, owners, Path("/p/s.cc"))
        self.assertEqual(len(result["functions"]), 2)
        self.assertEqual(result["functions"][0]["ast_record_count"], 2)
        self.assertEqual(len(result["functions"][0]["representations"]), 2)
        self.assertFalse(result["exclusions"])

    def test_project_headers_and_foreign_headers_have_separate_ownership(self):
        prepared = b"int h(){}\nint s(){}\nint x(){}\n"
        ast = {
            "inner": [
                self.declaration("h", 0, 4, 8),
                self.declaration("s", 10, 14, 18),
                self.declaration("x", 20, 24, 28),
            ]
        }
        owners = {
            1: (Path("/p/h.h"), 1),
            2: (Path("/p/s.cc"), 1),
            3: (Path("/external/h.h"), 1),
        }
        primary = module.inventory(ast, prepared, owners, Path("/p/s.cc"))
        self.assertEqual([f["name"] for f in primary["functions"]], ["s"])
        project = module.inventory(ast, prepared, owners, Path("/p/s.cc"), Path("/p"))
        self.assertEqual(
            [f["ownership_role"] for f in project["functions"]],
            ["project_header", "primary"],
        )

    def test_conflicting_declarations_and_invalid_offsets_are_not_silently_scored(self):
        owners = {1: (Path("/p/s.cc"), 1)}
        ast = {
            "inner": [self.declaration("f", 0, 4, 8), self.declaration("g", 0, 4, 8)]
        }
        result = module.inventory(ast, b"int f(){}\n", owners, Path("/p/s.cc"))
        self.assertFalse(result["functions"])
        self.assertEqual(len(result["exclusions"]), 1)
        with self.assertRaisesRegex(ValueError, "offset outside"):
            module.inventory(
                self.declaration("f", 0, 4, 100),
                b"int f(){}\n",
                owners,
                Path("/p/s.cc"),
            )


if __name__ == "__main__":
    unittest.main()
