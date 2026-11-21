# Plot a reference band (low/high envelope) around a mean line with base
# graphics.  The point is careful par() handling: save, modify, restore.

plot_with_band <- function(x, y, lower, upper, xlab = "x", ylab = "y",
                           main = "", col_line = "steelblue") {
  if (length(x) != length(y) || length(lower) != length(x) || length(upper) != length(x)) {
    stop("x, y, lower, upper must have equal length")
  }

  old_par <- par(no.readonly = TRUE)  # remember margins so callers are safe
  on.exit(par(old_par), add = TRUE)

  par(mar = c(4.2, 4.2, 2.5, 0.8))  # wider left/bottom for labels
  plot(range(x), range(c(lower, upper), na.rm = TRUE), type = "n",
       xlab = xlab, ylab = ylab, main = main)

  # filled envelope behind the line
  polygon(c(x, rev(x)), c(upper, rev(lower)),
          col = adjustcolor(col_line, alpha.f = 0.15), border = NA)

  lines(x, y, col = col_line, lwd = 2)
  lines(x, upper, col = col_line, lty = 2, lwd = 0.8)
  lines(x, lower, col = col_line, lty = 2, lwd = 0.8)

  # annotate the extremes so the printed figure is self-describing
  i_peak <- which.max(y)
  points(x[i_peak], y[i_peak], pch = 19, col = col_line)
  text(x[i_peak], y[i_peak], labels = sprintf("peak %g", y[i_peak]),
       pos = ifelse(y[i_peak] > mean(y, na.rm = TRUE), 1, 3), cex = 0.8)

  invisible(list(peak_index = i_peak, peak_value = y[i_peak]))
}

# Example (not run):
#   x <- seq(0, 2 * pi, length.out = 50)
#   y <- sin(x)
#   plot_with_band(x, y, y - 0.1, y + 0.1, xlab = "phase", ylab = "signal",
#                  main = "sine with band")
