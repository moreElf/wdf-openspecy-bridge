# Batch identification with the OpenSpecy R package (tested API: CRAN 2.0.x).
# Pipeline: read_any -> Raman library (lib$raman / filter_spec) -> process_spec -> match_spec(conform = TRUE)
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
lib_ok <- tryCatch({
  check_lib(lib_name, condition = "error")
  TRUE
}, error = function(e) FALSE)
if (!lib_ok) {
  get_lib(lib_name)
}
lib <- load_lib(lib_name)
# OpenSpecy 2.x ships libraries split by technique; older ones are one object to filter.
lib <- if (is_OpenSpecy(lib)) {
  filter_spec(lib, logic = tolower(lib$metadata$spectrum_type) == "raman")
} else {
  lib$raman
}

use_derivative <- lib_name == "derivative"

results <- lapply(inputs, function(f) {
  x <- read_any(f)
  x <- process_spec(
    x,
    conform_spec = FALSE,  # match_spec(conform = TRUE) aligns to the library axis
    smooth_intens = use_derivative,
    smooth_intens_args = list(polynomial = 3, window = 11, derivative = 1, abs = TRUE),
    subtr_baseline = !use_derivative,
    make_rel = TRUE
  )
  hits <- match_spec(x, library = lib, na.rm = TRUE, conform = TRUE, top_n = top_n,
                     add_library_metadata = "sample_name")
  hits <- as.data.frame(hits)
  hits <- hits[order(hits$object_id, -hits$match_val), , drop = FALSE]
  hits$input_file <- basename(f)
  group <- if ("object_id" %in% names(hits)) hits$object_id else rep(1, nrow(hits))
  hits$rank <- ave(seq_len(nrow(hits)), group, FUN = seq_along)
  hits
})

all_cols <- unique(unlist(lapply(results, names)))
results <- lapply(results, function(d) {
  d[setdiff(all_cols, names(d))] <- NA
  d[all_cols]
})
out <- do.call(rbind, results)
front <- intersect(c("input_file", "object_id", "rank", "match_val", "spectrum_identity",
                     "material_class", "sample_name"), names(out))
out <- out[c(front, setdiff(names(out), front))]
# Drop list columns that write.csv cannot serialise.
out <- out[!vapply(out, is.list, logical(1))]
write.csv(out, out_csv, row.names = FALSE, fileEncoding = "UTF-8")
cat(sprintf("wrote %d rows to %s\n", nrow(out), out_csv))
