"""
Settings — simulation clock and the adjustable parameters W, R, L, T
(Sections 3, 7, 9 and 10).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional


class SettingsMixin:
    """Advance the clock and update the parameters."""

    def advance_clock(self, hours: float) -> datetime:
        """Move the simulation clock forward; it never goes back (Section 3)."""
        if not hours > 0:
            raise ValueError(f"Las horas a avanzar deben ser positivas, se recibió {hours}")
        before = self.snapshot()
        self.clock += timedelta(hours=hours)
        self._record("ADVANCE_CLOCK", before,
                     f"Avanzar reloj {hours}h hasta {self.clock.isoformat()}")
        return self.clock

    def update_parameters(self, w_hours: Optional[float] = None,
                          r_km: Optional[float] = None,
                          l_depth: Optional[int] = None,
                          t_archive_hours: Optional[float] = None) -> None:
        """Change W, R, L and/or T as one action. Nothing changes if any value is invalid."""
        errors = _parameter_errors(w_hours, r_km, l_depth, t_archive_hours)
        if errors:
            raise ValueError("; ".join(errors))

        before = self.snapshot()
        if w_hours is not None:
            self.W_hours = float(w_hours)
        if r_km is not None:
            self.R_km = float(r_km)
        if l_depth is not None:
            self.L_depth = int(l_depth)
        if t_archive_hours is not None:
            self.T_archive_hours = float(t_archive_hours)

        # A change of W or R can change associations (Section 7).
        self.recalculate_all_associations()
        self._record("PARAM_UPDATE", before,
                     f"Actualizar parámetros W={self.W_hours}h R={self.R_km}km "
                     f"L={self.L_depth} T={self.T_archive_hours}h")


def _parameter_errors(w_hours, r_km, l_depth, t_archive_hours) -> list[str]:
    errors = []
    if w_hours is not None and not w_hours > 0:
        errors.append(f"W debe ser positivo, se recibió {w_hours}")
    if r_km is not None and not r_km > 0:
        errors.append(f"R debe ser positivo, se recibió {r_km}")
    if l_depth is not None and (int(l_depth) != l_depth or l_depth < 0):
        errors.append(f"L debe ser un entero no negativo, se recibió {l_depth}")
    if t_archive_hours is not None and not t_archive_hours > 0:
        errors.append(f"T debe ser positivo, se recibió {t_archive_hours}")
    return errors
