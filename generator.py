from __future__ import annotations
import math
import pytest
from typing import Optional

from settings import grid_settings

class Generator:
    """
    Generator model.

    Attributes:
        name: Name of the generator (non-empty string).
        bus_name: Name of the connected bus (non-empty string).
        mw_setpoint: Active power setpoint in MW (float).
        v_setpoint: Voltage magnitude setpoint in p.u. (float or None).
        p: per unit real power injection (float).
    """

    def __init__(
        self,
        name: str,
        bus_name: str,
        mw_setpoint: float,
        v_setpoint: float | None = None,
    ) -> None:
        # store raw values first so __repr__ is safe even if validation fails
        self._name = name
        self._bus_name = bus_name
        self._mw_setpoint = mw_setpoint
        self._v_setpoint = v_setpoint
        self._p = None  # will be set by calc_p()
        self._validate_params(name, bus_name, mw_setpoint, v_setpoint)

    # ------------------------------------------------------------------
    # Representation
    # ------------------------------------------------------------------
    def __repr__(self) -> str:
        return (
            f"Generator(name={self._name!r}, "
            f"bus_name={self._bus_name!r}, "
            f"mw_setpoint={self._mw_setpoint!r}, "
            f"v_setpoint={self._v_setpoint!r})"
        )

    def __str__(self) -> str:
        base = (
            f"Generator {self._name} at bus {self._bus_name}: "
            f"P={self._mw_setpoint} MW"
        )
        if self._v_setpoint is not None:
            base += f", Vset={self._v_setpoint} p.u."
        return base

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------
    def _validate_params(
        self,
        name: str,
        bus_name: str,
        mw_setpoint: float,
        v_setpoint: float | None,
    ) -> None:
        # basic string checks
        if (
            not isinstance(name, str)
            or not isinstance(bus_name, str)
            or not name.strip()
            or not bus_name.strip()
        ):
            raise ValueError("name and bus_name must be non-empty strings")

        # numeric checks
        mw = self._as_float(mw_setpoint, "mw_setpoint")
        if not math.isfinite(mw):
            raise ValueError("mw_setpoint must be finite")

        if v_setpoint is not None:
            v = self._as_float(v_setpoint, "v_setpoint")
            if v <= 0:
                raise ValueError("v_setpoint must be positive when provided")

    @staticmethod
    def _as_float(value: int | float, field: str) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{field} must be a number")
        return float(value)
    
    def calc_p(self) -> float:
        """Calculate and update per unit real power injection based on base MVA."""
        self._p = self.mw_setpoint / grid_settings.sbase
        return self._p

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------
    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("name must be a non-empty string")
        self._name = value.strip()

    @property
    def bus_name(self) -> str:
        return self._bus_name

    @bus_name.setter
    def bus_name(self, value: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("bus_name must be a non-empty string")
        self._bus_name = value.strip()

    @property
    def mw_setpoint(self) -> float:
        return self._mw_setpoint

    @mw_setpoint.setter
    def mw_setpoint(self, value: float) -> None:
        v = self._as_float(value, "mw_setpoint")
        if not math.isfinite(v):
            raise ValueError("mw_setpoint must be finite")
        self._mw_setpoint = v

    @property
    def v_setpoint(self) -> float | None:
        return self._v_setpoint

    @v_setpoint.setter
    def v_setpoint(self, value: float | None) -> None:
        if value is None:
            self._v_setpoint = None
            return
        v = self._as_float(value, "v_setpoint")
        if v <= 0:
            raise ValueError("v_setpoint must be positive when provided")
        self._v_setpoint = v

    @property
    def p(self) -> Optional[float]:
        """Per unit real power injection, updated by calc_p()."""
        return self._p

def main():
    pass


if __name__ == "__main__":
    main()
