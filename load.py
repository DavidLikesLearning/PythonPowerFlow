from __future__ import annotations
from dataclasses import dataclass
import math
import pytest
from typing import Optional

from settings import grid_settings

@dataclass
class Load:
    """
    Load model.

    Attributes:
        name: Identifier for the load.
        bus1_name: Bus name where the load is connected.
        mw: Real power (megawatts).
        mvar: Reactive power (megavolt-amperes reactive).
        mva: Apparent power (megavolt-amperes), computed as sqrt(mw^2 + mvar^2).
    """

    def __init__(self, name: str, bus1_name: str, mw: float, mvar: float):
        self._name = name
        self._bus1_name = bus1_name
        self._mw = mw
        self._mvar = mvar
        self._p = None  # will be set by calc_p()
        self._q = None  # will be set by calc_q()
        self._validate_params(name, bus1_name, mw, mvar)

    def __repr__(self) -> str:
        # Unambiguous, developer-focused, ideally reconstructable representation
        return (
            f"Load(name={self._name!r}, "
            f"bus1_name={self._bus1_name!r}, "
            f"mw={self._mw!r}, mvar={self._mvar!r})"
        )

    def __str__(self) -> str:
        # Human-readable summary
        return (
            f"Load {self._name} "
            f"at {self._bus1_name}: "
            f"mw={self._mw} MW, mvar={self._mvar} MVAr, mva={self.mva:.6f} MVA"
        )

    def _validate_params(self, name: str, bus1_name: str,
                         mw: float, mvar: float) -> None:
        if (not isinstance(name, str) or
                not isinstance(bus1_name, str)):
            raise ValueError("name and bus1_name must be non-empty strings")

        if name == "" or bus1_name == "":
            raise ValueError("name and bus1_name must be non-empty strings")

        # No specific constraints on mw and mvar values (can be positive, negative, or zero)
    def calc_p(self) -> float:
        """Calculate and update per unit real power injection based on base MVA."""
        self._p = self.mw / grid_settings.sbase
        return self._p
    
    def calc_q(self) -> float:
        """Calculate and update per unit reactive power injection based on base MVA."""
        self._q = self.mvar / grid_settings.sbase
        return self._q

    @staticmethod
    def _as_float(value: int | float, field: str) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{field} must be a number")
        return float(value)

    # --- name ---
    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("name must be a non-empty string")
        self._name = value.strip()

    # --- bus1_name ---
    @property
    def bus1_name(self) -> str:
        return self._bus1_name

    @bus1_name.setter
    def bus1_name(self, value: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("bus1_name must be a non-empty string")
        self._bus1_name = value.strip()

    # --- mw ---
    @property
    def mw(self) -> float:
        return self._mw

    @mw.setter
    def mw(self, value: float) -> None:
        self._mw = float(value)

    # --- mvar ---
    @property
    def mvar(self) -> float:
        return self._mvar

    @mvar.setter
    def mvar(self, value: float) -> None:
        self._mvar = float(value)

    # --- mva (computed, read-only) ---
    @property
    def mva(self) -> float:
        return math.sqrt(self.mw ** 2 + self.mvar ** 2)
    
    @property
    def p(self) -> Optional[float]:
        """Per unit real power injection, updated by calc_p()."""
        return self._p

    @property
    def q(self) -> Optional[float]:
        """Per unit reactive power injection, updated by calc_q()."""
        return self._q

def main():
    pass



if __name__ == "__main__":
   main()
