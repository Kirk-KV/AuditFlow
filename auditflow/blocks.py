from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Callable

import yaml


AUTO_BLOCK_RE = re.compile(
    r"<!-- AUTO:(?P<name>[A-Z0-9_]+) START -->.*?<!-- AUTO:(?P=name) END -->",
    re.DOTALL,
)

FRONT_MATTER_RE = re.compile(r"\A---\n(?P<yaml>.*?)\n---\n?", re.DOTALL)

DIGEST_KEY = "observations_digest"

REPORT_BLOCK_NAMES = (
    "COVER",
    "AUDIT_FACTS",
    "SUMMARY_OBSERVATIONS",
    "DETAILED_OBSERVATIONS",
    "DISTRIBUTION_TEAM",
)

ARCHIVE_BLOCK_NAMES = (
    "COVER",
    "ONE_PAGE_STORY",
    "INITIAL_ASSUMPTIONS",
    "PLANNING_DECISIONS",
    "SCOPE_RISK_EVOLUTION",
    "TESTING_TRACEABILITY",
    "OBSERVATIONS_OUTCOME",
    "EVIDENCE_MAP",
)


def present_block_names(content: str) -> set[str]:
    return {match.group("name") for match in AUTO_BLOCK_RE.finditer(content)}


def missing_block_names(content: str, expected: tuple[str, ...]) -> tuple[str, ...]:
    """Return expected AUTO blocks whose markers are absent from the document.

    A deleted marker is not something the generator can repair, because the
    auditor owns the document layout. It does mean the generated content silently
    stops appearing, so callers report it instead of treating the document as
    up to date.
    """

    present = present_block_names(content)
    return tuple(name for name in expected if name not in present)


def replace_auto_blocks(content: str, blocks: dict[str, str]) -> str:
    def repl(match: re.Match[str]) -> str:
        name = match.group("name")
        replacement = blocks.get(name, "").strip()
        return f"<!-- AUTO:{name} START -->\n{replacement}\n<!-- AUTO:{name} END -->"

    return AUTO_BLOCK_RE.sub(repl, content)


def read_front_matter(content: str) -> dict[str, Any]:
    """Return the YAML front matter of a QMD document, or an empty mapping."""

    match = FRONT_MATTER_RE.match(content)
    if not match:
        return {}
    try:
        front_matter = yaml.safe_load(match.group("yaml")) or {}
    except yaml.YAMLError:
        return {}
    return front_matter if isinstance(front_matter, dict) else {}


def update_front_matter(
    content: str,
    update: Callable[[dict[str, Any]], None],
) -> str:
    """Apply `update` to the document's front matter and rewrite it in place.

    Documents without front matter are returned unchanged, because AuditFlow does
    not add a header the auditor chose to remove.
    """

    match = FRONT_MATTER_RE.match(content)
    if not match:
        return content

    try:
        front_matter = yaml.safe_load(match.group("yaml")) or {}
    except yaml.YAMLError:
        return content
    if not isinstance(front_matter, dict):
        return content

    update(front_matter)

    body = content[match.end() :]
    rendered = yaml.safe_dump(
        front_matter,
        sort_keys=False,
        allow_unicode=True,
        width=120,
    ).strip()
    return f"---\n{rendered}\n---\n\n{body.lstrip()}"


def stamp_observations_digest(front_matter: dict[str, Any], digest: str) -> None:
    """Record which observations a generated document was built from."""

    auditflow_metadata = front_matter.get("auditflow")
    if not isinstance(auditflow_metadata, dict):
        auditflow_metadata = {}
        front_matter["auditflow"] = auditflow_metadata
    auditflow_metadata[DIGEST_KEY] = digest


def stamped_observations_digest(content: str) -> str:
    """Return the digest a generated document was stamped with, if any."""

    auditflow_metadata = read_front_matter(content).get("auditflow")
    if not isinstance(auditflow_metadata, dict):
        return ""
    return str(auditflow_metadata.get(DIGEST_KEY) or "")


def observations_digest(project_root: Path) -> str:
    """Fingerprint the observation files a report or archive is generated from.

    The digest is stamped into the generated document so validation can tell an
    up-to-date report from one written before the observations last changed.
    Each part is length-prefixed so no combination of names and content can
    produce the same digest as a different set of files.
    """

    digest = hashlib.sha256()
    observations_dir = project_root / "06_observations"
    if observations_dir.exists():
        for path in sorted(observations_dir.glob("OBS-*.yml")):
            # Checkout can change line endings without changing observations.
            content = path.read_bytes().replace(b"\r\n", b"\n")
            for part in (path.name.encode("utf-8"), content):
                digest.update(str(len(part)).encode("ascii"))
                digest.update(b":")
                digest.update(part)
    return digest.hexdigest()
