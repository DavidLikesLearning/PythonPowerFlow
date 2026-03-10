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
    
    # Test voltage setting (using the intended method)
    bus1._set_voltage(115.0)
    assert bus1.v == 115.0, "Voltage should be updated to 115.0 V"
    
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
        Bus(name="Bus5", nominal_kv=110.0, bus_type=BusType.PQ, vpu=-1.0)
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

