from __future__ import annotations


class AuditFlowError(Exception):
    """Base class for failures that are shown to the auditor without a traceback.

    Commands raise subclasses of this error for situations an auditor can fix,
    such as a missing prerequisite file or an inconsistent audit project. The CLI
    prints the message and exits with a non-zero status. Anything that is not an
    AuditFlowError is treated as a defect and keeps its traceback.
    """


class AuditFlowFileError(AuditFlowError):
    """Raised when a required project file is missing or cannot be read."""


class AuditFlowDataError(AuditFlowError):
    """Raised when a project file is readable but does not hold the expected data."""
