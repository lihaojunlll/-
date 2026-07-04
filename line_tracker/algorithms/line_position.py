class LinePositionEstimator:
    def __init__(self, weights):
        self.weights = weights
        self.last = 0.0

    def estimate(self, flags):
        n = sum(flags)
        if n == 0:
            return self.last, False
        pos = sum(f * w for f, w in zip(flags, self.weights)) / n
        self.last = pos
        return pos, True
