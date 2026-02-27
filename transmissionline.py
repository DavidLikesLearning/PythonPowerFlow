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

    def __init__(self, name: str, bus1_name: str, bus2_name: str,
                 r: float, x: float, b: float=0, g:float=0) -> None:
        self._name = name
        self._bus1_name = bus1_name
        self._bus2_name = bus2_name
        self._r = r # series
        self._x = x # series
        self._g = g # shunt
        self._b = b # shunt
        self._validate_params()
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
    def _validate_params(self) -> None:
        if (not isinstance(self.name, str) or
                not isinstance(self.bus1_name, str) or
                    not isinstance(self.bus2_name, str)):
            raise ValueError("name must be a non-empty string")
        if self.name == "" or self.bus1_name == "" or self.bus2_name == "":
            raise ValueError("name must be a non-empty string")
        if self.r < 0 or self.x < 0 or self._g < 0 or self._b < 0:
            raise ValueError("r, x, b_shunt, g_shunt must be non-negative.")
        if self.r == 0 and self.x == 0:
            raise ValueError("r and x cannot both be zero.")


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
        # Complex admittance: Y = 1/(r + jx)
        y_complex = 1/(self._r + 1j*self._x)

        # Initialize DataFrame with bus names
        matrix = pd.DataFrame(
            np.zeros((2, 2), dtype=complex),
            index=[self.bus1_name, self.bus2_name],
            columns=[self.bus1_name, self.bus2_name]
        )

        # Fill diagonal: sum of admittances connected to each bus
        matrix.loc[self.bus1_name, self.bus1_name] = y_complex +1j*self._b/2.0
        matrix.loc[self.bus2_name, self.bus2_name] = y_complex +1j*self._b/2.0

        # Fill off-diagonal: negative admittance between buses
        matrix.loc[self.bus1_name, self.bus2_name] = -y_complex
        matrix.loc[self.bus2_name, self.bus1_name] = -y_complex

        return matrix

    @property
    def admittance_matrix(self) -> pd.DataFrame:
        """
        Get the 2x2 admittance matrix for this transmission line.

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
    def r(self, value: float):
        """Set resistance and update derived admittance and matrix."""
        self._r = value
        self._validate_params()
        self._admittance_matrix = self._build_admittance_matrix()

    # --- x ---
    @property
    def x(self) -> float:
        return self._x

    @x.setter
    def x(self, value: float) -> None:
        self._x = value
        self._validate_params()
        self._admittance_matrix = self._build_admittance_matrix()
    # --- g (computed, read-only) ---

    @property
    def g(self) -> float:
        return self._g
    @g.setter
    def g(self, value: float) -> None:
        self._g = value
        self._validate_params()
        self._admittance_matrix = self._build_admittance_matrix()

    @property
    def b(self) -> float:
        return self._b

    @b.setter
    def b(self, value: float) -> None:
        self._b = value
        self._validate_params()
        self._admittance_matrix = self._build_admittance_matrix()

def test_invalid_name_rejected():
    with pytest.raises(ValueError):
        TransmissionLine("", "BUS1", "BUS2", r=1.0, x=1.0)

def test_negative_r_rejected():
    with pytest.raises(ValueError):
        TransmissionLine("L1", "BUS1", "BUS2", r=-0.1, x=1.0)

def test_undefined_when_r_and_x_zero():
    with pytest.raises(ValueError):
        line = TransmissionLine("L1", "BUS1", "BUS2", r=0.0, x=0.0)
        assert False, f"Should be undefined when r == 0 and x == 0"
#---------------------------------------------------------------------------#
# admittance_matrix tests
#---------------------------------------------------------------------------#

def test_y_matrix_returns_dataframe():
    line1 = TransmissionLine("Line 1", "Bus 1", "Bus 2",
                             r=0.02, x=0.25)
    y_matrix = line1.admittance_matrix
    assert isinstance(y_matrix, pd.DataFrame), "calc_y_matrix() should return a pd.DataFrame"

def test_y_matrix_shape():
    line1 = TransmissionLine("Line 1", "Bus 1", "Bus 2",
                             r=0.02, x=0.25)
    y_matrix = line1.admittance_matrix
    assert y_matrix.shape == (2, 2), "admittance_matrix must be a 2x2 matrix"

def test_y_matrix_bus_labels():
    line1 = TransmissionLine("Line 1", "Bus 1", "Bus 2",
                             r=0.02, x=0.25)
    y_matrix = line1.admittance_matrix
    assert list(y_matrix.index)   == ["Bus 1", "Bus 2"]
    assert list(y_matrix.columns) == ["Bus 1", "Bus 2"]

def test_y_matrix_elements():
    """
    Each diagonal element should equal Yseries + Yshunt/2
    (pi-model: half the shunt at each end).
    """
    line1 = TransmissionLine("Line 1", "Bus 1", "Bus 2",
                             r=0.02, x=0.25, b = .03)
    y_matrix = line1.admittance_matrix
    expected_element = 1/(line1.r+1j*line1.x) + 1j*.03 *1/2
    assert y_matrix.values[0,0] - expected_element < 1e-7, f"Expected {expected_element}, got {y_matrix.values[0,0]}"
    assert y_matrix.values[1,1] - expected_element < 1e-7, f"Expected {expected_element}, got {y_matrix.values[1,1]}"
    assert y_matrix.values[0,1] + expected_element < 1e-7, f"Expected {-expected_element}, got {y_matrix.values[0,1]}"
    assert y_matrix.values[1,0] + expected_element < 1e-7, f"Expected {-expected_element}, got {y_matrix.values[1,0]}"

def test_y_matrix_off_diagonal_elements():
    """Off-diagonal elements should equal -Yseries."""
    line1 = TransmissionLine("Line 1", "Bus 1", "Bus 2",
                             r=0.02, x=0.25, b = .03)
    y_matrix = line1.admittance_matrix
    expected_off = 1/(line1.r+1j*line1.x)
    print('\nAdmittance Matrix:\n',y_matrix)
    assert y_matrix.values[0,0] - expected_off < 1e-7, f"Expected {expected_off}, got {y_matrix.values[0,0]}"
    assert y_matrix.values[1,1] - expected_off < 1e-7, f"Expected {expected_off}, got {y_matrix.values[1,1]}"
   

if __name__ == "__main__":
    test_invalid_name_rejected()
    test_negative_r_rejected()
    test_undefined_when_r_and_x_zero()
    test_y_matrix_elements()
    test_y_matrix_off_diagonal_elements()

    print("Congratulations 👌\nTransmission tests passed.")