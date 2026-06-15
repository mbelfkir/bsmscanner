#include "bsm/core/functions.hpp"

#include <cmath>
#include <limits>
#include <stdexcept>

namespace bsm::core {

namespace {

bool is_complex_value(const ScalarValue& value) {
  return std::holds_alternative<std::complex<double>>(value);
}

}  // namespace

double scalar_to_real(const ScalarValue& value) {
  if (const auto* real = std::get_if<double>(&value)) {
    return *real;
  }
  if (const auto* boolean = std::get_if<bool>(&value)) {
    return *boolean ? 1.0 : 0.0;
  }
  if (const auto* complex = std::get_if<std::complex<double>>(&value)) {
    if (std::abs(complex->imag()) > 1e-14) {
      throw std::runtime_error("Cannot coerce non-real complex value to real.");
    }
    return complex->real();
  }
  throw std::runtime_error("Unsupported scalar coercion to real.");
}

bool scalar_to_bool(const ScalarValue& value) {
  if (const auto* boolean = std::get_if<bool>(&value)) {
    return *boolean;
  }
  if (const auto* real = std::get_if<double>(&value)) {
    return *real != 0.0;
  }
  if (const auto* complex = std::get_if<std::complex<double>>(&value)) {
    return std::abs(*complex) != 0.0;
  }
  throw std::runtime_error("Unsupported scalar coercion to bool.");
}

std::complex<double> scalar_to_complex(const ScalarValue& value) {
  if (const auto* complex = std::get_if<std::complex<double>>(&value)) {
    return *complex;
  }
  if (const auto* real = std::get_if<double>(&value)) {
    return std::complex<double>(*real, 0.0);
  }
  if (const auto* boolean = std::get_if<bool>(&value)) {
    return std::complex<double>(*boolean ? 1.0 : 0.0, 0.0);
  }
  throw std::runtime_error("Unsupported scalar coercion to complex.");
}

ScalarValue execute_builtin_function(std::string_view name,
                                     const std::vector<ScalarValue>& args) {
  if (name == "nan") {
    if (!args.empty()) {
      throw std::runtime_error("nan() does not accept arguments.");
    }
    return std::numeric_limits<double>::quiet_NaN();
  }

  if (name == "sqrt") {
    if (is_complex_value(args.front())) {
      return std::sqrt(scalar_to_complex(args.front()));
    }
    return std::sqrt(scalar_to_real(args.front()));
  }

  if (name == "log") {
    if (is_complex_value(args.front())) {
      return std::log(scalar_to_complex(args.front()));
    }
    return std::log(scalar_to_real(args.front()));
  }

  if (name == "exp") {
    if (is_complex_value(args.front())) {
      return std::exp(scalar_to_complex(args.front()));
    }
    return std::exp(scalar_to_real(args.front()));
  }

  if (name == "sin") {
    if (is_complex_value(args.front())) {
      return std::sin(scalar_to_complex(args.front()));
    }
    return std::sin(scalar_to_real(args.front()));
  }

  if (name == "cos") {
    if (is_complex_value(args.front())) {
      return std::cos(scalar_to_complex(args.front()));
    }
    return std::cos(scalar_to_real(args.front()));
  }

  if (name == "asin") {
    if (is_complex_value(args.front())) {
      return std::asin(scalar_to_complex(args.front()));
    }
    return std::asin(scalar_to_real(args.front()));
  }

  if (name == "atan") {
    if (is_complex_value(args.front())) {
      return std::atan(scalar_to_complex(args.front()));
    }
    return std::atan(scalar_to_real(args.front()));
  }

  if (name == "atan2") {
    return std::atan2(scalar_to_real(args.at(0)), scalar_to_real(args.at(1)));
  }

  if (name == "abs") {
    if (is_complex_value(args.front())) {
      return std::abs(scalar_to_complex(args.front()));
    }
    return std::abs(scalar_to_real(args.front()));
  }

  if (name == "arg") {
    return std::arg(scalar_to_complex(args.front()));
  }

  if (name == "real") {
    return scalar_to_complex(args.front()).real();
  }

  if (name == "imag") {
    return scalar_to_complex(args.front()).imag();
  }

  if (name == "conj") {
    return std::conj(scalar_to_complex(args.front()));
  }

  if (name == "fmod") {
    return std::fmod(scalar_to_real(args.at(0)), scalar_to_real(args.at(1)));
  }

  if (name == "min") {
    double result = std::numeric_limits<double>::infinity();
    for (const auto& arg : args) {
      result = std::min(result, scalar_to_real(arg));
    }
    return result;
  }

  if (name == "max") {
    double result = -std::numeric_limits<double>::infinity();
    for (const auto& arg : args) {
      result = std::max(result, scalar_to_real(arg));
    }
    return result;
  }

  if (name == "isfinite") {
    if (is_complex_value(args.front())) {
      const auto value = scalar_to_complex(args.front());
      return std::isfinite(value.real()) && std::isfinite(value.imag());
    }
    return std::isfinite(scalar_to_real(args.front()));
  }

  if (name == "if_else") {
    return scalar_to_bool(args.at(0)) ? args.at(1) : args.at(2);
  }

  throw std::runtime_error("Unknown builtin function: " + std::string(name));
}

}  // namespace bsm::core
