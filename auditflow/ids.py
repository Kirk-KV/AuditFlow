from __future__ import annotations

import re

from auditflow.errors import AuditFlowDataError


WORKPAPER_REF_PATTERN = re.compile(r"^WP-[A-Za-z0-9_-]+$")

_UNSAFE_RUN = re.compile(r"[^A-Za-z0-9_-]+")


def is_safe_workpaper_ref(value: str) -> bool:
    """Return True when the reference can be used as a file name unchanged."""

    return bool(WORKPAPER_REF_PATTERN.fullmatch(value))


def ref_fragment(value: str) -> str:
    """Reduce a company-defined identifier to the characters allowed in a reference.

    Control identifiers come from the auditee's own control framework and may
    contain spaces, dots, slashes, or non-Latin letters. Everything outside
    [A-Za-z0-9_-] collapses into a single hyphen. The result can be empty, which
    the caller handles by falling back to the test identifier.
    """

    return _UNSAFE_RUN.sub("-", value).strip("-_")


def build_workpaper_ref(
    *,
    control_id: str | None,
    test_id: str,
    taken: set[str],
    preferred: str | None = None,
) -> str:
    """Return a unique, file-name-safe workpaper reference and reserve it.

    The reference is the identity of a workpaper file, so it is assigned once and
    then preserved: `preferred` carries the reference an earlier run already gave
    this row, which keeps file names stable when the audit program is regenerated
    after new controls are added.

    When no usable reference exists, the reference is derived from `control_id`,
    and falls back to `test_id` when the control identifier reduces to nothing or
    would collide with a reference already in use. Collisions are resolved rather
    than allowed, because two program rows sharing one reference would silently
    overwrite each other's workpaper.
    """

    occupied = {ref.casefold() for ref in taken}
    if preferred and is_safe_workpaper_ref(preferred) and preferred.casefold() not in occupied:
        taken.add(preferred)
        return preferred

    candidate = ""
    if control_id:
        fragment = ref_fragment(control_id)
        if fragment:
            candidate = f"WP-{fragment}"

    if not candidate or candidate.casefold() in occupied:
        candidate = f"WP-{test_id}"

    if candidate.casefold() in occupied:
        suffix = 2
        while f"{candidate}-{suffix}".casefold() in occupied:
            suffix += 1
        candidate = f"{candidate}-{suffix}"

    taken.add(candidate)
    return candidate


def require_safe_workpaper_ref(value: str, context: str) -> str:
    """Return the reference, or explain why it cannot become a file name."""

    if not is_safe_workpaper_ref(value):
        raise AuditFlowDataError(
            f"{context}: workpaper_ref {value!r} cannot be used as a file name. "
            "It must look like WP-C-001 and use only letters, digits, '-' and '_'. "
            "Run 'auditflow create audit-program' to regenerate valid references."
        )
    return value
