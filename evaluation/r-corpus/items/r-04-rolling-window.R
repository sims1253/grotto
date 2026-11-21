# Streaming statistics over a fixed-width window, computed with explicit
# loops so the control flow (for / while / next / break) is the point.

rolling_max_window <- function(x, width = 3) {
  n <- length(x)
  if (width < 1 || width > n) {
    stop("width must be in [1, length(x)]")
  }

  out <- numeric(0)
  i <- 1
  while (i <= n - width + 1) {
    window_max <- -Inf

    for (j in i:(i + width - 1)) {
      value <- x[j]
      if (is.na(value)) {
        next  # skip gaps in the sensor feed without shrinking the window
      }
      if (value > window_max) {
        window_max <- value
      }
    }

    # a window with no observations at all stays NA, not -Inf
    if (is.infinite(window_max)) {
      out <- c(out, NA_real_)
    } else {
      out <- c(out, window_max)
    }
    i <- i + 1
  }
  out
}

# Walk a vector until the first value that exceeds a cap, then stop early.
# Returns the 1-based index, or 0 when the cap is never exceeded.

first_above <- function(x, cap) {
  for (i in seq_along(x)) {
    if (is.na(x[i])) {
      break  # a gap means the stream ended for our purposes
    }
    if (x[i] > cap) {
      return(i)
    }
  }
  0L
}

# Example (not run):
#   rolling_max_window(c(1, 4, NA, 2, 7, 3), width = 3)
#   #> [1] 4 4 7 7
#   first_above(c(0.1, 0.4, 1.9, 0.2), cap = 1.5)
#   #> [1] 3
