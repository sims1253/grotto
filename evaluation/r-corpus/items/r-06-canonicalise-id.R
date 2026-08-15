# Canonicalise messy sample identifiers like "A_01", "a-1", "S3#a2"
# into a stable "A01" form, and classify rows of a lookup table by them.

canon_id <- function(x) {
  if (!is.character(x)) {
    x <- as.character(x)
  }
  upper <- toupper(trimws(x))
  upper <- gsub("[^A-Z0-9]+", "", upper)  # strip separators and symbols
  sub("^([A-Z]+)([0-9]+)$", "\\1\\2", upper)
}

# Split "GENE007" style ids into letter prefix and numeric suffix.
# Returns a data frame with the original id plus the two parts.

split_id <- function(x) {
  ok <- grepl("^[A-Za-z]+[0-9]+$", x)
  if (!all(ok)) {
    warning(sprintf("%d id(s) do not match <letters><digits>", sum(!ok)))
  }
  prefix <- sub("^([A-Za-z]+)[0-9]+$", "\\1", x)
  suffix <- sub("^[A-Za-z]+([0-9]+)$", "\\1", x)
  number <- suppressWarnings(as.numeric(ifelse(ok, suffix, NA)))
  data.frame(raw = x, valid = ok, prefix = prefix, number = number)
}

# Build a compact label like "A01/B02" for a pair of ids, padding the
# numeric part to a common width.

pair_label <- function(a, b, width = 2) {
  pa <- split_id(a)
  pb <- split_id(b)
  fmt <- function(p) {
    sprintf("%s%0*d", p$prefix, width, p$number)
  }
  sprintf("%s/%s", fmt(pa), fmt(pb))
}

# Example (not run):
#   canon_id(c(" a-1 ", "A_01", "s3#a2"))
#   #> [1] "A1"  "A01" "S3A2"
#   pair_label("a1", "B14")
#   #> [1] "a01/B14"
