"""
Adapter for FaIR 2.x.

Separate from the existing ``fair_adapter`` (FaIR 1.6) so the two run
side-by-side: FaIR 1.6 keeps working for downstream users that depend
on its outputs, while ``FaIRv2`` (this adapter) handles the AR7-relevant
calibrations and the xarray-batched ensemble API of FaIR 2.x.
"""
from .fair2_adapter import FAIR2

__all__ = ["FAIR2"]
