from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

import yaml


MANIFEST_RELATIVE_PATH = Path("04_evidence") / "evidence_manifest.yml"
HASH_ALGORITHM = "sha256"
SCHEMA_VERSION = 1
HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
EXCLUDED_ROOT_FILES = {"evidence_manifest.yml", "README.md"}
EXCLUDED_FILE_NAMES = {".gitkeep", ".DS_Store", "Thumbs.db", "desktop.ini"}
VERSIONED_PATH_PREFIXES = ("02_raw_data/scripts/",)


class EvidenceManifestError(ValueError):
    """Raised when evidence cannot be scanned or its manifest is invalid."""


@dataclass(frozen=True, order=True)
class EvidenceFile:
    path: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True)
class EvidenceChange:
    kind: str
    path: str
    expected_sha256: str | None = None
    actual_sha256: str | None = None
    expected_size_bytes: int | None = None
    actual_size_bytes: int | None = None


@dataclass(frozen=True)
class EvidenceComparison:
    manifest_exists: bool
    manifest_files: tuple[EvidenceFile, ...]
    current_files: tuple[EvidenceFile, ...]
    changes: tuple[EvidenceChange, ...]

    @property
    def clean(self) -> bool:
        return self.manifest_exists and not self.changes


@dataclass(frozen=True)
class EvidenceRefreshResult:
    manifest_path: Path
    changed: bool
    files: tuple[EvidenceFile, ...]
    previous_changes: tuple[EvidenceChange, ...]


def _evidence_root(project_root: Path) -> Path:
    root = project_root.resolve()
    evidence_root = (root / "04_evidence").resolve()
    try:
        evidence_root.relative_to(root)
    except ValueError as exc:
        raise EvidenceManifestError(
            "Evidence folder resolves outside the audit project."
        ) from exc
    if not evidence_root.exists():
        raise EvidenceManifestError("Missing evidence folder: 04_evidence")
    if not evidence_root.is_dir():
        raise EvidenceManifestError("04_evidence must be a directory")
    return evidence_root


def _hash_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    try:
        before = path.stat()
        with path.open("rb") as file:
            while chunk := file.read(1024 * 1024):
                digest.update(chunk)
        after = path.stat()
    except OSError as exc:
        raise EvidenceManifestError(f"Cannot read evidence file {path}: {exc}") from exc
    if before.st_size != after.st_size or before.st_mtime_ns != after.st_mtime_ns:
        raise EvidenceManifestError(
            f"Evidence file changed while it was being hashed: {path}"
        )
    return digest.hexdigest(), after.st_size


def _is_metadata_file(relative_path: Path | PurePosixPath) -> bool:
    if relative_path.name in EXCLUDED_FILE_NAMES:
        return True
    return len(relative_path.parts) == 1 and relative_path.name in EXCLUDED_ROOT_FILES


def _is_scan_excluded(relative_path: Path | PurePosixPath) -> bool:
    if _is_metadata_file(relative_path):
        return True
    path = relative_path.as_posix()
    return any(path.startswith(prefix) for prefix in VERSIONED_PATH_PREFIXES)


def scan_evidence(project_root: Path) -> tuple[EvidenceFile, ...]:
    evidence_root = _evidence_root(project_root)
    files: list[EvidenceFile] = []
    for path in sorted(evidence_root.rglob("*")):
        if path.is_symlink():
            relative_path = path.relative_to(evidence_root).as_posix()
            raise EvidenceManifestError(
                f"Evidence symlinks are not supported: 04_evidence/{relative_path}"
            )
        if not path.is_file():
            continue
        relative_path = path.relative_to(evidence_root)
        if _is_scan_excluded(relative_path):
            continue
        resolved_path = path.resolve()
        try:
            resolved_path.relative_to(evidence_root)
        except ValueError as exc:
            raise EvidenceManifestError(
                f"Evidence file resolves outside 04_evidence: {relative_path.as_posix()}"
            ) from exc
        sha256, size_bytes = _hash_file(path)
        files.append(
            EvidenceFile(
                path=relative_path.as_posix(),
                sha256=sha256,
                size_bytes=size_bytes,
            )
        )
    return tuple(sorted(files))


def _parse_file_entry(entry: Any, index: int) -> EvidenceFile:
    if not isinstance(entry, dict):
        raise EvidenceManifestError(f"Manifest files[{index}] must be a mapping")
    unknown_fields = sorted(set(entry) - {"path", "sha256", "size_bytes"})
    if unknown_fields:
        raise EvidenceManifestError(
            f"Manifest files[{index}] has unknown field(s): "
            f"{', '.join(unknown_fields)}"
        )

    path = str(entry.get("path") or "").strip().replace("\\", "/")
    pure_path = PurePosixPath(path)
    if (
        not path
        or path != pure_path.as_posix()
        or pure_path.is_absolute()
        or ".." in pure_path.parts
        or ":" in path
        or any(ord(character) < 32 for character in path)
    ):
        raise EvidenceManifestError(
            f"Manifest files[{index}].path must be a safe relative path"
        )
    if _is_metadata_file(pure_path):
        raise EvidenceManifestError(
            f"Manifest files[{index}].path is reserved metadata: {path}"
        )
    sha256 = str(entry.get("sha256") or "").strip().lower()
    if not HASH_PATTERN.fullmatch(sha256):
        raise EvidenceManifestError(
            f"Manifest files[{index}].sha256 must be a 64-character SHA-256 digest"
        )
    size_bytes = entry.get("size_bytes")
    if isinstance(size_bytes, bool) or not isinstance(size_bytes, int) or size_bytes < 0:
        raise EvidenceManifestError(
            f"Manifest files[{index}].size_bytes must be a non-negative integer"
        )
    return EvidenceFile(path=path, sha256=sha256, size_bytes=size_bytes)


