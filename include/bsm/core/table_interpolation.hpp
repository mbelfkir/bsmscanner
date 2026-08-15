#pragma once

#include <stdexcept>
#include <string>
#include <vector>

namespace bsm::core::table {

// Shared two-column [x, y] lookup-table interpolation.
//
// This is used both by the generic `table_lookup` constraint kind
// (src/constraints.cpp) and by plugin-specific table-based likelihood terms
// (e.g. the oneloop_likelihoods.neutrino_mass_term plugin in
// src/plugins/oneloop_likelihoods.cpp). The two previously carried
// independent, hand-copied implementations of this exact numerical logic;
// it is centralized here so a future fix to the interpolation math applies
// to every caller automatically instead of requiring the same patch in
// multiple files. See docs/dm_status.md and docs/release_notes_oneloop.md
// for the April 2026 table_lookup bug that motivated this consolidation.

// Validates that `table` is non-empty and that its x-values (column 0) are
// strictly increasing. A table with a single row is always valid. Throws
// std::runtime_error(empty_message) or std::runtime_error(ascending_message)
// on failure; callers can customize the messages to keep their existing
// error text.
void validate_ascending(
    const std::vector<std::vector<double>>& table,
    const std::string& empty_message = "Empty lookup table.",
    const std::string& ascending_message =
        "Lookup table x-values must be strictly increasing.");

// Piecewise-linear interpolation. Clamps to the table's endpoint y-values
// outside its x-domain.
double interpolate_linear(const std::vector<std::vector<double>>& table, double x);

// Second derivatives of a natural cubic spline through `table`, for use with
// interpolate_cubic_spline below.
std::vector<double> build_natural_cubic_spline_second_derivatives(
    const std::vector<std::vector<double>>& table);

// Natural cubic spline interpolation using precomputed second derivatives.
// Clamps `x` to the table's x-domain before evaluating. Throws
// std::runtime_error if two adjacent table points collapse to the same
// x-value (a degenerate spline interval).
double interpolate_cubic_spline(const std::vector<std::vector<double>>& table,
                                const std::vector<double>& second,
                                double x);

}  // namespace bsm::core::table
