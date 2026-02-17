from __future__ import annotations
from dataclasses import dataclass
import math
import pytest

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


# --- Tests ---

def test_mva_computation_basic():
    load = Load("LOAD1", "BUS1", mw=3.0, mvar=4.0)
    assert math.isclose(load.mva, 5.0, rel_tol=0, abs_tol=1e-12)


def test_mva_updates_when_mw_changes():
    load = Load("LOAD1", "BUS1", mw=3.0, mvar=4.0)
    load.mw = 6.0
    assert math.isclose(load.mva, math.sqrt(36.0 + 16.0), rel_tol=0, abs_tol=1e-12)


def test_mva_updates_when_mvar_changes():
    load = Load("LOAD1", "BUS1", mw=3.0, mvar=4.0)
    load.mvar = 8.0
    assert math.isclose(load.mva, math.sqrt(9.0 + 64.0), rel_tol=0, abs_tol=1e-12)


def test_invalid_name_rejected():
    with pytest.raises(ValueError):
        Load("", "BUS1", mw=1.0, mvar=1.0)


def test_invalid_bus1_name_rejected():
    with pytest.raises(ValueError):
        Load("LOAD1", "", mw=1.0, mvar=1.0)


def test_zero_load():
    load = Load("LOAD1", "BUS1", mw=0.0, mvar=0.0)
    assert math.isclose(load.mva, 0.0, rel_tol=0, abs_tol=1e-12)


if __name__ == "__main__":
    test_mva_computation_basic()
    test_mva_updates_when_mw_changes()
    test_mva_updates_when_mvar_changes()
    test_invalid_name_rejected()
    test_invalid_bus1_name_rejected()
    test_zero_load()
    print("Congratulations :D\nLoad tests passed.")
