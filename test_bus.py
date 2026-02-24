from bus import Bus

def test_bus():
    """Test function for the Bus class."""
    print("Testing Bus class...")
    
    # Reset bus index counter before testing
    Bus.reset_index_counter()
    
    # Create a bus instance
    bus1 = Bus(name="Bus1", nominal_kv=110.0)
    
    # Test initialization
    assert bus1.name == "Bus1", "Bus name should be 'Bus1'"
    assert bus1.nominal_kv == 110.0, "Nominal voltage should be 110.0 kV"
    assert bus1.v == 110.0, "Initial voltage should be equal to nominal voltage"
    
    # Test string representation
    assert str(bus1) == "Bus(name='Bus1', index=1, v=110.0V)", "String representation is incorrect"
    
    # Test voltage setting (using the intended method)
    bus1._set_voltage(115.0)
    assert bus1.v == 115.0, "Voltage should be updated to 115.0 V"
    
    print("All tests passed for Bus class!")
