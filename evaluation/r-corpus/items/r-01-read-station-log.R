# Read a raw monitoring CSV and return a cleaned data frame.
#
# The station loggers append a status column that mixes numeric codes and
# the literal string "NA"; this helper coerces, filters, and sorts in one
# pass so downstream summaries never see the raw file again.

read_station_log <- function(path, keep_failed = FALSE, tz = "UTC") {
  raw <- read.csv(path, stringsAsFactors = FALSE, na.strings = c("NA", ""))

  # keep only the columns the pipeline actually consumes
  wanted <- c("station", "timestamp", "temp_c", "humidity", "status")
  missing <- setdiff(wanted, names(raw))
  if (length(missing) > 0) {
    stop("station log is missing columns: ", paste(missing, collapse = ", "))
  }
  log <- raw[, wanted]

  # numeric coercion: status sometimes arrives as "1", "0", or "ERR"
  log$temp_c <- suppressWarnings(as.numeric(log$temp_c))
  log$humidity <- suppressWarnings(as.numeric(log$humidity))
  log$status_code <- ifelse(log$status == "OK", 0L, -1L)

  # drop rows where both measurements failed, unless asked not to
  bad <- is.na(log$temp_c) & is.na(log$humidity)
  if (!keep_failed) {
    log <- log[!bad, ]
  }

  # parse timestamps; malformed rows become NA and are reported, not hidden
  log$timestamp <- as.POSIXct(log$timestamp, tz = tz, tryFormats = c(
    "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M", "%d-%m-%Y %H:%M:%S"
  ))
  n_unparsed <- sum(is.na(log$timestamp))
  if (n_unparsed > 0) {
    warning(sprintf("%d timestamp(s) could not be parsed in %s", n_unparsed, path))
  }

  # stable output order: station, then time
  log <- log[order(log$station, log$timestamp), ]
  rownames(log) <- NULL
  log
}

# Example (not run): merge two months of logs and report failure counts.
# full <- rbind(read_station_log("jan.csv"), read_station_log("feb.csv"))
# table(full$station, full$status_code)
