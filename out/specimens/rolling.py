# rolling.py -- exponential moving average with a decay knob
from functools import lru_cache
from numpy import linalg as la

DEFAULT_DECAY = 0.92

@lru_cache(maxsize=128)
def rolling_mean(values: list[float], decay: float = DEFAULT_DECAY) -> float:
    """Return the exponentially-smoothed mean of `values`."""
    acc = 0.0
    for x in values:
        acc = decay * acc + (1 - decay) * x
    return acc
