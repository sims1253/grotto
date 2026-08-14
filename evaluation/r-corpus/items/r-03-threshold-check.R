# A small S3 class for threshold checks on a numeric vector, with a
# print method and a summary method.  Deliberately base-R only.

threshold_check <- function(values, lower, upper, label = "unnamed") {
  if (lower > upper) {
    tmp <- lower
    lower <- upper
    upper <- tmp
    warning("lower > upper; bounds were swapped")
  }
  structure(
    list(
      label = label,
      values = values[!is.na(values)],
      lower = lower,
      upper = upper
    ),
    class = "threshold_check"
  )
}

check_counts <- function(x) {
  below <- sum(x$values < x$lower)
  above <- sum(x$values > x$upper)
  inside <- length(x$values) - below - above
  list(below = below, inside = inside, above = above)
}

print.threshold_check <- function(x, ...) {
  counts <- check_counts(x)
  cat(sprintf("<threshold_check> %s: %d value(s)\n", x$label, length(x$values)))
  cat(sprintf(
    "  in [%g, %g]: %d inside, %d below, %d above\n",
    x$lower, x$upper, counts$inside, counts$below, counts$above
  ))
  invisible(x)
}

summary.threshold_check <- function(object, ...) {
  counts <- check_counts(object)
  data.frame(
    label = object$label,
    n = length(object$values),
    min = min(object$values),
    median = median(object$values),
    max = max(object$values),
    frac_inside = counts$inside / max(length(object$values), 1L),
    row.names = NULL
  )
}

# Example (not run):
#   tc <- threshold_check(c(0.5, 1.2, 9.9, 10.4, NA), lower = 1, upper = 10,
#                         label = "gain")
#   print(tc)
#   #> <threshold_check> gain: 4 value(s)
#   #>   in [1, 10]: 2 inside, 1 below, 1 above
#   summary(tc)
