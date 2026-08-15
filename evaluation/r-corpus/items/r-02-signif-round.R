# Round a numeric vector to a fixed number of significant digits.
#
# round(x, digits) rounds decimal places, which is the wrong tool when
# values span orders of magnitude.  This helper keeps the magnitude and
# drops precision, and is careful about zeros (log10 of 0 is -Inf).

signif_round <- function(x, digits = 3) {
  if (!is.numeric(x)) {
    stop("x must be numeric, got ", class(x)[1])
  }
  if (digits < 1 || digits > 15 || digits != floor(digits)) {
    stop("digits must be an integer in [1, 15]")
  }

  out <- rep(NA_real_, length(x))
  nonzero <- !is.na(x) & x != 0

  # magnitude of each value, floored: 1234 -> 3, 0.05 -> -2
  magnitude <- floor(log10(abs(x[nonzero])))
  out[nonzero] <- round(x[nonzero], digits - 1 - magnitude)

  # zeros and NAs pass through untouched by the branch above
  out[x == 0 & !is.na(x)] <- 0
  out
}

# Recompute relative differences between two runs of an experiment,
# reporting values in percent with bounded significant digits.

relative_diff <- function(new, old, digits = 3) {
  if (length(new) != length(old)) {
    stop("new and old must have equal length")
  }
  denom <- ifelse(old == 0, NA_real_, old)  # avoid dividing by zero
  pct <- 100 * (new - old) / denom
  signif_round(pct, digits = digits)
}

# Example (not run):
#   signif_round(c(123456, 0.000123456, 0, NA), digits = 2)
#   #> [1] 120000.00     0.00     0.00        NA
#   relative_diff(new = c(105, 98), old = c(100, 100))
#   #> [1]  5 -2
