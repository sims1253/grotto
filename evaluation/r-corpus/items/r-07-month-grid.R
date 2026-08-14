# Month-grid helpers: expand a date range into per-month buckets and
# label them for report headers.  Base-R date handling only.

month_grid <- function(start, end) {
  start <- as.Date(start)
  end <- as.Date(end)
  if (is.na(start) || is.na(end)) {
    stop("start and end must be parseable as dates")
  }
  if (start > end) {
    tmp <- start
    start <- end
    end <- tmp
  }

  # first day of every month touching the range
  month_starts <- seq.Date(from = as.Date(cut(start, "month")),
                           to = end, by = "month")

  data.frame(
    month_start = month_starts,
    month_label = format(month_starts, "%Y-%m"),
    quarter = paste0("Q", (as.integer(format(month_starts, "%m")) - 1) %/% 3 + 1),
    is_leap = (as.integer(format(month_starts, "%Y")) %% 4 == 0)
  )
}

# Assign each observation date to its month bucket and count hits.
# Dates outside the grid are counted in the "outside" bucket instead of
# being dropped silently.

bucket_by_month <- function(dates, grid) {
  dates <- as.Date(dates)
  labels <- grid$month_label
  key <- format(as.Date(cut(dates, "month")), "%Y-%m")

  counts <- setNames(numeric(length(labels)), labels)
  inside <- key %in% labels
  for (k in key[inside]) {
    counts[k] <- counts[k] + 1
  }

  list(counts = counts, outside = sum(!inside, na.rm = TRUE))
}

# Example (not run):
#   grid <- month_grid("2023-11-15", "2024-03-02")
#   grid$month_label
#   #> [1] "2023-11" "2023-12" "2024-01" "2024-02" "2024-03"
#   bucket_by_month(c("2023-12-24", "2024-01-02", "2025-08-01"), grid)
#   #> $counts: 2023-11 2023-12 2024-01 2024-02 2024-03 = 0 1 1 0 0
#   #> $outside: 1
