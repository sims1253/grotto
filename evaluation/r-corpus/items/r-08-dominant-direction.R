# A tiny principal-direction calculator on a covariance matrix, written
# with explicit indexing, nested brackets, and apply over margins.

dominant_direction <- function(m, n_vectors = 1) {
  if (!is.matrix(m) || nrow(m) != ncol(m)) {
    stop("m must be a square matrix")
  }
  d <- nrow(m)
  if (n_vectors < 1 || n_vectors > d) {
    stop("n_vectors must be in [1, dim(m)]")
  }

  # power iteration with deflation on the absolute values of m
  remaining <- abs(m)
  vectors <- matrix(0, nrow = d, ncol = n_vectors)
  values <- numeric(n_vectors)

  for (k in seq_len(n_vectors)) {
    v <- rep(1 / sqrt(d), d)  # deterministic start vector
    for (iter in 1:100) {
      w <- remaining %*% v
      norm <- sqrt(sum(w * w))
      if (norm < 1e-12) {
        break
      }
      v_new <- w / norm
      if (max(abs(v_new - v)) < 1e-9) {
        v <- v_new
        break
      }
      v <- v_new
    }
    vectors[, k] <- v
    values[k] <- as.numeric(t(v) %*% remaining %*% v)
    remaining <- remaining - values[k] * (v %o% v)  # deflate
  }

  list(values = values, vectors = vectors)
}

# Per-variable spread of a data matrix, applied column-wise.

column_spread <- function(x) {
  apply(x, 2, function(col) {
    col <- col[!is.na(col)]
    if (length(col) < 2) return(NA_real_)
    (quantile(col, 0.75) - quantile(col, 0.25)) / max(sd(col), 1e-9)
  })
}

# Example (not run):
#   m <- cov(matrix(rnorm(200), ncol = 4))
#   pd <- dominant_direction(m, n_vectors = 2)
#   pd$values[1] >= pd$values[2] - 1e-8  # deflation keeps ordering
#   round(column_spread(matrix(rnorm(100), ncol = 5)), 3)
