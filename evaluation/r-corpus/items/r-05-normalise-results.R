# Normalise a list of experiment result tables with the apply family.
# Each table is a list with entries $name, $runtime_ms, and $scores.

normalise_results <- function(results, trim = 0.1) {
  if (!is.list(results) || length(results) == 0) {
    stop("results must be a non-empty list")
  }

  # extract a named field from every element, keeping names
  pick <- function(field) {
    vapply(
      results,
      function(r) {
        value <- r[[field]]
        if (is.null(value)) NA_real_ else as.numeric(value)
      },
      numeric(1)
    )
  }

  names <- vapply(results, function(r) {
    if (is.null(r$name)) "<unnamed>" else r$name
  }, character(1))

  runtimes <- pick("runtime_ms")
  scores <- pick("scores")

  # trimmed mean that tolerates all-NA input
  safe_trim_mean <- function(v) {
    v <- v[!is.na(v)]
    if (length(v) == 0) return(NA_real_)
    mean(v, trim = trim)
  }

  # per-table inner summaries, flattened to a matrix
  score_stats <- t(vapply(results, function(r) {
    s <- r$scores[!is.na(r$scores)]
    c(min = if (length(s)) min(s) else NA_real_,
      mean = safe_trim_mean(r$scores),
      max = if (length(s)) max(s) else NA_real_)
  }, numeric(3)))

  data.frame(
    name = names,
    runtime_ms = runtimes,
    score_min = score_stats[, "min"],
    score_mean = score_stats[, "mean"],
    score_max = score_stats[, "max"],
    row.names = NULL
  )
}

# Example (not run):
#   rs <- list(
#     list(name = "a", runtime_ms = 120, scores = c(0.2, 0.4, 5.0)),
#     list(name = "b", runtime_ms = 90,  scores = c(0.3, 0.35, 0.31))
#   )
#   normalise_results(rs)
