from __future__ import annotations

import hashlib
from pathlib import Path

from app.models import StoredFile


class MirrorStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def write_bytes(self, storage_key: str, data: bytes) -> StoredFile:
        path = self.root / Path(storage_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        checksum = hashlib.sha256(data).hexdigest()
        created = not path.exists()
        if created:
            path.write_bytes(data)
        return StoredFile(storage_key=storage_key, path=path, checksum=checksum, created=created, size=len(data))

