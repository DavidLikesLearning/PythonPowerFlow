from __future__ import annotations
from dataclasses import dataclass
import math
import pytest


@dataclass
class TransmissionLine:
    """
    Transmission line model.

    Attributes:
        name: Identifier for the line.
        bus1_name: From-bus name.
        bus2_name: To-bus name.
        r: Series resistance (ohms).
        x: Series reactance (ohms).
        g: Series conductance (siemens), computed as r / (r^2 + x^2).
    """

    def __init__(self, name: str, bus1_name: str, bus2_name: str, r: float, x: float):
        self.name = name
        self.bus1_name = bus1_name
        self.bus2_name = bus2_name
        self._validate_params(r, x)
        self._r = r
        self._x = x


    def __repr__(self) -> str:
        # Unambiguous, developer-focused, ideally reconstructable representation
        return (
            f"TransmissionLine(name={self.name!r}, "
            f"bus1_name={self.bus1_name!r}, "
            f"bus2_name={self.bus2_name!r}, "
            f"r={self.r!r}, x={self.x!r})"
        )

    def __str__(self) -> str:
        # Human-readable summary
        return (
            f"Transmission line {self.name} "
            f"({self.bus1_name} ↔ {self.bus2_name}): "
            f"r={self.r} Ω, x={self.x} Ω, g={self.g:.6f} S"
        )
    def _validate_params(self, r: float, x: float) -> None:
        if r < 0 or x < 0:
            raise ValueError("r and x must be non-negative.")
        if r == 0 and x == 0:
            raise ValueError("r and x cannot both be zero.")

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

    # --- bus2_name ---
    @property
    def bus2_name(self) -> str:
        return self._bus2_name

    @bus2_name.setter
    def bus2_name(self, value: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("bus2_name must be a non-empty string")
        self._bus2_name = value.strip()

    @property
    def r(self) -> float:
        return self._r

    @r.setter
    def r(self, value: float) -> None:
        value = float(value)
        if value < 0:
            raise ValueError("r must be >= 0")
        self._r = value

    # --- x ---
    @property
    def x(self) -> float:
        return self._x

    @x.setter
    def x(self, value: float) -> None:
        value = float(value)
        # Allow negative x if you want to model capacitive series reactance.
        self._x = value

    # --- g (computed, read-only) ---
    @property
    def g(self) -> float:
        denom = (self.r ** 2) + (self.x ** 2)
        if denom == 0:
            raise ZeroDivisionError("g is undefined when r == 0 and x == 0")
        return self.r / denom

    # Optional: keep your original method name (but corrected spelling)
    def calc_g(self) -> float:
        return self.g

def test_g_computation_basic():
    line = TransmissionLine("L1", "BUS1", "BUS2", r=1.0, x=1.0)
    assert math.isclose(line.g, 0.5, rel_tol=0, abs_tol=1e-12)

def test_g_updates_when_r_changes():
    line = TransmissionLine("L1", "BUS1", "BUS2", r=1.0, x=1.0)
    line.r = 2.0
    assert math.isclose(line.g, 2.0 / (4.0 + 1.0), rel_tol=0, abs_tol=1e-12)

def test_g_updates_when_x_changes():
    line = TransmissionLine("L1", "BUS1", "BUS2", r=2.0, x=1.0)
    line.x = 3.0
    assert math.isclose(line.g, 2.0 / (4.0 + 9.0), rel_tol=0, abs_tol=1e-12)

def test_invalid_name_rejected():
    with pytest.raises(ValueError):
        TransmissionLine("", "BUS1", "BUS2", r=1.0, x=1.0)

def test_negative_r_rejected():
    with pytest.raises(ValueError):
        TransmissionLine("L1", "BUS1", "BUS2", r=-0.1, x=1.0)

def test_g_undefined_when_r_and_x_zero():
    line = TransmissionLine("L1", "BUS1", "BUS2", r=0.0, x=0.0)
    with pytest.raises(ValueError):
        _ = line.g

if __name__ == "__main__":
    test_g_computation_basic()
    test_g_updates_when_r_changes()
    test_g_updates_when_x_changes()
    test_invalid_name_rejected()
    test_negative_r_rejected()
    test_g_undefined_when_r_and_x_zero()
    print("Congratulations :D\nTransmission tests passed.")