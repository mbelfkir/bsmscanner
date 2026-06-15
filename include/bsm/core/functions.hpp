#pragma once

#include "bsm/core/types.hpp"

#include <string_view>
#include <vector>

namespace bsm::core {

double scalar_to_real(const ScalarValue& value);
bool scalar_to_bool(const ScalarValue& value);
std::complex<double> scalar_to_complex(const ScalarValue& value);
ScalarValue execute_builtin_function(std::string_view name,
                                     const std::vector<ScalarValue>& args);

}  // namespace bsm::core
