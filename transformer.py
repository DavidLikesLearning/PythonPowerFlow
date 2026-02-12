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
        g = r / (r^2 + x^2)
        b = -x / (r^2 + x^2)

    Example
    -------
    t = Transformer(name="T1", bus1="BusA", bus2="BusB", r=0.02, x=0.04)
    print(t.g, t.b)
    """
    def __init__(self, name: str, bus1: str, bus2: str, r: float, x: float):
        self.name = name
        self.bus1 = bus1
        self.bus2 = bus2
        self._validate_params(r, x)
        self._r = r
        self._x = x
        self._g = self.calc_g()
        self._b = self.calc_b()
    
    def __repr__(self) -> str:
        return f"Transformer(name={self.name!r}, bus1={self.bus1!r}, bus2={self.bus2!r}, r={self._r}, x={self._x})"
    
    def __str__(self) -> str:
        return (f"Transformer '{self.name}': {self.bus1} <-> {self.bus2}\n"
                f"  Impedance: R={self._r:.6f}, X={self._x:.6f}\n"
                f"  Admittance: G={self._g:.6f}, B={self._b:.6f}")

    def _validate_params(self, r: float, x: float) -> None:
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

    @property
    def r(self) -> float:
        return self._r
    
    @r.setter
    def r(self, value: float):
        self._validate_params(value, self._x)
        self._r = value
        self._g = self.calc_g()
        self._b = self.calc_b()
    
    @property
    def x(self) -> float:
        return self._x
    
    @x.setter
    def x(self, value: float):
        self._validate_params(self._r, value)
        self._x = value
        self._g = self.calc_g()
        self._b = self.calc_b()
    
    @property
    def g(self) -> float:
        return self._g
    
    @property
    def b(self) -> float:
        return self._b


def test_transformer():
    ## add tests for the __str__ and __repr__ methods
    
    t = Transformer(name="T1", bus1="BusA", bus2="BusB", r=0.02, x=0.04)
    z_sq = 0.02**2 + 0.04**2
    assert t.r == 0.02
    assert t.x == 0.04
    assert abs(t.g - (0.02 / z_sq)) < 1e-12
    assert abs(t.b - (-0.04 / z_sq)) < 1e-12

    t.r = 0.03
    t.x = 0.06
    z_sq2 = 0.03**2 + 0.06**2
    assert abs(t.g - (0.03 / z_sq2)) < 1e-12
    assert abs(t.b - (-0.06 / z_sq2)) < 1e-12

    try:
        Transformer(name="T2", bus1="BusA", bus2="BusB", r=0.0, x=0.0)
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


if __name__ == "__main__":
    test_transformer()
    print("Transformer tests passed.")

