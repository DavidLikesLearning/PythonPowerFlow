from circuit import Circuit
from bus import BusType

def case6_9_5bus_jacobian():
    """Build the 5-bus example 6.9 from the Power System Analysis book,
    compare the Y-bus matrix to the CSV, and assert numerical equality."""
    circuit = Circuit("5-Bus Example 6.9")
    circuit.add_bus("One", 15.0,bus_type=BusType.PQ)
    circuit.add_bus("Two", 345.0,bus_type=BusType.PQ)
    circuit.add_bus("Three", 15.0,bus_type=BusType.PV)
    circuit.add_bus("Four", 345.0,bus_type=BusType.PQ)
    circuit.add_bus("Five", 345.0,bus_type=BusType.PQ)

    circuit.add_transmission_line("L42", "Four", "Two", r=0.009, x=0.1,  b=1.72)
    circuit.add_transmission_line("L52", "Five", "Two", r=0.0045, x=0.05, b=0.88)
    circuit.add_transmission_line("L54", "Five", "Four", r=0.00225, x=0.025, b=0.44)

    circuit.add_transformer("T15", "One", "Five", r=0.0015, x=0.02)
    circuit.add_transformer("T34", "Three", "Four", r=0.00075, x=0.01)
    circuit.calc_ybus()
    print('index:\n',circuit._bus_index)

    circuit.add_load('TwoL', 'Two', 800, 280)
    circuit.add_load('ThreeL', 'Three', 80, 40)
    circuit.add_generator('ThreeG', 'Three', 520, 0)

    J = circuit.calc_jacobian()
    print("J.shape:\n",J.shape)
    print("J:\n",J)

def main():
    case6_9_5bus_jacobian()

if __name__ == "__main__":
    main()
