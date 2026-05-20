from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

SUPPORTED_SCHEMA_VERSION = 1


@dataclass
class SourceManifest:
    schema_version: int = SUPPORTED_SCHEMA_VERSION
    probe_policy: dict[str, Any] = field(default_factory=dict)
    years: dict[str, dict[str, Any]] = field(default_factory=dict)
    exams: dict[str, dict[str, Any]] = field(default_factory=dict)
    files: dict[str, dict[str, Any]] = field(default_factory=dict)


def _require_mapping(value: Any, section: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"Invalid source manifest {section}: expected object")
    return value


def _require_entry_mapping(value: Any, section: str) -> dict[str, dict[str, Any]]:
    mapping = _require_mapping(value, section)
    for key, entry in mapping.items():
        if not isinstance(entry, dict):
            raise ValueError(f"Invalid source manifest {section}.{key}: expected object")
    return mapping


def source_manifest_from_data(data: dict[str, Any]) -> SourceManifest:
    schema_version = data.get("schema_version")
    if schema_version != SUPPORTED_SCHEMA_VERSION:
        raise ValueError(f"Unsupported source manifest schema_version: {schema_version}")
    return SourceManifest(
        schema_version=schema_version,
        probe_policy=_require_mapping(data.get("probe_policy", {}), "probe_policy"),
        years=_require_entry_mapping(data.get("years", {}), "years"),
        exams=_require_entry_mapping(data.get("exams", {}), "exams"),
        files=_require_entry_mapping(data.get("files", {}), "files"),
    )


def load_source_manifest(path: Path) -> SourceManifest:
    if not path.exists():
        return SourceManifest()
    data = json.loads(path.read_text(encoding="utf-8"))
    return source_manifest_from_data(data)


def write_source_manifest(path: Path, manifest: SourceManifest) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(asdict(manifest), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
