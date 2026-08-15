#include "bsm/core/table_interpolation.hpp"

#include <algorithm>

namespace bsm::core::table {

void validate_ascending(const std::vector<std::vector<double>>& table,
                        const std::string& empty_message,
                        const std::string& ascending_message) {
  if (table.empty()) {
    throw std::runtime_error(empty_message);
  }
  if (table.size() <= 1) {
    return;
  }
  for (std::size_t i = 1; i < table.size(); ++i) {
    if (!(table[i - 1].at(0) < table[i].at(0))) {
      throw std::runtime_error(ascending_message);
    }
  }
}

double interpolate_linear(const std::vector<std::vector<double>>& table, double x) {
  if (x <= table.front().at(0)) {
    return table.front().at(1);
  }
  if (x >= table.back().at(0)) {
    return table.back().at(1);
  }
  for (std::size_t i = 1; i < table.size(); ++i) {
    const auto& left = table[i - 1];
    const auto& right = table[i];
    if (x <= right.at(0)) {
      const double span = right.at(0) - left.at(0);
      const double weight = (x - left.at(0)) / span;
      return (1.0 - weight) * left.at(1) + weight * right.at(1);
    }
  }
  return table.back().at(1);
}

std::vector<double> build_natural_cubic_spline_second_derivatives(
    const std::vector<std::vector<double>>& table) {
  const std::size_t n = table.size();
  std::vector<double> second(n, 0.0);
  if (n <= 2) {
    return second;
  }

  std::vector<double> u(n - 1, 0.0);
  for (std::size_t i = 1; i + 1 < n; ++i) {
    const double x_im1 = table[i - 1].at(0);
    const double x_i = table[i].at(0);
    const double x_ip1 = table[i + 1].at(0);
    const double y_im1 = table[i - 1].at(1);
    const double y_i = table[i].at(1);
    const double y_ip1 = table[i + 1].at(1);

    const double sig = (x_i - x_im1) / (x_ip1 - x_im1);
    const double p = sig * second[i - 1] + 2.0;
    second[i] = (sig - 1.0) / p;
    u[i] = (6.0 *
                (((y_ip1 - y_i) / (x_ip1 - x_i)) -
                 ((y_i - y_im1) / (x_i - x_im1))) /
                (x_ip1 - x_im1) -
            sig * u[i - 1]) /
           p;
  }

  second[n - 1] = 0.0;
  for (std::size_t k = n - 1; k-- > 0;) {
    second[k] = second[k] * second[k + 1] + u[k];
  }
  return second;
}

double interpolate_cubic_spline(const std::vector<std::vector<double>>& table,
                                const std::vector<double>& second,
                                double x) {
  if (table.size() <= 1) {
    return table.front().at(1);
  }
  if (x <= table.front().at(0)) {
    x = table.front().at(0);
  } else if (x >= table.back().at(0)) {
    x = table.back().at(0);
  }

  auto upper = std::lower_bound(
      table.begin(),
      table.end(),
      x,
      [](const std::vector<double>& row, double value) { return row.at(0) < value; });
  std::size_t hi = static_cast<std::size_t>(upper - table.begin());
  if (hi == 0) {
    hi = 1;
  } else if (hi >= table.size()) {
    hi = table.size() - 1;
  }
  const std::size_t lo = hi - 1;

  const double x_lo = table[lo].at(0);
  const double x_hi = table[hi].at(0);
  const double y_lo = table[lo].at(1);
  const double y_hi = table[hi].at(1);
  const double h = x_hi - x_lo;
  if (!(h > 0.0)) {
    throw std::runtime_error("Lookup table contains a non-positive spline interval.");
  }
  const double a = (x_hi - x) / h;
  const double b = (x - x_lo) / h;
  return a * y_lo + b * y_hi +
         ((a * a * a - a) * second[lo] + (b * b * b - b) * second[hi]) *
             (h * h) / 6.0;
}

}  // namespace bsm::core::table
