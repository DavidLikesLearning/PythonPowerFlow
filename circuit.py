# circuit.py
from __future__ import annotations
import warnings
class Circuit:
    """
    Circuit class for power system network modeling.

    This class serves as a container to assemble a complete power system network
    by storing and managing all equipment objects (buses, transformers,
    transmission lines, generators, and loads).

    Attributes:
        name: Identifier for the circuit.
        buses: Dictionary storing Bus objects with bus names as keys.
        transformers: Dictionary storing Transformer objects with transformer names as keys.
        transmission_lines: Dictionary storing TransmissionLine objects with line names as keys.
        generators: Dictionary storing Generator objects with generator names as keys.
        loads: Dictionary storing Load objects with load names as keys.
    """

    def __init__(self, name: str):
        """
        Initialize a Circuit instance.

        Args:
            name: The circuit name (must be a non-empty string).

        Raises:
            ValueError: If name is not a non-empty string.
        """
        if not isinstance(name, str) or not name.strip():
            raise ValueError("name must be a non-empty string")

        if name != name.strip():
            raise warnings.warn("Circuit name is stripped in processing.")

        self._name = name.strip()
        self._buses = {}
        self._transformers = {}
        self._transmission_lines = {}
        self._generators = {}
        self._loads = {}

    def __repr__(self) -> str:
        """Return unambiguous representation of Circuit."""
        return f"Circuit(name={self._name!r})"

    def __str__(self) -> str:
        """Return human-readable summary of Circuit."""
        return (
            f"Circuit '{self._name}': "
            f"{len(self._buses)} buses, "
            f"{len(self._transformers)} transformers, "
            f"{len(self._transmission_lines)} transmission lines, "
            f"{len(self._generators)} generators, "
            f"{len(self._loads)} loads"
        )

    # --- name property ---
    @property
    def name(self) -> str:
        """Get circuit name."""
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        """Set circuit name."""
        if not isinstance(value, str) or not value.strip():
            raise ValueError("name must be a non-empty string")
        self._name = value.strip()

    # --- Equipment dictionary properties (read-only) ---
    @property
    def buses(self) -> dict:
        """Get buses dictionary."""
        return self._buses

    @property
    def transformers(self) -> dict:
        """Get transformers dictionary."""
        return self._transformers

    @property
    def transmission_lines(self) -> dict:
        """Get transmission lines dictionary."""
        return self._transmission_lines

    @property
    def generators(self) -> dict:
        """Get generators dictionary."""
        return self._generators

    @property
    def loads(self) -> dict:
        """Get loads dictionary."""
        return self._loads

    # --- Add methods ---
    def add_bus(self, name: str, nominal_kv: float) -> None:
        """
        Add a bus to the circuit.

        Args:
            name: Bus name (must be unique within buses).
            nominal_kv: Nominal voltage in kV.

        Raises:
            ValueError: If a bus with the same name already exists.
        """
        if name in self._buses:
            raise ValueError(f"Bus '{name}' already exists in circuit")

        # Import here to avoid circular dependencies
        from bus import Bus
        self._buses[name] = Bus(name, nominal_kv)

    def add_transformer(self, name: str, bus1_name: str, bus2_name: str,
                        r: float, x: float) -> None:
        """
        Add a transformer to the circuit.

        Args:
            name: Transformer name (must be unique within transformers).
            bus1_name: Primary bus name.
            bus2_name: Secondary bus name.
            r: Series resistance.
            x: Series reactance.

        Raises:
            ValueError: If a transformer with the same name already exists.
        """
        if name in self._transformers:
            raise ValueError(f"Transformer '{name}' already exists in circuit")

        from transformer import Transformer
        self._transformers[name] = Transformer(name, bus1_name, bus2_name, r, x)

    def add_transmission_line(self, name: str, bus1_name: str, bus2_name: str,
                              r: float, x: float, g: float, b: float) -> None:
        """
        Add a transmission line to the circuit.

        Args:
            name: Line name (must be unique within transmission lines).
            bus1_name: From-bus name.
            bus2_name: To-bus name.
            r: Series resistance.
            x: Series reactance.
            g: Shunt conductance.
            b: Shunt susceptance.

        Raises:
            ValueError: If a transmission line with the same name already exists.
        """
        if name in self._transmission_lines:
            raise ValueError(f"Transmission line '{name}' already exists in circuit")

        from transmission_line import TransmissionLine
        self._transmission_lines[name] = TransmissionLine(name, bus1_name, bus2_name, r, x)

    def add_generator(self, name: str, bus1_name: str,
                      voltage_setpoint: float, mw_setpoint: float) -> None:
        """
        Add a generator to the circuit.

        Args:
            name: Generator name (must be unique within generators).
            bus1_name: Bus name where generator is connected.
            voltage_setpoint: Voltage setpoint in per unit.
            mw_setpoint: Active power setpoint in MW.

        Raises:
            ValueError: If a generator with the same name already exists.
        """
        if name in self._generators:
            raise ValueError(f"Generator '{name}' already exists in circuit")

        from generator import Generator
        self._generators[name] = Generator(name, bus1_name, voltage_setpoint, mw_setpoint)

    def add_load(self, name: str, bus1_name: str, mw: float, mvar: float) -> None:
        """
        Add a load to the circuit.

        Args:
            name: Load name (must be unique within loads).
            bus1_name: Bus name where load is connected.
            mw: Active power in MW.
            mvar: Reactive power in MVAr.

        Raises:
            ValueError: If a load with the same name already exists.
        """
        if name in self._loads:
            raise ValueError(f"Load '{name}' already exists in circuit")

        from load import Load
        self._loads[name] = Load(name, bus1_name, mw, mvar)


# --- Testing functions ---
def test_circuit_creation():
    """Test basic circuit creation."""
    circuit = Circuit("Test Circuit")
    assert circuit.name == "Test Circuit"
    assert isinstance(circuit.name, str)
    print("✓ Circuit creation test passed")


def test_empty_name_rejected():
    """Test that empty names are rejected."""
    try:
        Circuit("")
        assert False, "Should have raised ValueError"
    except ValueError:
        print("✓ Empty name rejection test passed")


def test_attribute_initialization():
    """Test that all dictionaries are initialized correctly."""
    circuit = Circuit("Test Circuit")
    assert circuit.buses == {}
    assert isinstance(circuit.buses, dict)
    assert circuit.transformers == {}
    assert circuit.transmission_lines == {}
    assert circuit.generators == {}
    assert circuit.loads == {}
    print("✓ Attribute initialization test passed")


def test_duplicate_component_rejected():
    """Test that duplicate component names are rejected."""
    circuit = Circuit("Test Circuit")
    circuit.add_bus("Bus 1", 20.0)

    try:
        circuit.add_bus("Bus 1", 30.0)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "already exists" in str(e)
        print("✓ Duplicate component rejection test passed")


def test_str_repr():
    """Test string representations."""
    circuit = Circuit("My Circuit")
    print(f"✓ __repr__: {repr(circuit)}")
    print(f"✓ __str__: {str(circuit)}")


if __name__ == "__main__":
    print("Running Circuit class tests...\n")
    test_circuit_creation()
    test_empty_name_rejected()
    test_attribute_initialization()
    test_duplicate_component_rejected()
    test_str_repr()
    print("\n✅ All Circuit class tests passed!")
