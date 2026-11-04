# Batch identification with the OpenSpecy R package (>= 1.0).
# Usage: Rscript openspecy_match.R <out.csv> <library> <top_n> <in1.csv> [in2.csv ...]
#   library: "derivative" (default, recommended) or "nobaseline"

suppressPackageStartupMessages(library(OpenSpecy))

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 4) {
  stop("usage: openspecy_match.R <out.csv> <library> <top_n> <in.csv> ...")
}
out_csv <- args[[1]]
lib_name <- args[[2]]
top_n <- as.integer(args[[3]])
inputs <- args[-(1:3)]

# Downloads the library once into the package's cache directory.
if (!isTRUE(tryCatch(check_lib(lib_name), error = function(e) FALSE))) {
  get_lib(lib_name)
}
lib <- load_lib(lib_name)

use_derivative <- lib_name == "derivative"

results <- lapply(inputs, function(f) {
  x <- read_any(f)
  x <- process_spec(
    x,
    conform_spec = TRUE,
    conform_spec_args = list(range = lib$wavenumber, res = NULL),
    smooth_intens = use_derivative,
    smooth_intens_args = list(polynomial = 3, window = 11, derivative = 1, abs = TRUE),
    subtr_baseline = !use_derivative,
    make_rel = TRUE
  )
  hits <- match_spec(x, library = lib, na.rm = TRUE, top_n = top_n,
                     add_library_info = TRUE, order = x)
  hits <- as.data.frame(hits)
  hits$input_file <- basename(f)
  hits$rank <- seq_len(nrow(hits))
  hits
})

all_cols <- unique(unlist(lapply(results, names)))
results <- lapply(results, function(d) {
  d[setdiff(all_cols, names(d))] <- NA
  d[all_cols]
})
out <- do.call(rbind, results)
front <- intersect(c("input_file", "rank", "match_val", "spectrum_identity",
                     "material_class", "sample_name"), names(out))
out <- out[c(front, setdiff(names(out), front))]
# Drop list columns that write.csv cannot serialise.
out <- out[!vapply(out, is.list, logical(1))]
write.csv(out, out_csv, row.names = FALSE, fileEncoding = "UTF-8")
cat(sprintf("wrote %d rows to %s\n", nrow(out), out_csv))
