from circuit import Circuit

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
    circuit.add_bus("Bus 2", 20.0)
    circuit.add_generator("Gen 1", "bus 1",
                          20, 200)
    circuit.add_transmission_line("Transmission line",
                                  "Bus 1",bus2_name="Bus 2",
                                  r = 1 ,x=1)
    circuit.add_transformer('optimus', bus1_name="Bus 1",bus2_name="Bus 2",
                            r = 2, x=2)
    circuit.add_load('Load', bus1_name="Bus 1",mw = 150, mvar=100)

    try:
        circuit.add_bus("Bus 1", 30.0)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "already exists" in str(e)

    try:
        circuit.add_generator("Gen 1", "bus 1",
                              20, 200)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "already exists" in str(e)

    try:
        circuit.add_transmission_line("Transmission line",
                                  "Bus 1",bus2_name="Bus 2",
                                  r = 1 ,x=1)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "already exists" in str(e)

    try:
        circuit.add_transformer('optimus', bus1_name="Bus 1",bus2_name="Bus 2",
                            r = 2, x=2)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "already exists" in str(e)

    try:
        circuit.add_load('Load', bus1_name="Bus 1",mw = 150, mvar=100)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "already exists" in str(e)
    print("✓ Duplicate component rejection test passed")


        
def test_add_generator():
    """
    tests generator addition and name exclusiveness """
    circuit = Circuit("Test Circuit")
    circuit.add_generator("Bus 1", bus_name="Bus 1",
                          mw_setpoint= 100, voltage_setpoint=20.0)
    assert circuit.generators["Bus 1"].bus_name == "Bus 1"
    assert circuit.generators["Bus 1"].mw_setpoint == 100
    assert circuit.generators["Bus 1"].v_setpoint == 20.0

def test_add_connection_without_buses():
    """Try to add transmission line and transformer when buses aren't in
    circuit yet — both should raise ValueError."""
    circuit = Circuit("Test Circuit")

    try:
        circuit.add_transmission_line("Line 1", "Bus 1", "Bus 2", r=0.01, x=0.1)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "not both in circuit" in str(e)

    try:
        circuit.add_transformer("T1", bus1_name="Bus 1", bus2_name="Bus 2", r=0.01, x=0.05)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "not both in circuit" in str(e)

    print("✓ Add connection without buses test passed")

def test_add_transmission_line():
    """Make a circuit, add two buses, then add a transmission line and
    verify all its properties are stored correctly."""
    circuit = Circuit("Test Circuit")
    circuit.add_bus("Bus 1", 138.0)
    circuit.add_bus("Bus 2", 138.0)
    circuit.add_transmission_line("Line 1",
        "Bus 1", "Bus 2", r=0.02, x=0.2)
    assert "Line 1" in circuit.transmission_lines
    line = circuit.transmission_lines["Line 1"]
    assert line.name == "Line 1"
    assert line.bus1_name == "Bus 1"
    assert line.bus2_name == "Bus 2"
    assert line.r == 0.02
    assert line.x == 0.2
    print("✓ Add transmission line test passed")

def test_add_transformer():
    """Make a circuit, add two buses, then add a transformer and verify
    its properties are stored correctly."""
    circuit = Circuit("Test Circuit")
    circuit.add_bus("Bus 1", 20.0)
    circuit.add_bus("Bus 2", 138.0)
    circuit.add_transformer("T1",
        bus1_name="Bus 1", bus2_name="Bus 2", r=0.005, x=0.05)
    assert "T1" in circuit.transformers
    transformer = circuit.transformers["T1"]
    assert transformer.name == "T1"
    assert transformer.bus1_name == "Bus 1"
    assert transformer.bus2_name == "Bus 2"
    assert transformer.r == 0.005
    assert transformer.x == 0.05
    print("✓ Add transformer test passed")

def test_add_load():
    """Make a circuit, add a load, and verify its properties are stored
    correctly."""
    circuit = Circuit("Test Circuit")
    circuit.add_bus("Bus 1", 20.0)
    circuit.add_load("Load 1",
        bus1_name="Bus 1", mw=150.0, mvar=50.0)
    assert "Load 1" in circuit.loads
    load = circuit.loads["Load 1"]
    assert load.name == "Load 1"
    assert load.bus1_name == "Bus 1"
    assert load.mw == 150.0
    assert load.mvar == 50.0
    print("✓ Add load test passed")

def test_str_repr():
    """Test string representations."""
    circuit = Circuit("My Circuit")
    print(f"✓ __repr__: {repr(circuit)}")
    print(f"✓ __str__: {str(circuit)}")

def test_build_5bus_example():
    """Build the 5-bus example 6.9 from the Power System Analysis book and
    print the Y-bus matrix."""
    circuit = Circuit("5-Bus Example 6.9")
    circuit.add_bus("One", 15.0)
    circuit.add_bus("Two", 345.0)
    circuit.add_bus("Three", 15.0)
    circuit.add_bus("Four", 345.0)
    circuit.add_bus("Five", 345.0)

    circuit.add_transmission_line("L42", "Four", "Two", r=0.009, x=0.1,  b=1.72)
    circuit.add_transmission_line("L13", "Five", "Two", r=0.0045, x=0.05,b=0.88)
    circuit.add_transmission_line("L23", "Five", "Four", r=0.00225, x=0.025, b=0.44)

    circuit.add_transformer("T15", "One","Five", r=0.0015, x=0.02)
    circuit.add_transformer("T34", "Three", "Four", r=0.00075, x=0.01)
    print(circuit._y_bus)
    print("✓ 5-bus example 6.9 test passed")
        

def test_y_bus():
    """Make a circuit, add two buses, then add a transformer and verify
    its properties are stored correctly."""
    circuit = Circuit("Test Circuit")
    circuit.add_bus("Bus 1", 20.0)
    circuit.add_bus("Bus 2", 138.0)
    circuit.add_bus("Bus 3", 138.0)
    circuit.add_transformer("T1",
        bus1_name="Bus 1", bus2_name="Bus 2", r=0.005, x=0.05)
    circuit.add_transformer("T2",
                            bus1_name="Bus 3", bus2_name="Bus 2", r=0.005, x=0.05)
    print(circuit._y_bus)
    print("✓ Add transformer test passed")
    

if __name__ == '__main__':
    pass