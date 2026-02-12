from __future__ import annotations
import math
import pytest


class Generator:
    """
    Generator model.

    Attributes:
        name: Name of the generator (non-empty string).
        bus_name: Name of the connected bus (non-empty string).
        mw_setpoint: Active power setpoint in MW (float).
        v_setpoint: Voltage magnitude setpoint in p.u. (float or None).
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
    def _as_float(value: float, field: str) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{field} must be a number")
        return float(value)

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


# ----------------------------------------------------------------------
# Tests (pytest-style, similar to transmission_line.py)
# ----------------------------------------------------------------------
def test_generator_basic_creation():
    g = Generator("G1", "BUS1", mw_setpoint=100.0, v_setpoint=1.05)
    assert g.name == "G1"
    assert g.bus_name == "BUS1"
    assert g.mw_setpoint == 100.0
    assert g.v_setpoint == 1.05


def test_generator_v_setpoint_optional():
    g = Generator("G1", "BUS1", mw_setpoint=50.0)
    assert g.v_setpoint is None
    # setting later
    g.v_setpoint = 1.0
    assert g.v_setpoint == 1.0


def test_generator_repr_contains_fields():
    g = Generator("G1", "BUS1", mw_setpoint=100.0, v_setpoint=1.0)
    rep = repr(g)
    assert "Generator(" in rep
    assert "name='G1'" in rep
    assert "bus_name='BUS1'" in rep
    assert "mw_setpoint=100.0" in rep
    assert "v_setpoint=1.0" in rep


def test_generator_str_human_readable():
    g = Generator("G1", "BUS1", mw_setpoint=100.0, v_setpoint=1.02)
    s = str(g)
    assert "Generator G1" in s
    assert "BUS1" in s
    assert "100.0 MW" in s
    assert "1.02 p.u." in s


def test_invalid_name_rejected():
    with pytest.raises(ValueError):
        Generator("", "BUS1", mw_setpoint=10.0)


def test_invalid_bus_name_rejected():
    with pytest.raises(ValueError):
        Generator("G1", "   ", mw_setpoint=10.0)


def test_invalid_mw_setpoint_type():
    with pytest.raises(TypeError):
        Generator("G1", "BUS1", mw_setpoint="100 MW")  # type: ignore[arg-type]


def test_invalid_mw_setpoint_infinite():
    with pytest.raises(ValueError):
        Generator("G1", "BUS1", mw_setpoint=float("inf"))


def test_invalid_v_setpoint_negative():
    with pytest.raises(ValueError):
        Generator("G1", "BUS1", mw_setpoint=10.0, v_setpoint=-1.0)


def test_setters_enforce_validation():
    g = Generator("G1", "BUS1", mw_setpoint=10.0, v_setpoint=1.0)

    with pytest.raises(ValueError):
        g.name = ""

    with pytest.raises(ValueError):
        g.bus_name = "  "

    with pytest.raises(TypeError):
        g.mw_setpoint = "100"  # type: ignore[assignment]

    with pytest.raises(ValueError):
        g.v_setpoint = 0.0


if __name__ == "__main__":
    # simple local test runner, mirroring transmission_line.py style
    test_generator_basic_creation()
    test_generator_v_setpoint_optional()
    test_generator_repr_contains_fields()
    test_generator_str_human_readable()
    test_invalid_name_rejected()
    test_invalid_bus_name_rejected()
    test_invalid_mw_setpoint_type()
    test_invalid_mw_setpoint_infinite()
    test_invalid_v_setpoint_negative()
    test_setters_enforce_validation()

    print("Congratulations :D\nGenerator tests passed.")
