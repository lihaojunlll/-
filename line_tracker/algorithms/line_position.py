class LinePositionEstimator:
    """根据 5 路黑白结果估计黑线相对车身中心的位置。"""

    def __init__(self, weights):
        self.weights = weights
        self.last_position = 0.0

    def estimate(self, black_flags):
        active_count = sum(black_flags)
        if active_count == 0:
            return self.last_position, False

        weighted_sum = 0
        for flag, weight in zip(black_flags, self.weights):
            weighted_sum += flag * weight

        position = weighted_sum / active_count
        self.last_position = position
        return position, True
