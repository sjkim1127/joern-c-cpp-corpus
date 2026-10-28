import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "freeze_checkpoint_inputs.py"
spec = importlib.util.spec_from_file_location("freeze_checkpoint_inputs", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def encoded(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()


class FreezeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.checkpoints = self.root / "checkpoints"
        self.checkpoints.mkdir()
        self.contract = {"backend": "frozen"}
        (self.root / "contract.json").write_bytes(encoded(self.contract))

    def tearDown(self):
        self.tmp.cleanup()

    def add(self, index, text):
        row = {
            "filename": "input.cpp",
            "language": "c++",
            "text": text,
            "sha256": hashlib.sha256(text.encode()).hexdigest(),
            "origins": [],
        }
        request_id = hashlib.sha256(
            encoded({"contract": self.contract, "row": row})
        ).hexdigest()
        record = {"request_sha256": request_id, "status": "parsed"}
        (self.checkpoints / f"{index:08d}.request.json").write_bytes(
            encoded({"row": row, "request_sha256": request_id})
        )
        (self.checkpoints / f"{index:08d}.json").write_bytes(
            encoded(
                {
                    "record": record,
                    "sha256": hashlib.sha256(encoded(record)).hexdigest(),
                }
            )
        )

    def test_duplicate_inputs_remain_separate(self):
        self.add(0, "int f(){return 1;}")
        self.add(1, "int f(){return 1;}")
        result = module.freeze(self.checkpoints)
        self.assertEqual((result["requested"], result["distinct_input_hashes"]), (2, 1))
        self.assertEqual(len(result["rows"]), 2)

    def test_corrupt_row_rejected(self):
        self.add(0, "int f(){return 1;}")
        path = self.checkpoints / "00000000.request.json"
        request = json.loads(path.read_bytes())
        request["row"]["text"] = "int f(){return 2;}"
        path.write_bytes(encoded(request))
        with self.assertRaisesRegex(ValueError, "source hash mismatch"):
            module.freeze(self.checkpoints)

    def test_row_hash_recalculation_cannot_bypass_request_contract(self):
        self.add(0, "int f(){return 1;}")
        path = self.checkpoints / "00000000.request.json"
        request = json.loads(path.read_bytes())
        request["row"]["text"] = "int f(){return 2;}"
        request["row"]["sha256"] = hashlib.sha256(
            request["row"]["text"].encode()
        ).hexdigest()
        path.write_bytes(encoded(request))
        with self.assertRaisesRegex(ValueError, "request hash"):
            module.freeze(self.checkpoints)

    def test_missing_sequence_and_tampered_record_rejected(self):
        self.add(1, "int f(){return 1;}")
        with self.assertRaisesRegex(ValueError, "sequence"):
            module.freeze(self.checkpoints)
        self.add(0, "int g(){return 2;}")
        path = self.checkpoints / "00000000.json"
        envelope = json.loads(path.read_bytes())
        envelope["record"]["status"] = "corrupt"
        path.write_bytes(encoded(envelope))
        with self.assertRaisesRegex(ValueError, "record hash mismatch"):
            module.freeze(self.checkpoints)


if __name__ == "__main__":
    unittest.main()
