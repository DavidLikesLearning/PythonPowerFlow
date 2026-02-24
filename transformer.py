import pandas as pd
import numpy as np
import pytest

class Transformer:
    """
    Represents a transformer modeled as a series impedance in a conductance matrix.

    Parameters
    ----------
    name : str
        Transformer identifier.
    bus1_name : str
        Connected bus name on side 1.
    bus2_name : str
        Connected bus name on side 2.
    r : float
        Series resistance (pu or ohms, consistent with system base).
    x : float
        Series reactance (pu or ohms, consistent with system base).
    g : float
        Shunt conductance
    b: float
        Shunt susceptance
    Notes
    -----
    The series admittance is computed as:
        Y = 1 / (r + jx)

    The shunt admittance is computed as:
        Y_shunt = g + jb

    The admittance matrix is a 2x2 DataFrame where:
        - [bus1, bus1] = Y + Y_shunt/2
        - [bus1, bus2] = -Y (negative admittance between buses)
        - [bus2, bus1] = -Y (negative admittance between buses)
        - [bus2, bus2] = Y + Y_shunt/2
    Example
    -------
    t = Transformer(name="T1", bus1="BusA", bus2="BusB", r=0.02, x=0.04)
    print(t.admittance_matrix)
    """
    def __init__(self, name: str, bus1_name: str, bus2_name: str,
                 r: float, x: float, g:float=0, b: float=0):
        self.name = name
        self.bus1_name = bus1_name
        self.bus2_name = bus2_name
        self._r = r # series
        self._x = x # series
        self._g = g # shunt
        self._b = b # shunt
        self._validate_params()
        self._admittance_matrix = self._build_admittance_matrix()
    
    def __repr__(self) -> str:
        return f"Transformer(name={self.name!r}, bus1_name={self.bus1_name!r}, bus2_name={self.bus2_name!r}, r={self.r}, x={self.x})"
    
    def __str__(self) -> str:
        return (f"Transformer '{self.name}': {self.bus1_name} <-> {self.bus2_name}\n"
                f"  Impedance: R={self._r:.4f}, X={self._x:.4f}\n"
                f"  Admittance: G={self._g:.4f}, B={self._b:.4f}\n"
                f"  Admittance Matrix:\n{self._admittance_matrix}")

    def _validate_params(self) -> None:
        if (not isinstance(self.name, str) or
                not isinstance(self.bus1_name, str) or
                    not isinstance(self.bus2_name, str)):
            raise ValueError("name must be a non-empty string")
        if self.name == "" or self.bus1_name == "" or self.bus2_name == "":
            raise ValueError("name must be a non-empty string")
        if self.r < 0 or self.x < 0 or self.g < 0 or self.b < 0:
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
        # Complex admittance: Y = g + jb = 1/(r + jx)
        y_complex = 1/(self.r+ 1j * self.x)
        
        # Initialize DataFrame with bus names
        matrix = pd.DataFrame(
            np.zeros((2, 2), dtype=complex),
            index=[self.bus1_name, self.bus2_name],
            columns=[self.bus1_name, self.bus2_name]
        )
        
        # Fill diagonal: sum of admittances connected to each bus
        matrix.loc[self.bus1_name, self.bus1_name] = y_complex
        matrix.loc[self.bus2_name, self.bus2_name] = y_complex
        
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

    @property
    def r(self) -> float:
        return self._r
    
    @r.setter
    def r(self, value: float):
        """Set resistance and update derived admittance and matrix."""
        self._r = value
        self._validate_params()
        self._admittance_matrix = self._build_admittance_matrix()
    
    @property
    def x(self) -> float:
        return self._x
    
    @x.setter
    def x(self, value: float):
        """Set reactance and update derived admittance and matrix."""
        self._x =  value
        self._validate_params()
        self._admittance_matrix = self._build_admittance_matrix()

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
        self._b =value
        self._validate_params()
        self._admittance_matrix = self._build_admittance_matrix()


def test_invalid_name_rejected():
    with pytest.raises(ValueError):
        Transformer("", "BUS1", "BUS2", r=1.0, x=1.0)

def test_negative_r_rejected():
    with pytest.raises(ValueError):
        Transformer("L1", "BUS1", "BUS2", r=-0.1, x=1.0)

def test_undefined_when_r_and_x_zero():
    with pytest.raises(ValueError):
        t = Transformer("L1", "BUS1", "BUS2", r=0.0, x=0.0)
        assert False, f"Should be undefined when r == 0 and x == 0"

def test_admittance_matrix_properties():
    # Test admittance matrix structure
    t = Transformer("L1", "BUS1", "BUS2", r=0.2, x=0.3)
    matrix = t.admittance_matrix
    assert isinstance(matrix, pd.DataFrame)
    assert matrix.shape == (2, 2)
    assert list(matrix.index) == ["BUS1", "BUS2"]
    assert list(matrix.columns) == ["BUS1", "BUS2"]

def test_admittance_matrix_vals():
    # Test admittance matrix values
    t = Transformer("L1", "BUS1", "BUS2", r=0.2, x=0.3)
    y_expected = 1/( t.r + 1j * t.x)
    matrix = t.admittance_matrix
    assert abs(matrix.values[0,0] - y_expected) < 1e-12
    assert abs(matrix.values[1,1] - y_expected) < 1e-12
    assert abs(matrix.values[0,1] + y_expected) < 1e-12
    assert abs(matrix.values[1,0] + y_expected) < 1e-12

def test_admittance_matrix_updates():
    # Test parameter updates trigger matrix rebuild
    t = Transformer("L1", "BUS1", "BUS2", r=0.2, x=0.3)
    t.r = 0.03
    t.x = 0.06
    y_expected = 1/( t.r + 1j * t.x)
    matrix = t.admittance_matrix
    assert abs(t.admittance_matrix.values[0,0] - y_expected) < 1e-12

if __name__ == "__main__":
    test_invalid_name_rejected()
    test_negative_r_rejected()
    test_undefined_when_r_and_x_zero()
    test_admittance_matrix_properties()
    test_admittance_matrix_vals()
    test_admittance_matrix_updates()
    print("✓ All transformer tests passed")


