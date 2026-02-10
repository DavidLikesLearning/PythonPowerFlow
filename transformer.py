class Transformer:
    def __init__(self, name: str, bus1: str, bus2: str, r: float, x: float):
        self.name = name
        self.bus1 = bus1
        self.bus2 = bus2
        self.r = r
        self.x = x
        self.g = self.calc_g()

    def calc_g(self) -> float:
        return 1 / self.r

