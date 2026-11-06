# Batch identification with the OpenSpecy R package (tested: CRAN 2.0.3).
#
# Usage:
#   Rscript openspecy_match.R <preset> <transformation> <lib_type> <spectrum_type> <top_n> \
#     <in1.csv> <out1.csv> [<in2.csv> <out2.csv> ...]
#
#   Each input gets its own result file; the library is loaded once for the batch.
#
#   preset:         "web"    - reproduce openspecy.org defaults (the Shiny app bundled in OpenSpecy,
#                              inst/shiny): medoid library, 90 cm-1 Savitzky-Golay window, "Mean Up"
#                              6 cm-1 conformation, all spectrum types, match_spec(type = "roll").
#                   "legacy" - the pipeline used before v0.2: full Raman library, 11-point window,
#                              match_spec(conform = TRUE).
#   transformation: "derivative" or "nobaseline"
#   lib_type:       "medoid" or "full" (web preset only; legacy always uses the full library)
#   spectrum_type:  "all", "raman", "ftir" or "nir" (web preset only; legacy always uses "raman")

suppressPackageStartupMessages(library(OpenSpecy))

args <- commandArgs(trailingOnly = TRUE)
files <- args[-(1:5)]
if (length(args) < 7 || length(files) %% 2 != 0) {
  stop("usage: openspecy_match.R <preset> <transformation> <lib_type> <spectrum_type> <top_n> ",
       "<in1.csv> <out1.csv> [<in2.csv> <out2.csv> ...]")
}
preset <- match.arg(args[[1]], c("web", "legacy"))
transformation <- match.arg(args[[2]], c("derivative", "nobaseline"))
lib_type <- match.arg(args[[3]], c("medoid", "full"))
spectrum_type <- match.arg(args[[4]], c("all", "raman", "ftir", "nir"))
top_n <- as.integer(args[[5]])
inputs <- files[c(TRUE, FALSE)]
outputs <- files[c(FALSE, TRUE)]

if (preset == "legacy") {
  lib_type <- "full"
  spectrum_type <- "raman"
}

# Same artifact names as the web app's library_source().
lib_name <- if (lib_type == "medoid") paste0("medoid_", transformation) else transformation

# Downloads the library once into the package's cache directory.
lib_ok <- tryCatch({
  check_lib(lib_name, condition = "error")
  TRUE
}, error = function(e) FALSE)
if (!lib_ok) {
  get_lib(lib_name)
}
artifact <- load_lib(lib_name)

# OpenSpecy 2.x ships libraries split by technique; older ones are one object to filter.
select_spectrum_type <- function(artifact, type) {
  if (is_OpenSpecy(artifact)) {
    if (type == "all") return(artifact)
    return(filter_spec(artifact, logic = tolower(artifact$metadata$spectrum_type) == type))
  }
  if (type != "all") return(artifact[[type]])
  # As app_select_library_spectrum_type(): union axis, NA outside each technique's range.
  typed <- artifact[intersect(c("ftir", "raman", "nir"), names(artifact))]
  c_spec(unname(typed), range = "full", res = 6)
}
lib <- select_spectrum_type(artifact, spectrum_type)

# --- web preset: mirrors ordinary_process() + identify_blockwise() in the bundled app ---
web_conform_res <- 6     # "Wavenumber Resolution" slider default
web_window_cm <- 90      # "Wavenumber Window" slider default

match_web <- function(x) {
  # "Mean Up": keep the upload's axis when it is already finer than 6 cm-1 and
  # conform the library onto it instead; otherwise resample the upload.
  native <- spec_res(x)
  preserve_axis <- !is.finite(native) || web_conform_res >= native
  if (!preserve_axis) {
    x <- conform_spec(x, range = conform_res(x$wavenumber, res = web_conform_res),
                      res = NULL, type = "interp")
  }
  x <- process_spec(
    x,
    conform_spec = FALSE,
    smooth_intens = TRUE,
    smooth_intens_args = list(polynomial = 3,
                              window = calc_window_points(x$wavenumber, web_window_cm),
                              derivative = 1, abs = TRUE),
    subtr_baseline = FALSE,
    make_rel = TRUE
  )
  ref <- if (identical(lib$wavenumber, x$wavenumber)) lib else {
    conform_spec(lib, range = x$wavenumber, res = NULL, allow_na = anyNA(lib$spectra),
                 type = if (preserve_axis) "mean_up" else "roll")
  }
  match_spec(x, library = ref, na.rm = TRUE, conform = FALSE, type = "roll",
             top_n = top_n, add_library_metadata = "sample_name")
}

match_legacy <- function(x) {
  use_derivative <- transformation == "derivative"
  x <- process_spec(
    x,
    conform_spec = FALSE,  # match_spec(conform = TRUE) aligns to the library axis
    smooth_intens = use_derivative,
    smooth_intens_args = list(polynomial = 3, window = 11, derivative = 1, abs = TRUE),
    subtr_baseline = !use_derivative,
    make_rel = TRUE
  )
  match_spec(x, library = lib, na.rm = TRUE, conform = TRUE, top_n = top_n,
             add_library_metadata = "sample_name")
}

for (i in seq_along(inputs)) {
  f <- inputs[[i]]
  x <- read_any(f)
  hits <- as.data.frame(if (preset == "web") match_web(x) else match_legacy(x))
  group <- if ("object_id" %in% names(hits)) hits$object_id else rep(1, nrow(hits))
  ord <- order(group, -hits$match_val)
  hits <- hits[ord, , drop = FALSE]
  group <- group[ord]
  hits$input_file <- basename(f)
  hits$rank <- ave(seq_len(nrow(hits)), group, FUN = seq_along)

  front <- intersect(c("input_file", "object_id", "rank", "match_val", "material_class",
                       "spectrum_identity", "spectrum_type", "organization", "sample_name"),
                     names(hits))
  out <- hits[c(front, setdiff(names(hits), front))]
  # Drop list columns that write.csv cannot serialise.
  out <- out[!vapply(out, is.list, logical(1))]
  write.csv(out, outputs[[i]], row.names = FALSE, fileEncoding = "UTF-8")
  cat(sprintf("wrote %d rows to %s (preset=%s, library=%s, spectrum_type=%s)\n",
              nrow(out), outputs[[i]], preset, lib_name, spectrum_type))
}
