class Transmission_Line:
    """
    define transmisison line  class

    Attributes:
        name: name of the generator
        bus_1_name: bus 1 name
        bus_2_name: bus 2 name
        r: transmission line resistance in ohms
        x: transmission line reactance in ohms
        g: transmission line conductance in siemens
    """
    def __init__(self, name, bus1_name, bus2_name, r, x):
        self.name:str = name
        self.bus1_name = bus1_name
        self.bus2_name = bus2_name
        self.r = r
        self.x = x
        self.g = self.calg_g()

    def calg_g(self):
        """
        compute the conductance of transmission line from `r` and `x`
        """
        return self.r/(self.r**2 + self.x**2)
