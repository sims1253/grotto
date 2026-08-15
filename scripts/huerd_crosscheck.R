#!/usr/bin/env Rscript
# huerd cross-check of grotto anchor-search variants (NON-CANDIDATE exploration).
#
# Sources the local huerd package (../huerd) WITHOUT installing it -- the
# optimizer files are skipped (nloptr not installed, and not needed) and only
# the post-hoc analysis functions are used, with the packaged sysdata lookup.
#
# Input:  CSV with columns id,keyword,string,function,type,number (hex colors
#         of a variant's NIGHT palette categorical roles).
# Output: TSV with huerd's palette-quality metrics per row: min OKLAB distance,
#         performance ratio (vs huerd's estimated max for the size), and the
#         worst-case / per-type CVD-safe minimum distances.
#
# This is a SECOND OPINION with different conventions from grotto's own
# metrics (huerd maximises the min pairwise distance of a free palette;
# grotto's colors are transform outputs).  Agreement is informative;
# disagreement is a finding, not a verdict.

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 2) {
  stop("usage: huerd_crosscheck.R <input.csv> <output.tsv>")
}
infile <- args[1]
outfile <- args[2]

repo <- normalizePath(file.path(dirname(sub("^--file=", "", grep("^--file=", commandArgs(), value = TRUE))), ".."))
huerd_dir <- file.path(dirname(repo), "huerd")

env <- new.env(parent = globalenv())
src <- list.files(file.path(huerd_dir, "R"), pattern = "\\.R$", full.names = TRUE)
src <- src[!grepl("optimization_core|generate_palette|sysdata", src)]
for (f in src) source(f, local = env)
load(file.path(huerd_dir, "R", "sysdata.rda"), envir = env)

d <- read.csv(infile, stringsAsFactors = FALSE, check.names = FALSE)
# NB: check.names=FALSE keeps the `function` column name intact (it is a
# reserved word; the default would rename it to `function.`).
roles <- c("keyword", "string", "function", "type", "number")

rows <- lapply(seq_len(nrow(d)), function(i) {
  hexes <- toupper(unlist(d[i, roles], use.names = FALSE))
  ev <- env$evaluate_palette(hexes)
  data.frame(
    id = d$id[i],
    min_oklab = round(ev$distances$min, 4),
    perf_ratio = round(ev$distances$performance_ratio, 3),
    cvd_worst = round(ev$cvd_safety$worst_case_min_distance, 4),
    cvd_protan = round(ev$cvd_safety$protan$min_distance, 4),
    cvd_deutan = round(ev$cvd_safety$deutan$min_distance, 4),
    cvd_tritan = round(ev$cvd_safety$tritan$min_distance, 4),
    stringsAsFactors = FALSE
  )
})
out <- do.call(rbind, rows)
write.table(out, outfile, sep = "\t", quote = FALSE, row.names = FALSE)
cat(sprintf("huerd cross-check: %d palettes -> %s\n", nrow(out), outfile))
