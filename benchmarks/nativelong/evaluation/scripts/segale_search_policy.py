"""Selection state for SEGALE's VecAlign parameter search."""


class AlignmentSearchState:
    """Apply the existing SEGALE selection and stopping rules incrementally."""

    def __init__(self, stop_jump, cost_min):
        self.stop_jump = stop_jump
        self.cost_min = cost_min
        self.best_result = None
        self.best_avg_cost = float("inf")
        self.fallback_result = None
        self.prev_zero_cost_ratio = None
        self.prev_avg_cost = None
        self.stop_reason = None
        self.stop_result = None

    def observe(self, result):
        """Return True when this result triggers the existing stopping rule."""
        dpf = result["del_percentile_frac"]
        avg_cost = result["avg_cost"]
        zero_cost_ratio = result["zero_cost_ratio"]

        if abs(dpf - 0.2) < 1e-6:
            self.fallback_result = result

        if (
            self.prev_zero_cost_ratio is not None
            and self.prev_zero_cost_ratio != 0
            and (zero_cost_ratio / self.prev_zero_cost_ratio) > 1.5
        ):
            self.stop_reason = "zero_cost_ratio_multiplier"
        elif self.prev_zero_cost_ratio is not None:
            if zero_cost_ratio - self.prev_zero_cost_ratio > self.stop_jump:
                self.stop_reason = "zero_cost_ratio_jump"
            elif avg_cost > self.prev_avg_cost:
                self.stop_reason = "average_cost_increase"
            elif avg_cost < self.cost_min:
                self.stop_reason = "average_cost_below_minimum"
            elif zero_cost_ratio > 0.7:
                self.stop_reason = "zero_cost_ratio_above_limit"

        if self.stop_reason is not None:
            self.stop_result = result
            return True

        if avg_cost < self.best_avg_cost:
            self.best_result = result
            self.best_avg_cost = avg_cost

        self.prev_zero_cost_ratio = zero_cost_ratio
        self.prev_avg_cost = avg_cost
        return False

    @property
    def selected_result(self):
        return self.best_result or self.fallback_result


def select_alignment_result(all_results, stop_jump, cost_min):
    """Select from precomputed trials with the historical SEGALE semantics."""
    state = AlignmentSearchState(stop_jump, cost_min)
    for result in all_results:
        if state.observe(result):
            break
    return state
