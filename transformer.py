import pandas as pd
import numpy as np

class Transformer:
    """
    Represents a transformer modeled as a series impedance in a conductance matrix.

    Parameters
    ----------
    name : str
        Transformer identifier.
    bus1 : str
        Connected bus name on side 1.
    bus2 : str
        Connected bus name on side 2.
    r : float
        Series resistance (pu or ohms, consistent with system base).
    x : float
        Series reactance (pu or ohms, consistent with system base).

    Notes
    -----
    The series admittance is computed as:
        Y = 1 / (r + jx)
        g = r / (r^2 + x^2)
        b = -x / (r^2 + x^2)

    The admittance matrix is a 2x2 DataFrame where:
        - [bus1, bus1] = Y (sum of admittances connected to bus1)
        - [bus1, bus2] = -Y (negative admittance between buses)
        - [bus2, bus1] = -Y (negative admittance between buses)
        - [bus2, bus2] = Y (sum of admittances connected to bus2)

    Example
    -------
    t = Transformer(name="T1", bus1="BusA", bus2="BusB", r=0.02, x=0.04)
    print(t.admittance_matrix)
    """
    def __init__(self, name: str, bus1_name: str, bus2_name: str, r: float, x: float):
        self.name = name
        self.bus1_name = bus1_name
        self.bus2_name = bus2_name
        self._validate_params(r, x)
        self._r = r
        self._x = x
        self._g = self.calc_g()
        self._b = self.calc_b()
        self._admittance_matrix = self._build_admittance_matrix()
    
    def __repr__(self) -> str:
        return f"Transformer(name={self.name!r}, bus1_name={self.bus1_name!r}, bus2_name={self.bus2_name!r}, r={self._r}, x={self._x})"
    
    def __str__(self) -> str:
        return (f"Transformer '{self.name}': {self.bus1_name} <-> {self.bus2_name}\n"
                f"  Impedance: R={self._r:.6f}, X={self._x:.6f}\n"
                f"  Admittance: G={self._g:.6f}, B={self._b:.6f}\n"
                f"  Admittance Matrix:\n{self._admittance_matrix}")

    def _validate_params(self, r: float, x: float) -> None:
        """Validate that impedance parameters are non-negative and not both zero."""
        if r < 0 or x < 0:
            raise ValueError("r and x must be non-negative.")
        if r == 0 and x == 0:
            raise ValueError("r and x cannot both be zero.")

    def calc_g(self) -> float:
        """Return conductance g based on current r and x."""
        z_squared = self._r**2 + self._x**2
        return self._r / z_squared
    
    def calc_b(self) -> float:
        """Return susceptance b based on current r and x."""
        z_squared = self._r**2 + self._x**2
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
        self._validate_params(value, self._x)
        self._r = value
        self._g = self.calc_g()
        self._b = self.calc_b()
        self._admittance_matrix = self._build_admittance_matrix()
    
    @property
    def x(self) -> float:
        return self._x
    
    @x.setter
    def x(self, value: float):
        """Set reactance and update derived admittance and matrix."""
        self._validate_params(self._r, value)
        self._x = value
        self._g = self.calc_g()
        self._b = self.calc_b()
        self._admittance_matrix = self._build_admittance_matrix()
    
    @property
    def g(self) -> float:
        return self._g
    
    @property
    def b(self) -> float:
        return self._b


def test_transformer():
    """Test transformer properties including admittance matrix."""
    
    # Basic instantiation and impedance/admittance calculations
    t = Transformer(name="T1", bus1_name="BusA", bus2_name="BusB", r=0.02, x=0.04)
    z_sq = 0.02**2 + 0.04**2
    assert t.r == 0.02
    assert t.x == 0.04
    assert abs(t.g - (0.02 / z_sq)) < 1e-12
    assert abs(t.b - (-0.04 / z_sq)) < 1e-12

    # Test admittance matrix structure
    matrix = t.admittance_matrix
    assert isinstance(matrix, pd.DataFrame)
    assert matrix.shape == (2, 2)
    assert list(matrix.index) == ["BusA", "BusB"]
    assert list(matrix.columns) == ["BusA", "BusB"]
    
    # Test admittance matrix values
    y_expected = t.g + 1j * t.b
   
    assert abs(matrix.values[0,0] - y_expected) < 1e-12
    assert abs(matrix.values[1,1] - y_expected) < 1e-12
    assert abs(matrix.values[0,1] + y_expected) < 1e-12
    assert abs(matrix.values[1,0] + y_expected) < 1e-12

    # Test parameter updates trigger matrix rebuild
    t.r = 0.03
    t.x = 0.06
    z_sq2 = 0.03**2 + 0.06**2
    assert abs(t.g - (0.03 / z_sq2)) < 1e-12
    assert abs(t.b - (-0.06 / z_sq2)) < 1e-12
    
    # Verify matrix is updated
    y_expected2 = t.g + 1j * t.b
    assert abs(t.admittance_matrix.values[0,0] - y_expected2) < 1e-12

    # Test validation
    try:
        Transformer(name="T2", bus1_name="BusA", bus2_name="BusB", r=0.0, x=0.0)
        assert False, "Expected ValueError for r=0 and x=0"
    except ValueError:
        pass

    try:
        t.r = -0.01
        assert False, "Expected ValueError for negative r"
    except ValueError:
        pass

    try:
        t.x = -0.01
        assert False, "Expected ValueError for negative x"
    except ValueError:
        pass

    print("✓ All transformer tests passed")


if __name__ == "__main__":
    test_transformer()

