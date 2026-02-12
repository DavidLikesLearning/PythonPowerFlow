"""
Bus class for power systems circuit simulation.

This module defines the Bus class which represents a bus (node) in an electrical circuit.
A bus has a name and a voltage value that can be set and retrieved.
"""
from typing import Optional

class Bus:
    """
    Represents a bus (node) in an electrical circuit.
    
    Each bus is automatically assigned a unique index for identification.
    The voltage is calculated and set by external solver classes.
    
    Attributes:
        name (str): The name identifier of the bus
        index (int): Unique index automatically assigned to each bus
        v (float): The voltage at the bus in volts (set by solver, initially 0.0)
    """
    
    _bus_index = 1  # Class variable to track next available index
    
    def __init__(self, name: str, nominal_kv: Optional[float] = None):
        """
        Initialize a Bus instance.
        
        Args:
            name (str): The name identifier of the bus
            nominal_kv (float): The nominal voltage of the bus in kilovolts
        """
        self.name = name
        self.bus_index = Bus._bus_index
        Bus._bus_index += 1
        self.nominal_kv = nominal_kv  # Initial voltage, to be set by solver # remove attribute direct access
    
    @property
    def voltage(self) -> Optional[float]:
        """Get the voltage at the bus in volts (read-only for users)."""
        return self.nominal_kv
    
    def _set_voltage(self, value: float) -> None:
        """
        Set the voltage at the bus (intended for use by solver classes).
        
        Args:
            value (float): The voltage value to set at the bus
            
        Note:
            This method is intended for use by solver classes and should not be
            called directly by users.
        """
        self.nominal_kv = value
    
    @classmethod
    def reset_index_counter(cls) -> None:
        """
        Reset the bus index counter to 1 (useful for testing).
        """
        cls._bus_index = 1
    
    def __str__(self) -> str:
        """String representation of the Bus."""
        return f"Bus(name='{self.name}', index={self.bus_index}, v={self.nominal_kv}V)"
    
    def __repr__(self) -> str:
        """Official string representation of the Bus."""
        return f"Bus('{self.name}', index={self.bus_index})"


def test_bus():
    """Test function for the Bus class."""
    print("Testing Bus class...")
    
    # Reset index counter for consistent testing
    Bus.reset_index_counter()
    
    # Test 1: Create a bus with automatic indexing
    bus1 = Bus("Bus1")
    print(f"Test 1 - Created bus: {bus1}")
    assert bus1.name == "Bus1"
    assert bus1.bus_index == 1
    assert bus1.voltage == None
    
    # Test 2: Create another bus with automatic indexing
    bus2 = Bus("Bus2")
    print(f"Test 2 - Created second bus: {bus2}")
    assert bus2.name == "Bus2"
    assert bus2.bus_index == 2
    assert bus2.voltage == None
    
    # Test 3: Set voltage using internal method (for solver)
    bus1._set_voltage(240.0)
    print(f"Test 3 - After setting voltage: {bus1}")
    assert bus1.voltage == 240.0

    # Test 6: Test property access and unique indexing
    bus4 = Bus("Property_Test")
    bus4._set_voltage(480.0)
    print(f"Test 6 - Property access: name={bus4.name}, index={bus4.bus_index}, voltage={bus4.voltage}V")
    assert bus4.name == "Property_Test"  # Instead of bus4.bus_name
    assert bus4.bus_index == 3
    assert bus4.voltage == 480.0
    
    # Test 7: Verify voltage property is read-only for users
    print("Test 7 - Voltage property is read-only")
    try:
        bus4.voltage = 500.0  # type: ignore # This should not work
        print("  ✗ Voltage property should be read-only!")
        assert False, "Voltage property should be read-only"
    except AttributeError:
        print("  ✓ Voltage property is correctly read-only")
    
    print("All Bus tests passed!")


def main():
    """Main function to run when script is executed directly."""
    print("=" * 50)
    print("Bus Class Circuit Simulator Module")
    print("=" * 50)
    
    # Reset index counter for clean demo
    Bus.reset_index_counter()
    
    # Run tests
    test_bus()
    
    # Demo usage
    print("\nDemo Usage:")
    print("-" * 20)
    
    # Create some example buses
    buses = [
        Bus("Generator_Bus"),
        Bus("Load_Bus_1"),
        Bus("Load_Bus_2")
    ]
    
    print("Initial bus states:")
    for bus in buses:
        print(f"  {bus}")
    
    # Simulate solver setting voltages
    print("\nSimulating solver setting voltages:")
    buses[0]._set_voltage(13800.0)  # Generator bus
    buses[1]._set_voltage(4160.0)   # Load bus 1
    buses[2]._set_voltage(277.0)    # Load bus 2
    
    print("After solver sets voltages:")
    for bus in buses:
        print(f"  {bus}")
        
    print("\nBus indexing demonstration:")
    print(f"Next bus will have index: {Bus._bus_index}")
    new_bus = Bus("New_Bus")
    print(f"Created: {new_bus}")


if __name__ == "__main__":
    main()