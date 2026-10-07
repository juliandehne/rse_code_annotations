"""The base of every enum in this package: named values that still are plain text.

Instead of writing a "magic string" such as ``"warn"`` in many places, the allowed values
are listed once, as members of an enum (``Severity.WARN``). The editor can then complete
and check them, and a typo is an error instead of a silently different string.

The enums of the package:

==================================================  ==============================
enum                                                what it lists
==================================================  ==============================
:class:`~rse_annotations.core.plugin.Mode`          the features a plugin can offer
:class:`~rse_annotations.core.plugin.Phase`         when a plugin's analysis runs
:class:`~rse_annotations.core.findings.Severity`    how bad one finding is
:class:`~rse_annotations.core.findings.Status`      the outcome of a plugin or check
``rse_annotations.inspection.verdicts.Decision``    what a reviewer decided
``rse_annotations.reporting.renderers.OutputFormat``  the output formats
``...human_code_inspection.plugin.Facet``           the parts of the human code inspection
``rse_annotations.decorators.markers.HazardDecorator``  the review concerns (decorators)
==================================================  ==============================
"""

from __future__ import annotations

from enum import Enum


class TextEnum(str, Enum):
    """An enum whose members are also strings: ``Severity.WARN == "warn"``.

    So a member is written to YAML/JSON as plain text, prints as its value (also in
    f-strings), and can be looked up in a dict or set by the plain string.
    """

    __hash__ = str.__hash__   # {Severity.WARN: 1}["warn"] works

    def __str__(self) -> str:   # "warn", not "Severity.WARN"
        return self.value
