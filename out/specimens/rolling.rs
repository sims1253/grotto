// rolling.rs -- exponential moving average
use std::collections::VecDeque;

const DEFAULT_DECAY: f64 = 0.92;

#[inline]
/// Exponentially-smoothed mean of a slice.
pub fn rolling_mean(values: &[f64], decay: f64) -> f64 {
    let mut acc: f64 = 0.0;
    for &x in values {
        acc = decay * acc + (1.0 - decay) * x;
    }
    acc
}
