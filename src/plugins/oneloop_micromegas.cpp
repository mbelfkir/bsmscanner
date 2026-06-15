#include "bsm/core/functions.hpp"
#include "bsm/core/plugins.hpp"

#include <algorithm>
#include <cmath>
#include <complex>
#include <limits>
#include <mutex>
#include <optional>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

#ifdef BSM_SCANNER_ENABLE_ONELOOP_MICROMEGAS
#include "micromegas.h"
#include "micromegas_aux.h"
#include "VandP.h"
#endif

namespace bsm::plugins::oneloop_micromegas {

namespace {

constexpr double kPi = 3.14159265358979323846;
constexpr const char* kTargetNameBinding = "dm_target_name";

struct OneloopMicromegasInputs {
  std::vector<std::pair<std::string, double>> numeric_assignments;
  std::string dm_target_name;
};

struct OneloopMicromegasResult {
  int err_dm = -1;
  bool candidate_valid = false;
  bool target_match = false;
  double candidate_mass = std::numeric_limits<double>::quiet_NaN();
  double omega = std::numeric_limits<double>::quiet_NaN();
  double sigma_si = std::numeric_limits<double>::quiet_NaN();
  double dd_pvalue = std::numeric_limits<double>::quiet_NaN();
  std::string candidate_name;
};

bool same_inputs(const OneloopMicromegasInputs& lhs,
                 const OneloopMicromegasInputs& rhs) {
  return lhs.numeric_assignments == rhs.numeric_assignments &&
         lhs.dm_target_name == rhs.dm_target_name;
}

double coerce_numeric_argument(const bsm::core::Value& value,
                               const std::string& name) {
  if (const auto* real = std::get_if<double>(&value)) {
    return *real;
  }
  if (const auto* boolean = std::get_if<bool>(&value)) {
    return *boolean ? 1.0 : 0.0;
  }
  if (const auto* complex = std::get_if<std::complex<double>>(&value)) {
    if (std::abs(complex->imag()) > 1.0e-14) {
      throw std::runtime_error(
          "oneloop_micromegas plugin binding '" + name +
          "' cannot be coerced from a complex value with non-zero imaginary part.");
    }
    return complex->real();
  }
  throw std::runtime_error(
      "oneloop_micromegas plugin binding '" + name +
      "' must be a scalar numeric value.");
}

std::string require_string_argument(const bsm::core::Value& value,
                                    const std::string& name) {
  if (const auto* string = std::get_if<std::string>(&value)) {
    return *string;
  }
  throw std::runtime_error(
      "oneloop_micromegas plugin binding '" + name + "' must be a string.");
}

OneloopMicromegasInputs parse_inputs(const bsm::core::PluginInvocation& invocation) {
  OneloopMicromegasInputs inputs;
  inputs.numeric_assignments.reserve(invocation.arguments.size());

  bool target_name_seen = false;
  for (const auto& [binding_name, value] : invocation.arguments) {
    if (binding_name == kTargetNameBinding) {
      inputs.dm_target_name = require_string_argument(value, binding_name);
      target_name_seen = true;
      continue;
    }
    inputs.numeric_assignments.emplace_back(
        binding_name,
        coerce_numeric_argument(value, binding_name));
  }

  if (!target_name_seen) {
    throw std::runtime_error(
        "oneloop_micromegas plugin requires the string binding 'dm_target_name'.");
  }

  std::sort(inputs.numeric_assignments.begin(),
            inputs.numeric_assignments.end(),
            [](const auto& lhs, const auto& rhs) { return lhs.first < rhs.first; });
  return inputs;
}

#ifdef BSM_SCANNER_ENABLE_ONELOOP_MICROMEGAS

std::mutex& micromegas_mutex() {
  static std::mutex instance;
  return instance;
}

bool is_assignable_model_parameter(const std::string& name) {
  for (int index = 0; index < nModelVars; ++index) {
    if (varNames[index] != nullptr && name == varNames[index]) {
      return true;
    }
  }
  return false;
}

bool may_be_derived_backend_quantity(const std::string& name) {
  // Some oneloop CalcHEP exports keep MA02/thetaa as external parameters,
  // while newer CH exports derive them from MH01/MH02/MA01/thetah.
  return name == "MA02" || name == "thetaa";
}

void assign_model_parameters(const OneloopMicromegasInputs& inputs) {
  for (const auto& [binding_name, assigned_value] : inputs.numeric_assignments) {
    if (!is_assignable_model_parameter(binding_name)) {
      if (may_be_derived_backend_quantity(binding_name)) {
        continue;
      }
      throw std::runtime_error(
          "micrOMEGAs model does not expose assignable parameter '" +
          binding_name + "' for the oneloop plugin.");
    }
    const int status = assignValW(const_cast<char*>(binding_name.c_str()), assigned_value);
    if (status != 0) {
      throw std::runtime_error(
          "Failed to assign micrOMEGAs parameter '" + binding_name +
          "' for the oneloop plugin.");
    }
  }
}

double find_candidate_mass(const std::string& candidate_name) {
  if (candidate_name.empty()) {
    return std::numeric_limits<double>::quiet_NaN();
  }
  for (int index = 1; index <= Ncdm; ++index) {
    if (CDM[index] != nullptr && candidate_name == CDM[index]) {
      return McdmN[index];
    }
  }
  return std::numeric_limits<double>::quiet_NaN();
}

double compute_sigma_si(const std::string& candidate_name) {
  if (candidate_name.empty()) {
    return std::numeric_limits<double>::quiet_NaN();
  }

  const double nucleon_mass = 0.939;
  double fallback_si = std::numeric_limits<double>::quiet_NaN();

  for (int index = 1; index <= Ncdm; ++index) {
    if (CDM[index] == nullptr) {
      continue;
    }
    double pA0[2] = {0.0, 0.0};
    double pA5[2] = {0.0, 0.0};
    double nA0[2] = {0.0, 0.0};
    double nA5[2] = {0.0, 0.0};
    const int status = nucleonAmplitudes(CDM[index], pA0, pA5, nA0, nA5);
    if (status != 0) {
      continue;
    }

    const double reduced_mass =
        nucleon_mass * McdmN[index] / (nucleon_mass + McdmN[index]);
    const double prefactor =
        4.0 / kPi * 3.8937966E8 * reduced_mass * reduced_mass;
    const double sigma_si =
        prefactor * std::max(pA0[0] * pA0[0], nA0[0] * nA0[0]);

    if (!std::isfinite(fallback_si)) {
      fallback_si = sigma_si;
    }
    if (candidate_name == CDM[index]) {
      return sigma_si;
    }
  }

  return fallback_si;
}

OneloopMicromegasResult evaluate_impl(const OneloopMicromegasInputs& inputs) {
  std::lock_guard<std::mutex> lock(micromegas_mutex());

  assign_model_parameters(inputs);
  VZdecay = 0;
  VWdecay = 0;
  ForceUG = 0;

  char candidate_buffer[64] = {0};
  OneloopMicromegasResult result;
  result.err_dm = sortOddParticles(candidate_buffer);
  result.candidate_name = candidate_buffer;
  result.candidate_valid = (result.err_dm == 0) && !result.candidate_name.empty();
  result.target_match = result.candidate_name == inputs.dm_target_name;
  result.candidate_mass = find_candidate_mass(result.candidate_name);
  if (result.candidate_valid) {
    result.sigma_si = compute_sigma_si(result.candidate_name);
  }

  if (!result.candidate_valid) {
    result.omega = -99.0;
    result.dd_pvalue = -1.0;
    return result;
  }

  double xf = 0.0;
  int omega_error = 0;
  const double omega =
      Ncdm == 1 ? darkOmega(&xf, 1, 1.0e-4, &omega_error)
                : darkOmegaN(1, 1.0e-4, &omega_error);
  if (omega_error == 0 && std::isfinite(omega) && omega >= 0.0) {
    result.omega = omega;
  } else {
    result.omega = -99.0;
  }

  char* experiment_name = nullptr;
  const double dd_pvalue = DD_pval(AllDDexp, Maxwell, &experiment_name);
  if (std::isfinite(dd_pvalue)) {
    result.dd_pvalue = dd_pvalue;
  } else {
    result.dd_pvalue = -1.0;
  }

  return result;
}

const OneloopMicromegasResult& evaluate_cached(
    const bsm::core::PluginInvocation& invocation) {
  thread_local std::optional<OneloopMicromegasInputs> cached_inputs;
  thread_local std::optional<OneloopMicromegasResult> cached_result;

  const OneloopMicromegasInputs inputs = parse_inputs(invocation);
  if (cached_inputs.has_value() && cached_result.has_value() &&
      same_inputs(*cached_inputs, inputs)) {
    return *cached_result;
  }

  cached_inputs = inputs;
  cached_result = evaluate_impl(inputs);
  return *cached_result;
}

bsm::core::Value omega(const bsm::core::PluginInvocation& invocation) {
  return evaluate_cached(invocation).omega;
}

bsm::core::Value sigma_si(const bsm::core::PluginInvocation& invocation) {
  return evaluate_cached(invocation).sigma_si;
}

bsm::core::Value dd_pvalue(const bsm::core::PluginInvocation& invocation) {
  return evaluate_cached(invocation).dd_pvalue;
}

bsm::core::Value candidate_mass(const bsm::core::PluginInvocation& invocation) {
  return evaluate_cached(invocation).candidate_mass;
}

bsm::core::Value target_match(const bsm::core::PluginInvocation& invocation) {
  return evaluate_cached(invocation).target_match;
}

bsm::core::Value candidate_valid(const bsm::core::PluginInvocation& invocation) {
  return evaluate_cached(invocation).candidate_valid;
}

bsm::core::Value candidate_name(const bsm::core::PluginInvocation& invocation) {
  return evaluate_cached(invocation).candidate_name;
}

struct PluginRegistrar {
  PluginRegistrar() {
    bsm::core::register_plugin_function("oneloop_micromegas", "omega", omega);
    bsm::core::register_plugin_function("oneloop_micromegas", "sigma_si", sigma_si);
    bsm::core::register_plugin_function("oneloop_micromegas", "dd_pvalue", dd_pvalue);
    bsm::core::register_plugin_function("oneloop_micromegas", "candidate_mass",
                                        candidate_mass);
    bsm::core::register_plugin_function("oneloop_micromegas", "target_match",
                                        target_match);
    bsm::core::register_plugin_function("oneloop_micromegas", "candidate_valid",
                                        candidate_valid);
    bsm::core::register_plugin_function("oneloop_micromegas", "candidate_name",
                                        candidate_name);
  }
};

const PluginRegistrar kRegistrar{};

#endif

}  // namespace

}  // namespace bsm::plugins::oneloop_micromegas