def load_evidence_manifest(project_root: Path) -> tuple[EvidenceFile, ...]:
    manifest_path = project_root.resolve() / MANIFEST_RELATIVE_PATH
    if not manifest_path.exists():
        raise EvidenceManifestError(
            "Evidence manifest not found: 04_evidence/evidence_manifest.yml. "
            "Run 'auditflow evidence refresh' to create it."
        )
    try:
        data = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise EvidenceManifestError(f"Cannot read evidence manifest: {exc}") from exc
    if not isinstance(data, dict):
        raise EvidenceManifestError("Evidence manifest must contain a YAML mapping")
    unknown_fields = sorted(set(data) - {"schema_version", "hash_algorithm", "files"})
    if unknown_fields:
        raise EvidenceManifestError(
            f"Evidence manifest has unknown field(s): {', '.join(unknown_fields)}"
        )
    if data.get("schema_version") != SCHEMA_VERSION:
        raise EvidenceManifestError(
            f"Evidence manifest schema_version must be {SCHEMA_VERSION}"
        )
    if data.get("hash_algorithm") != HASH_ALGORITHM:
        raise EvidenceManifestError(
            f"Evidence manifest hash_algorithm must be {HASH_ALGORITHM}"
        )
    entries = data.get("files", [])
    if not isinstance(entries, list):
        raise EvidenceManifestError("Evidence manifest files must be a list")
    files = tuple(_parse_file_entry(entry, index) for index, entry in enumerate(entries))
    paths = [item.path for item in files]
    if len(paths) != len({path.casefold() for path in paths}):
        raise EvidenceManifestError("Evidence manifest contains duplicate file paths")
    if paths != sorted(paths):
        raise EvidenceManifestError("Evidence manifest file paths must be sorted")
    return files


def compare_evidence(project_root: Path) -> EvidenceComparison:
    manifest_path = project_root.resolve() / MANIFEST_RELATIVE_PATH
    manifest_exists = manifest_path.exists()
    manifest_files = load_evidence_manifest(project_root) if manifest_exists else ()
    current_files = scan_evidence(project_root)
    expected_by_path = {item.path: item for item in manifest_files}
    current_by_path = {item.path: item for item in current_files}
    changes: list[EvidenceChange] = []

    for path in sorted(current_by_path.keys() - expected_by_path.keys()):
        current = current_by_path[path]
        changes.append(
            EvidenceChange(
                kind="added",
                path=path,
                actual_sha256=current.sha256,
                actual_size_bytes=current.size_bytes,
            )
        )
    for path in sorted(expected_by_path.keys() - current_by_path.keys()):
        expected = expected_by_path[path]
        changes.append(
            EvidenceChange(
                kind="missing",
                path=path,
                expected_sha256=expected.sha256,
                expected_size_bytes=expected.size_bytes,
            )
        )
    for path in sorted(expected_by_path.keys() & current_by_path.keys()):
        expected = expected_by_path[path]
        current = current_by_path[path]
        if (
            expected.sha256 != current.sha256
            or expected.size_bytes != current.size_bytes
        ):
            changes.append(
                EvidenceChange(
                    kind="modified",
                    path=path,
                    expected_sha256=expected.sha256,
                    actual_sha256=current.sha256,
                    expected_size_bytes=expected.size_bytes,
                    actual_size_bytes=current.size_bytes,
                )
            )
    return EvidenceComparison(
        manifest_exists=manifest_exists,
        manifest_files=manifest_files,
        current_files=current_files,
        changes=tuple(changes),
    )


def _manifest_data(files: tuple[EvidenceFile, ...]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "hash_algorithm": HASH_ALGORITHM,
        "files": [
            {
                "path": item.path,
                "sha256": item.sha256,
                "size_bytes": item.size_bytes,
            }
            for item in files
        ],
    }


def refresh_evidence_manifest(project_root: Path) -> EvidenceRefreshResult:
    comparison = compare_evidence(project_root)
    manifest_path = project_root.resolve() / MANIFEST_RELATIVE_PATH
    changed = (
        not comparison.manifest_exists
        or comparison.manifest_files != comparison.current_files
    )
    if changed:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            yaml.safe_dump(
                _manifest_data(comparison.current_files),
                allow_unicode=True,
                sort_keys=False,
                width=120,
            ),
            encoding="utf-8",
        )
    return EvidenceRefreshResult(
        manifest_path=manifest_path,
        changed=changed,
        files=comparison.current_files,
        previous_changes=comparison.changes,
    )
