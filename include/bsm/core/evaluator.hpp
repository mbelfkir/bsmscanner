#pragma once

#include "bsm/core/graph.hpp"
#include "bsm/core/status.hpp"

#include <string>
#include <unordered_map>
#include <vector>

namespace bsm::core {

class CompiledModel {
 public:
  explicit CompiledModel(CompiledModelPlan plan);

  PointResult evaluate(const std::unordered_map<std::string, Value>& inputs) const;
  const CompiledModelPlan& plan() const noexcept { return plan_; }

 private:
  std::size_t require_index(const std::string& name) const;

  CompiledModelPlan plan_;
  std::unordered_map<std::string, std::size_t> name_to_index_;
  std::vector<std::size_t> evaluation_order_indices_;
};

}  // namespace bsm::core

