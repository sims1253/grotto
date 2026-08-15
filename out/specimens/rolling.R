# rolling.R -- exponential moving average
library(dplyr)

DEFAULT_DECAY <- 0.92

rolling_mean <- function(values, decay = DEFAULT_DECAY) {
  #' Exponentially-smoothed mean of `values`.
  acc <- 0
  for (x in values) {
    acc <- decay * acc + (1 - decay) * x
  }
  return(acc)
}

result <- rolling_mean(c(1, 2, 3))
print(result)
