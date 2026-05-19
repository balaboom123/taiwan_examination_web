import tempfile
import unittest
from pathlib import Path

from app.storage import MirrorStore


class MirrorStoreTests(unittest.TestCase):
    def test_write_bytes_is_idempotent_for_existing_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = MirrorStore(Path(tmp_dir))
            first = store.write_bytes("115/115030/101/0101/question.pdf", b"%PDF-1.7 demo")
            second = store.write_bytes("115/115030/101/0101/question.pdf", b"%PDF-1.7 demo")

            self.assertEqual(first.checksum, second.checksum)
            self.assertFalse(second.created)
            self.assertTrue((Path(tmp_dir) / "115" / "115030" / "101" / "0101" / "question.pdf").exists())


if __name__ == "__main__":
    unittest.main()
