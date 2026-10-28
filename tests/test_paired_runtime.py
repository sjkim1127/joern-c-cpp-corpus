import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "paired_runtime.py"
spec = importlib.util.spec_from_file_location("paired_runtime", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RuntimeTests(unittest.TestCase):
    def test_failure_is_not_counted_as_success_and_timeout_is_retained(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.cpp"
            source.write_text("int f() { return 1; }")
            binary = root / "fake"
            binary.write_text("#!/bin/sh\nexit 7\n")
            binary.chmod(0o755)
            result = module.run(binary, source, "cpp", 1)
            self.assertEqual((result["status"], result["exit_code"]), ("completed", 7))
            binary.write_text("#!/bin/sh\nsleep 1\n")
            self.assertEqual(
                module.run(binary, source, "cpp", 0.05)["status"], "timeout"
            )


if __name__ == "__main__":
    unittest.main()
