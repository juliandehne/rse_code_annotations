"""The ``human_code_inspection`` hazard plugin (see :mod:`.plugin`).

Run it on its own with ``python -m rse_annotations.plugins.hazards.human_code_inspection``.
"""

from .plugin import FACETS, STATIC_FACETS, HumanCodeInspection, InspectionData

__all__ = ["HumanCodeInspection", "InspectionData", "FACETS", "STATIC_FACETS"]
