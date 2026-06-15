#pragma once

#include "bsm/core/types.hpp"

#include <optional>
#include <string>
#include <vector>

namespace bsm::core {

struct NodePlan {
  std::string name;
  NodeKind kind = NodeKind::Derived;
  ValueType value_type = ValueType::Unknown;
  std::vector<std::string> dependencies;
  bool active = true;

  std::optional<LiteralSpec> literal;
  std::optional<Program> program;
  std::optional<MatrixProgram> matrix;
  std::optional<ProjectionSpec> projection;
  std::optional<PluginCallSpec> plugin_call;
  std::optional<DiagonalizationSpec> diagonalization;
  std::optional<MixingMatrixSpec> mixing_matrix;
  std::optional<ConstraintSpec> constraint;
  std::optional<OutputSpec> output;

  bool fatal = false;
  std::string failure_message;
};

struct CompiledModelPlan {
  std::string name;
  std::string version;
  std::vector<NodePlan> nodes;
  std::vector<std::string> evaluation_order;
  std::vector<std::string> saved_outputs;
};

}  // namespace bsm::core
