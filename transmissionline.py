from __future__ import annotations
from dataclasses import dataclass
import math
import pytest
import pandas as pd
import numpy as np


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

    def __init__(self, name: str, bus1_name: str, bus2_name: str, r: float, x: float) -> None:
        self._name = name
        self._bus1_name = bus1_name
        self._bus2_name = bus2_name
        self._r = r
        self._x = x
        self._validate_params(name, bus1_name, bus2_name, r, x)
        self._g = self.calc_g()
        self._b = self.calc_b()
        self._admittance_matrix = self._build_admittance_matrix()


    def __repr__(self) -> str:
        # Unambiguous, developer-focused, ideally reconstructable representation
        return (
            f"TransmissionLine(name={self._name!r}, "
            f"bus1_name={self._bus1_name!r}, "
            f"bus2_name={self._bus2_name!r}, "
            f"r={self._r!r}, x={self._x!r})"
        )

    def __str__(self) -> str:
        # Human-readable summary
        return (
            f"Transmission line {self._name} "
            f"({self._bus1_name} ↔ {self._bus2_name}): "
            f"r={self._r} Ω, x={self._x} Ω, g={self._g:.6f} S"
        )
    def _validate_params(self,name:str, bus1_name:str, bus2_name:str,
                         r: float, x: float) -> None:
        if (not isinstance(name, str) or
                not isinstance(bus1_name, str) or
                    not isinstance(bus2_name, str)):
            raise ValueError("name must be a non-empty string")
        if name == "" or bus1_name == "" or bus2_name == "":
            raise ValueError("name must be a non-empty string")
        if r < 0 or x < 0:
            raise ValueError("r and x must be non-negative.")
        if r == 0 and x == 0:
            raise ValueError("r and x cannot both be zero.")

    def calc_g(self) -> float:
        """Return conductance g based on current r and x."""
        z_squared = self._r ** 2 + self._x ** 2
        return self._r / z_squared

    def calc_b(self) -> float:
        """Return susceptance b based on current r and x."""
        z_squared = self._r ** 2 + self._x ** 2
        return -self._x / z_squared

    def _build_admittance_matrix(self) -> pd.DataFrame:
        """
        Build the 2x2 admittance matrix for this transformer.

        Returns
        -------
        pd.DataFrame
            2x2 DataFrame with bus names as index and columns.
            Diagonal elements: complex admittance Y = g + jb
            Off-diagonal elements: -Y
        """
        # Complex admittance: Y = g + jb = 1/(r + jx)
        y_complex = self._g + 1j * self._b

        # Initialize DataFrame with bus names
        matrix = pd.DataFrame(
            np.zeros((2, 2), dtype=complex),
            index=[self.bus1_name, self.bus2_name],
            columns=[self.bus1_name, self.bus2_name]
        )

        # Fill diagonal: sum of admittances connected to each bus
        matrix.loc[self.bus1_name, self.bus1_name] = y_complex +1j*self.calc_g()/2
        matrix.loc[self.bus2_name, self.bus2_name] = y_complex +1j*self.calc_g()/2

        # Fill off-diagonal: negative admittance between buses
        matrix.loc[self.bus1_name, self.bus2_name] = -y_complex
        matrix.loc[self.bus2_name, self.bus1_name] = -y_complex

        return matrix

    @property
    def admittance_matrix(self) -> pd.DataFrame:
        """
        Get the 2x2 admittance matrix for this transformer.

        Returns
        -------
        pd.DataFrame
            Admittance matrix with complex values.
        """
        return self._admittance_matrix

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
        return self._r / denom

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
    with pytest.raises(ValueError):
        line = TransmissionLine("L1", "BUS1", "BUS2", r=0.0, x=0.0)
        _ = line.g
#---------------------------------------------------------------------------#
# admittance_matrix tests
#---------------------------------------------------------------------------#

def test_yprim_returns_dataframe():
    line1 = TransmissionLine("Line 1", "Bus 1", "Bus 2",
                             r=0.02, x=0.25)
    yprim = line1.admittance_matrix
    assert isinstance(yprim, pd.DataFrame), "calc_yprim() should return a pd.DataFrame"

def test_yprim_shape():
    line1 = TransmissionLine("Line 1", "Bus 1", "Bus 2",
                             r=0.02, x=0.25)
    yprim = line1.admittance_matrix
    assert yprim.shape == (2, 2), "admittance_matrix must be a 2x2 matrix"

def test_yprim_bus_labels():
    line1 = TransmissionLine("Line 1", "Bus 1", "Bus 2",
                             r=0.02, x=0.25)
    yprim = line1.admittance_matrix
    assert list(yprim.index)   == ["Bus 1", "Bus 2"]
    assert list(yprim.columns) == ["Bus 1", "Bus 2"]

def test_yprim_diagonal_elements():
    """
    Each diagonal element should equal Yseries + Yshunt/2
    (pi-model: half the shunt at each end).
    """
    line1 = TransmissionLine("Line 1", "Bus 1", "Bus 2",
                             r=0.02, x=0.25)
    yprim = line1.admittance_matrix
    expected_diag = 1/(line1.r+1j*line1.x) + 1j*line1.r /(line1.x**2+line1.r**2) *1/2
    assert math.isclose(yprim.loc["Bus 1", "Bus 1"].real, expected_diag.real, rel_tol=1e-7)
    assert math.isclose(yprim.loc["Bus 1", "Bus 1"].imag, expected_diag.imag, rel_tol=1e-7)
    assert math.isclose(yprim.loc["Bus 2", "Bus 2"].real, expected_diag.real, rel_tol=1e-7)
    assert math.isclose(yprim.loc["Bus 2", "Bus 2"].imag, expected_diag.imag, rel_tol=1e-7)

def test_yprim_off_diagonal_elements():
    """Off-diagonal elements should equal -Yseries."""
    line1 = TransmissionLine("Line 1", "Bus 1", "Bus 2",
                             r=0.02, x=0.25)
    yprim = line1.admittance_matrix
    expected_off = -1/(line1.r+1j*line1.x)
    assert math.isclose(yprim.loc["Bus 1", "Bus 2"].real, expected_off.real, rel_tol=1e-9)
    assert math.isclose(yprim.loc["Bus 1", "Bus 2"].imag, expected_off.imag, rel_tol=1e-9)
    assert math.isclose(yprim.loc["Bus 2", "Bus 1"].real, expected_off.real, rel_tol=1e-9)
    assert math.isclose(yprim.loc["Bus 2", "Bus 1"].imag, expected_off.imag, rel_tol=1e-9)

if __name__ == "__main__":
    test_g_computation_basic()
    test_g_updates_when_r_changes()
    test_g_updates_when_x_changes()
    test_invalid_name_rejected()
    test_negative_r_rejected()
    test_g_undefined_when_r_and_x_zero()
    print("Congratulations :D\nTransmission tests passed.")