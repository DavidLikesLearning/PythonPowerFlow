from bus import Bus, BusType

def test_bus():
    """Test function for the Bus class."""
    print("Testing Bus class...")
    
    # Reset bus index counter before testing
    Bus.reset_index_counter()
    
    # Test valid initialization with all attributes
    bus1 = Bus(name="Bus1", nominal_kv=110.0, bus_type=BusType.Slack)
    assert bus1.name == "Bus1", "Bus name should be 'Bus1'"
    assert bus1.nominal_kv == 110.0, "Nominal voltage should be 110.0 kV"
    assert bus1.v == 110.0, "Initial voltage should be equal to nominal voltage"
    assert bus1.bus_type == BusType.Slack, "Bus type should be Slack"
    assert bus1.vpu == 1.0, "Initial vpu should be 1.0"
    assert bus1.delta == 0.0, "Initial delta should be 0.0"
    assert bus1.bus_index == 1, "Bus index should be 1"
    
    # Test string representation
    assert str(bus1) == "Bus(name='Bus1', index=1, v=110.0V)", "String representation is incorrect"
    
    # Test vpu setter and getter
    bus1.vpu = 1.05
    assert bus1.vpu == 1.05, "vpu should be updated to 1.05"
    
    # Test delta setter and getter
    bus1.delta = 5.0
    assert bus1.delta == 5.0, "delta should be updated to 5.0"
    
    # Test bus_type setter and getter
    bus1.bus_type = BusType.PQ
    assert bus1.bus_type == BusType.PQ, "bus_type should be updated to PQ"
    
    # Test automatic indexing
    bus2 = Bus(name="Bus2", nominal_kv=120.0, bus_type=BusType.PV)
    assert bus2.bus_index == 2, "Bus index should be 2 for second bus"
    assert bus2.bus_type == BusType.PV, "Bus type should be PV"
    
    # Test error handling for invalid bus_type
    try:
        Bus(name="Bus3", nominal_kv=130.0, bus_type="slack") # type: ignore
        assert False, "Should raise ValueError for invalid bus_type"
    except ValueError:
        pass
    
    # Test error handling for negative nominal_kv
    try:
        Bus(name="Bus4", nominal_kv=-10.0, bus_type=BusType.PQ)
        assert False, "Should raise ValueError for negative nominal_kv"
    except ValueError:
        pass
     
    # Test error handling for empty name
    try:
        Bus(name="", nominal_kv=110.0, bus_type=BusType.PQ)
        assert False, "Should raise ValueError for empty name"
    except ValueError:
        pass
    
    # Test error handling for negative vpu
    try:
        Bus(name="Bus5", nominal_kv=110.0, bus_type=BusType.PQ)
        assert False, "Should raise ValueError for negative vpu"
    except ValueError:
        pass
    
    # Test error handling for negative delta
    try:
        Bus(name="Bus6", nominal_kv=110.0, bus_type=BusType.PQ, delta=-5.0)
        assert False, "Should raise ValueError for negative delta"
    except ValueError:
        pass
    
    print("All tests passed for Bus class!")


def test_bus_init():
    """Test function for the Bus class."""
    print("Testing Bus class...")

    # Reset index counter for consistent testing
    Bus.reset_index_counter()

    # Test 1: Create a bus with automatic indexing
    bus1 = Bus("Bus1", 120.0, bus_type=BusType.Slack)
    print(f"Test 1 - Created bus: {bus1}")
    assert bus1.name == "Bus1"
    assert bus1.bus_index == 1
    assert bus1.nominal_kv == 120.0


def test_bus_attributes():
    Bus.reset_index_counter()

    # Test 2: Create another bus with automatic indexing
    bus1 = Bus("Bus1", 120.0, bus_type=BusType.Slack)
    bus2 = Bus("Bus2", 240.0, bus_type=BusType.PQ)
    print(f"Test 2 - Created second bus: {bus2}")
    assert bus2.name == "Bus2"
    assert bus2.bus_index == 2
    assert bus2.nominal_kv == 240.0
    assert bus2.bus_type == BusType.PQ


def test_bus_set_vals():
    Bus.reset_index_counter()
    # Test 2: Create another bus with automatic indexing
    bus1 = Bus("Bus1", 120.0, bus_type=BusType.Slack)
    assert bus1.v == 120.0
    # Test 3: Set voltage using internal method (for solver)
    bus1.vpu = 1.01
    print(f"Test 3 - After setting voltage: {bus1}")
    assert bus1.vpu == 1.01


def test_bus_indexing():
    Bus.reset_index_counter()
    # Test 6: Test property access and unique indexing
    bus4 = Bus("Property_Test", 100.0, bus_type=BusType.PQ)
    bus5 = Bus("another", 100.0, bus_type=BusType.PQ)
    bus6 = Bus("another_one", 100.0, bus_type=BusType.PQ)
    assert bus4.bus_index == 1
    assert bus5.bus_index == 2
    assert bus6.bus_index == 3
