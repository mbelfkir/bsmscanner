#pragma once

#include "bsm/core/types.hpp"

#include <functional>
#include <optional>
#include <string>

namespace bsm::core {

using ValueResolver = std::function<const Value&(const std::string&)>;
using CustomConstraintCallback =
    std::function<double(const ConstraintSpec&, const ValueResolver&)>;

void register_custom_constraint(const std::string& name,
                                CustomConstraintCallback callback);

std::optional<CustomConstraintCallback> find_custom_constraint(
    const std::string& name);

void finalize_constraint(ConstraintSpec& spec);

double evaluate_constraint(const ConstraintSpec& spec, const ValueResolver& resolver);

}  // namespace bsm::core
