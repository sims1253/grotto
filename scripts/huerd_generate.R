#!/usr/bin/env Rscript
# Generate grotto night categorical colors with huerd (>= 0.6.2).
#
# Uses the NEW huerd capabilities: cvd_safe = TRUE (objective maximizes the
# worst-case distance across protan/deutan/tritan simulation) and
# include_colors (fixed colors -- the semantic anchors grotto will NOT give
# up, e.g. the error red).  Requires the huerd package installed from
# ../huerd (R CMD INSTALL); optimizer "sann" needs no nloptr, but nloptr is
# installed anyway so "nloptr_cobyla" (the default) is also available.
#
# usage: huerd_generate.R <pins.csv> <n_free> <runs> <seed> <iterations> <out.csv>
#   pins.csv : one hex per line (comma-free), the fixed colors
#   out.csv  : columns run, index, hex, is_pin, min_dist, min_cvd_safe

args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 6) {
  stop("usage: huerd_generate.R <pins.csv> <n_free> <runs> <seed> <iterations> <out.csv>")
}
pins_file <- args[1]
n_free <- as.integer(args[2])
runs <- as.integer(args[3])
seed <- as.integer(args[4])
iterations <- as.integer(args[5])
outfile <- args[6]

library(huerd)

pins <- toupper(trimws(readLines(pins_file, warn = FALSE)))
pins <- pins[nzchar(pins)]

rows <- list()
for (r in seq_len(runs)) {
  set.seed(seed + r - 1L)
  pal <- generate_palette(
    n = n_free + length(pins),
    include_colors = pins,
    optimizer = "sann",
    cvd_safe = TRUE,
    progress = FALSE,
    init_lightness_bounds = c(0.50, 0.95),
    max_iterations = iterations
  )
  hexes <- export_palette(pal, "hex")
  # pal carries its evaluation as attributes; recompute cleanly instead of
  # depending on the attribute layout across huerd versions
  ev <- evaluate_palette(hexes)
  for (i in seq_along(hexes)) {
    rows[[length(rows) + 1]] <- data.frame(
      run = r,
      index = i,
      hex = toupper(hexes[i]),
      is_pin = toupper(hexes[i]) %in% pins,
      min_dist = ev$distances$min,
      min_cvd_safe = ev$cvd_safety$worst_case_min_distance,
      stringsAsFactors = FALSE
    )
  }
}
out <- do.call(rbind, rows)
write.table(out, outfile, sep = ",", quote = FALSE, row.names = FALSE)
cat(sprintf(
  "huerd generation: %d run(s) x %d colors (pins: %s) -> %s\n",
  runs, n_free + length(pins), paste(pins, collapse = " "), outfile
))
