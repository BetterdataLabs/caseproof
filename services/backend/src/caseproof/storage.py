"""Private object storage with immutable originals. Object keys are server-chosen, never model-selected."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from .config import get_settings


class ObjectStore:
    def put_immutable(self, key: str, data: bytes) -> str:  # returns a generation token
        raise NotImplementedError

    def get(self, key: str, generation: str | None = None) -> bytes:
        raise NotImplementedError

    def exists(self, key: str) -> bool:
        raise NotImplementedError


class LocalObjectStore(ObjectStore):
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root.resolve()):
            raise ValueError("object key escapes the storage root")
        return path

    def put_immutable(self, key: str, data: bytes) -> str:
        path = self._path(key)
        digest = hashlib.sha256(data).hexdigest()
        if path.exists():
            if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise RuntimeError("immutable object already exists with different content")
            return digest[:16]
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".partial")
        tmp.write_bytes(data)
        os.replace(tmp, path)  # staged publication: write, then publish atomically
        return digest[:16]

    def get(self, key: str, generation: str | None = None) -> bytes:
        return self._path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()


class GcsObjectStore(ObjectStore):
    def __init__(self, bucket: str) -> None:
        from google.cloud import storage

        self.bucket = storage.Client().bucket(bucket)

    def put_immutable(self, key: str, data: bytes) -> str:
        blob = self.bucket.blob(key)
        try:
            blob.upload_from_string(data, if_generation_match=0)  # never overwrite an existing original
        except Exception as exc:
            if "conditionNotMet" not in str(exc) and "412" not in str(exc):
                raise
            blob.reload()
            if blob.md5_hash is None:
                raise
        return str(blob.generation)

    def get(self, key: str, generation: str | None = None) -> bytes:
        blob = self.bucket.blob(
            key, generation=int(generation) if generation and generation.isdigit() else None
        )
        return blob.download_as_bytes()

    def exists(self, key: str) -> bool:
        return self.bucket.blob(key).exists()


_store: ObjectStore | None = None


def object_store() -> ObjectStore:
    global _store
    if _store is None:
        s = get_settings()
        _store = (
            GcsObjectStore(s.gcs_bucket) if s.storage_backend == "gcs" else LocalObjectStore(s.storage_dir)
        )
    return _store
