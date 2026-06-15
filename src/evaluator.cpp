#include "bsm/core/evaluator.hpp"

#include "bsm/core/constraints.hpp"
#include "bsm/core/functions.hpp"
#include "bsm/core/plugins.hpp"

#include <Eigen/Eigenvalues>
#include <Eigen/SVD>

#include <algorithm>
#include <cmath>
#include <stdexcept>
#include <string>

namespace bsm::core {

namespace {

ScalarValue scalar_from_value(const Value& value) {
  if (const auto* real = std::get_if<double>(&value)) {
    return *real;
  }
  if (const auto* boolean = std::get_if<bool>(&value)) {
    return *boolean;
  }
  if (const auto* complex = std::get_if<std::complex<double>>(&value)) {
    return *complex;
  }
  throw std::runtime_error("Expression attempted to read a non-scalar node.");
}

ScalarValue add_values(const ScalarValue& lhs, const ScalarValue& rhs) {
  if (std::holds_alternative<std::complex<double>>(lhs) ||
      std::holds_alternative<std::complex<double>>(rhs)) {
    return scalar_to_complex(lhs) + scalar_to_complex(rhs);
  }
  return scalar_to_real(lhs) + scalar_to_real(rhs);
}

ScalarValue sub_values(const ScalarValue& lhs, const ScalarValue& rhs) {
  if (std::holds_alternative<std::complex<double>>(lhs) ||
      std::holds_alternative<std::complex<double>>(rhs)) {
    return scalar_to_complex(lhs) - scalar_to_complex(rhs);
  }
  return scalar_to_real(lhs) - scalar_to_real(rhs);
}

ScalarValue mul_values(const ScalarValue& lhs, const ScalarValue& rhs) {
  if (std::holds_alternative<std::complex<double>>(lhs) ||
      std::holds_alternative<std::complex<double>>(rhs)) {
    return scalar_to_complex(lhs) * scalar_to_complex(rhs);
  }
  return scalar_to_real(lhs) * scalar_to_real(rhs);
}

ScalarValue div_values(const ScalarValue& lhs, const ScalarValue& rhs) {
  if (std::holds_alternative<std::complex<double>>(lhs) ||
      std::holds_alternative<std::complex<double>>(rhs)) {
    return scalar_to_complex(lhs) / scalar_to_complex(rhs);
  }
  return scalar_to_real(lhs) / scalar_to_real(rhs);
}

ScalarValue pow_values(const ScalarValue& lhs, const ScalarValue& rhs) {
  if (std::holds_alternative<std::complex<double>>(lhs) ||
      std::holds_alternative<std::complex<double>>(rhs)) {
    return std::pow(scalar_to_complex(lhs), scalar_to_complex(rhs));
  }
  return std::pow(scalar_to_real(lhs), scalar_to_real(rhs));
}

Value value_from_scalar(const ScalarValue& value) {
  if (const auto* real = std::get_if<double>(&value)) {
    return *real;
  }
  if (const auto* boolean = std::get_if<bool>(&value)) {
    return *boolean;
  }
  return std::get<std::complex<double>>(value);
}

bool finite_complex(const std::complex<double>& value) {
  return std::isfinite(value.real()) && std::isfinite(value.imag());
}

bool finite_value(const Value& value) {
  if (std::holds_alternative<std::monostate>(value)) return true;
  if (const auto* real = std::get_if<double>(&value)) return std::isfinite(*real);
  if (const auto* complex = std::get_if<std::complex<double>>(&value)) {
    return finite_complex(*complex);
  }
  if (const auto* vector = std::get_if<Eigen::VectorXd>(&value)) return vector->allFinite();
  if (const auto* matrix = std::get_if<Eigen::MatrixXd>(&value)) return matrix->allFinite();
  if (const auto* vector = std::get_if<Eigen::VectorXcd>(&value)) return vector->allFinite();
  if (const auto* matrix = std::get_if<Eigen::MatrixXcd>(&value)) return matrix->allFinite();
  if (const auto* diagonalization = std::get_if<DiagonalizationValue>(&value)) {
    return diagonalization->singular_values.allFinite() &&
           diagonalization->eigenvalues.allFinite() &&
           diagonalization->u_real.allFinite() &&
           diagonalization->v_real.allFinite() &&
           diagonalization->u_complex.allFinite() &&
           diagonalization->v_complex.allFinite();
  }
  return true;
}

PointResult invalid_physics_result(const std::string& reason) {
  PointResult result;
  result.status = PointStatus::Ok;
  result.valid = false;
  result.failure_reason = reason;
  return result;
}

Eigen::MatrixXcd matrix_to_complex(const Value& value, const std::string& name) {
  if (const auto* matrix = std::get_if<Eigen::MatrixXcd>(&value)) {
    return *matrix;
  }
  if (const auto* matrix = std::get_if<Eigen::MatrixXd>(&value)) {
    return matrix->cast<std::complex<double>>();
  }
  throw std::runtime_error("Mixing matrix input '" + name + "' is not a matrix.");
}

DiagonalizationValue takagi_factorization(const Eigen::MatrixXcd& matrix) {
  if (matrix.rows() != matrix.cols()) {
    throw std::runtime_error("Takagi diagonalization requires a square matrix.");
  }
  const double symmetry_tolerance = 1.0e-8 * std::max(1.0, matrix.norm());
  if ((matrix - matrix.transpose()).norm() > symmetry_tolerance) {
    throw std::runtime_error("Takagi diagonalization requires a complex symmetric matrix.");
  }

  const Eigen::Index n = matrix.rows();
  const Eigen::MatrixXd real_part = matrix.real();
  const Eigen::MatrixXd imag_part = matrix.imag();
  Eigen::MatrixXd doubled(2 * n, 2 * n);
  doubled.topLeftCorner(n, n) = real_part;
  doubled.topRightCorner(n, n) = -imag_part;
  doubled.bottomLeftCorner(n, n) = -imag_part;
  doubled.bottomRightCorner(n, n) = -real_part;

  Eigen::SelfAdjointEigenSolver<Eigen::MatrixXd> solver(doubled);
  if (solver.info() != Eigen::Success) {
    throw std::runtime_error("Takagi diagonalization failed.");
  }

  DiagonalizationValue diag;
  diag.singular_values.resize(n);
  diag.u_complex.resize(n, n);
  for (Eigen::Index column = 0; column < n; ++column) {
    const Eigen::Index eigen_index = 2 * n - 1 - column;
    diag.singular_values[column] = std::max(0.0, solver.eigenvalues()[eigen_index]);
    const Eigen::VectorXd packed = solver.eigenvectors().col(eigen_index);
    Eigen::VectorXcd unitary_column(n);
    for (Eigen::Index row = 0; row < n; ++row) {
      unitary_column[row] = {packed[row], packed[row + n]};
    }
    const double norm = unitary_column.norm();
    if (norm == 0.0 || !std::isfinite(norm)) {
      throw std::runtime_error("Takagi diagonalization produced a zero-norm vector.");
    }
    diag.u_complex.col(column) = unitary_column / norm;
  }
  // For Takagi, u_complex is the Takagi unitary U satisfying U^T M U = D.
  // v_complex is populated with conj(U) so generic matrix consumers still see
  // a complete pair of unitary factors.
  diag.v_complex = diag.u_complex.conjugate();
  return diag;
}

}  // namespace

CompiledModel::CompiledModel(CompiledModelPlan plan) : plan_(std::move(plan)) {
  for (std::size_t i = 0; i < plan_.nodes.size(); ++i) {
    name_to_index_.emplace(plan_.nodes[i].name, i);
  }
  for (const auto& name : plan_.evaluation_order) {
    evaluation_order_indices_.push_back(require_index(name));
  }
}

std::size_t CompiledModel::require_index(const std::string& name) const {
  const auto it = name_to_index_.find(name);
  if (it == name_to_index_.end()) {
    throw std::runtime_error("Unknown node in compiled model: " + name);
  }
  return it->second;
}

PointResult CompiledModel::evaluate(
    const std::unordered_map<std::string, Value>& inputs) const {
  PointResult result;
  std::vector<Value> cache(plan_.nodes.size());
  std::vector<bool> computed(plan_.nodes.size(), false);

  auto resolver = [&](const std::string& name) -> const Value& {
    const auto index = require_index(name);
    if (!computed[index]) {
      throw std::runtime_error("Attempted to resolve unevaluated node: " + name);
    }
    return cache[index];
  };

  auto evaluate_program = [&](const Program& program) -> ScalarValue {
    std::vector<ScalarValue> stack;
    stack.reserve(program.instructions.size());

    for (const auto& instruction : program.instructions) {
      if (instruction.op == "push_real") {
        stack.emplace_back(instruction.value);
      } else if (instruction.op == "push_bool") {
        stack.emplace_back(instruction.boolean);
      } else if (instruction.op == "push_complex") {
        stack.emplace_back(std::complex<double>(instruction.re, instruction.im));
      } else if (instruction.op == "load") {
        stack.emplace_back(scalar_from_value(resolver(instruction.name)));
      } else if (instruction.op == "neg") {
        const auto rhs = stack.back();
        stack.back() = mul_values(ScalarValue{-1.0}, rhs);
      } else if (instruction.op == "not") {
        const auto rhs = stack.back();
        stack.back() = !scalar_to_bool(rhs);
      } else if (instruction.op == "add") {
        const auto rhs = stack.back();
        stack.pop_back();
        const auto lhs = stack.back();
        stack.back() = add_values(lhs, rhs);
      } else if (instruction.op == "sub") {
        const auto rhs = stack.back();
        stack.pop_back();
        const auto lhs = stack.back();
        stack.back() = sub_values(lhs, rhs);
      } else if (instruction.op == "mul") {
        const auto rhs = stack.back();
        stack.pop_back();
        const auto lhs = stack.back();
        stack.back() = mul_values(lhs, rhs);
      } else if (instruction.op == "div") {
        const auto rhs = stack.back();
        stack.pop_back();
        const auto lhs = stack.back();
        stack.back() = div_values(lhs, rhs);
      } else if (instruction.op == "pow") {
        const auto rhs = stack.back();
        stack.pop_back();
        const auto lhs = stack.back();
        stack.back() = pow_values(lhs, rhs);
      } else if (instruction.op == "and") {
        const bool rhs = scalar_to_bool(stack.back());
        stack.pop_back();
        const bool lhs = scalar_to_bool(stack.back());
        stack.back() = lhs && rhs;
      } else if (instruction.op == "or") {
        const bool rhs = scalar_to_bool(stack.back());
        stack.pop_back();
        const bool lhs = scalar_to_bool(stack.back());
        stack.back() = lhs || rhs;
      } else if (instruction.op == "cmp_lt") {
        const auto rhs = scalar_to_real(stack.back());
        stack.pop_back();
        const auto lhs = scalar_to_real(stack.back());
        stack.back() = lhs < rhs;
      } else if (instruction.op == "cmp_le") {
        const auto rhs = scalar_to_real(stack.back());
        stack.pop_back();
        const auto lhs = scalar_to_real(stack.back());
        stack.back() = lhs <= rhs;
      } else if (instruction.op == "cmp_gt") {
        const auto rhs = scalar_to_real(stack.back());
        stack.pop_back();
        const auto lhs = scalar_to_real(stack.back());
        stack.back() = lhs > rhs;
      } else if (instruction.op == "cmp_ge") {
        const auto rhs = scalar_to_real(stack.back());
        stack.pop_back();
        const auto lhs = scalar_to_real(stack.back());
        stack.back() = lhs >= rhs;
      } else if (instruction.op == "cmp_eq") {
        const auto rhs = scalar_to_real(stack.back());
        stack.pop_back();
        const auto lhs = scalar_to_real(stack.back());
        stack.back() = lhs == rhs;
      } else if (instruction.op == "cmp_ne") {
        const auto rhs = scalar_to_real(stack.back());
        stack.pop_back();
        const auto lhs = scalar_to_real(stack.back());
        stack.back() = lhs != rhs;
      } else if (instruction.op == "call") {
        std::vector<ScalarValue> args(static_cast<std::size_t>(instruction.argc));
        for (int i = instruction.argc - 1; i >= 0; --i) {
          args[static_cast<std::size_t>(i)] = stack.back();
          stack.pop_back();
        }
        stack.emplace_back(execute_builtin_function(instruction.name, args));
      } else {
        throw std::runtime_error("Unknown instruction op: " + instruction.op);
      }
    }

    if (stack.size() != 1U) {
      throw std::runtime_error("Expression evaluation left an invalid stack state.");
    }

    return stack.back();
  };

  try {
    for (const auto node_index : evaluation_order_indices_) {
      const auto& node = plan_.nodes[node_index];

      switch (node.kind) {
        case NodeKind::ExternalParameter: {
          const auto it = inputs.find(node.name);
          if (it != inputs.end()) {
            cache[node_index] = it->second;
          } else if (node.literal.has_value()) {
            const auto& literal = *node.literal;
            if (literal.type == ValueType::Real) {
              cache[node_index] = literal.real_value;
            } else if (literal.type == ValueType::Complex) {
              cache[node_index] = literal.complex_value;
            } else if (literal.type == ValueType::Bool) {
              cache[node_index] = literal.bool_value;
            } else if (literal.type == ValueType::String) {
              cache[node_index] = literal.string_value;
            } else {
              result.status = PointStatus::MissingInput;
              result.valid = false;
              result.failure_reason = "Missing external parameter: " + node.name;
              return result;
            }
          } else {
            result.status = PointStatus::MissingInput;
            result.valid = false;
            result.failure_reason = "Missing external parameter: " + node.name;
            return result;
          }
          break;
        }

        case NodeKind::Constant: {
          const auto& literal = *node.literal;
          if (literal.type == ValueType::Real) {
            cache[node_index] = literal.real_value;
          } else if (literal.type == ValueType::Complex) {
            cache[node_index] = literal.complex_value;
          } else if (literal.type == ValueType::Bool) {
            cache[node_index] = literal.bool_value;
          } else if (literal.type == ValueType::String) {
            cache[node_index] = literal.string_value;
          }
          break;
        }

        case NodeKind::Derived:
        case NodeKind::Observable: {
          if (node.program.has_value()) {
            cache[node_index] = value_from_scalar(evaluate_program(*node.program));
          } else if (node.plugin_call.has_value()) {
            cache[node_index] = execute_plugin_call(*node.plugin_call, resolver);
          } else if (node.projection.has_value()) {
            const auto& projection = *node.projection;
            const auto& source_value = resolver(projection.source);
            if (const auto* diag = std::get_if<DiagonalizationValue>(&source_value)) {
              if (projection.quantity == "singular_values") {
                cache[node_index] = projection.index >= 0
                                        ? Value{diag->singular_values[projection.index]}
                                        : Value{diag->singular_values};
              } else if (projection.quantity == "eigenvalues") {
                cache[node_index] = projection.index >= 0
                                        ? Value{diag->eigenvalues[projection.index]}
                                        : Value{diag->eigenvalues};
              } else if (projection.quantity == "u_real") {
                cache[node_index] = projection.row >= 0 && projection.col >= 0
                                        ? Value{diag->u_real(projection.row, projection.col)}
                                        : Value{diag->u_real};
              } else if (projection.quantity == "u_complex") {
                cache[node_index] = projection.row >= 0 && projection.col >= 0
                                        ? Value{diag->u_complex(projection.row, projection.col)}
                                        : Value{diag->u_complex};
              } else if (projection.quantity == "v_real") {
                cache[node_index] = projection.row >= 0 && projection.col >= 0
                                        ? Value{diag->v_real(projection.row, projection.col)}
                                        : Value{diag->v_real};
              } else if (projection.quantity == "v_complex") {
                cache[node_index] = projection.row >= 0 && projection.col >= 0
                                        ? Value{diag->v_complex(projection.row, projection.col)}
                                        : Value{diag->v_complex};
              } else {
                throw std::runtime_error("Unknown projection quantity: " +
                                         projection.quantity);
              }
            } else if (const auto* matrix = std::get_if<Eigen::MatrixXcd>(&source_value)) {
              if (projection.quantity != "matrix" && projection.quantity != "value") {
                throw std::runtime_error("Unknown complex-matrix projection quantity: " +
                                         projection.quantity);
              }
              cache[node_index] = projection.row >= 0 && projection.col >= 0
                                      ? Value{(*matrix)(projection.row, projection.col)}
                                      : Value{*matrix};
            } else if (const auto* matrix = std::get_if<Eigen::MatrixXd>(&source_value)) {
              if (projection.quantity != "matrix" && projection.quantity != "value") {
                throw std::runtime_error("Unknown real-matrix projection quantity: " +
                                         projection.quantity);
              }
              cache[node_index] = projection.row >= 0 && projection.col >= 0
                                      ? Value{(*matrix)(projection.row, projection.col)}
                                      : Value{*matrix};
            } else if (const auto* vector = std::get_if<Eigen::VectorXd>(&source_value)) {
              if (projection.quantity != "vector" && projection.quantity != "value") {
                throw std::runtime_error("Unknown real-vector projection quantity: " +
                                         projection.quantity);
              }
              cache[node_index] = projection.index >= 0
                                      ? Value{(*vector)[projection.index]}
                                      : Value{*vector};
            } else if (const auto* vector = std::get_if<Eigen::VectorXcd>(&source_value)) {
              if (projection.quantity != "vector" && projection.quantity != "value") {
                throw std::runtime_error("Unknown complex-vector projection quantity: " +
                                         projection.quantity);
              }
              cache[node_index] = projection.index >= 0
                                      ? Value{(*vector)[projection.index]}
                                      : Value{*vector};
            } else {
              throw std::runtime_error("Projection source '" + projection.source +
                                       "' is not projectable.");
            }
          }
          break;
        }

        case NodeKind::TheoryCheck: {
          bool passes = false;
          if (node.program.has_value()) {
            passes = scalar_to_bool(evaluate_program(*node.program));
          } else if (node.plugin_call.has_value()) {
            passes = scalar_to_bool(scalar_from_value(execute_plugin_call(*node.plugin_call, resolver)));
          } else {
            throw std::runtime_error("Theory check node is missing both program and plugin call.");
          }
          cache[node_index] = passes;
          if (!passes) {
            if (node.fatal) {
              return invalid_physics_result(
                  "theory_check_failed: " +
                  (node.failure_message.empty() ? node.name : node.failure_message));
            }
            result.flags.push_back(node.name);
          }
          break;
        }

        case NodeKind::Matrix: {
          const auto& matrix = *node.matrix;
          if (node.value_type == ValueType::ComplexMatrix) {
            Eigen::MatrixXcd values(matrix.rows, matrix.cols);
            for (int i = 0; i < matrix.rows; ++i) {
              for (int j = 0; j < matrix.cols; ++j) {
                const auto cell_index = static_cast<std::size_t>(i * matrix.cols + j);
                values(i, j) = scalar_to_complex(evaluate_program(matrix.cells[cell_index]));
              }
            }
            cache[node_index] = values;
          } else {
            Eigen::MatrixXd values(matrix.rows, matrix.cols);
            for (int i = 0; i < matrix.rows; ++i) {
              for (int j = 0; j < matrix.cols; ++j) {
                const auto cell_index = static_cast<std::size_t>(i * matrix.cols + j);
                values(i, j) = scalar_to_real(evaluate_program(matrix.cells[cell_index]));
              }
            }
            cache[node_index] = values;
          }
          break;
        }

        case NodeKind::Diagonalization: {
          const auto& spec = *node.diagonalization;
          DiagonalizationValue diag;
          const auto& input = resolver(spec.input);
          if (spec.method == "svd") {
            if (const auto* complex_matrix = std::get_if<Eigen::MatrixXcd>(&input)) {
              Eigen::JacobiSVD<Eigen::MatrixXcd> svd(
                  *complex_matrix, Eigen::ComputeFullU | Eigen::ComputeFullV);
              diag.singular_values = svd.singularValues();
              diag.u_complex = svd.matrixU();
              diag.v_complex = svd.matrixV();
            } else {
              const auto& real_matrix = std::get<Eigen::MatrixXd>(input);
              Eigen::JacobiSVD<Eigen::MatrixXd> svd(
                  real_matrix, Eigen::ComputeFullU | Eigen::ComputeFullV);
              diag.singular_values = svd.singularValues();
              diag.u_real = svd.matrixU();
              diag.v_real = svd.matrixV();
            }
          } else if (spec.method == "svd_complex") {
            const auto& matrix = std::get<Eigen::MatrixXcd>(input);
            Eigen::JacobiSVD<Eigen::MatrixXcd> svd(
                matrix, Eigen::ComputeFullU | Eigen::ComputeFullV);
            diag.singular_values = svd.singularValues();
            diag.u_complex = svd.matrixU();
            diag.v_complex = svd.matrixV();
          } else if (spec.method == "svd_real") {
            const auto& matrix = std::get<Eigen::MatrixXd>(input);
            Eigen::JacobiSVD<Eigen::MatrixXd> svd(
                matrix, Eigen::ComputeFullU | Eigen::ComputeFullV);
            diag.singular_values = svd.singularValues();
            diag.u_real = svd.matrixU();
            diag.v_real = svd.matrixV();
          } else if (spec.method == "takagi") {
            const auto& matrix = std::get<Eigen::MatrixXcd>(input);
            diag = takagi_factorization(matrix);
          } else if (spec.method == "hermitian_eigh") {
            if (const auto* complex_matrix = std::get_if<Eigen::MatrixXcd>(&input)) {
              Eigen::SelfAdjointEigenSolver<Eigen::MatrixXcd> solver(*complex_matrix);
              diag.eigenvalues = solver.eigenvalues();
              diag.u_complex = solver.eigenvectors();
            } else {
              const auto& real_matrix = std::get<Eigen::MatrixXd>(input);
              Eigen::SelfAdjointEigenSolver<Eigen::MatrixXd> solver(real_matrix);
              diag.eigenvalues = solver.eigenvalues();
              diag.u_real = solver.eigenvectors();
            }
          } else if (spec.method == "self_adjoint_eigen") {
            const auto& matrix = std::get<Eigen::MatrixXd>(input);
            Eigen::SelfAdjointEigenSolver<Eigen::MatrixXd> solver(matrix);
            diag.eigenvalues = solver.eigenvalues();
            diag.u_real = solver.eigenvectors();
          } else if (spec.method == "self_adjoint_eigen_complex") {
            const auto& matrix = std::get<Eigen::MatrixXcd>(input);
            Eigen::SelfAdjointEigenSolver<Eigen::MatrixXcd> solver(matrix);
            diag.eigenvalues = solver.eigenvalues();
            diag.u_complex = solver.eigenvectors();
          } else {
            throw std::runtime_error("Unsupported diagonalization method: " +
                                     spec.method);
          }
          cache[node_index] = std::move(diag);
          break;
        }

        case NodeKind::MixingMatrix: {
          const auto& spec = *node.mixing_matrix;
          Eigen::MatrixXcd left;
          Eigen::MatrixXcd right;
          if (spec.left == "identity") {
            right = matrix_to_complex(resolver(spec.right), spec.right);
            left = Eigen::MatrixXcd::Identity(right.rows(), right.rows());
          } else if (spec.right == "identity") {
            left = matrix_to_complex(resolver(spec.left), spec.left);
            right = Eigen::MatrixXcd::Identity(left.rows(), left.rows());
          } else {
            left = matrix_to_complex(resolver(spec.left), spec.left);
            right = matrix_to_complex(resolver(spec.right), spec.right);
          }

          if (spec.convention == "U_left_dagger_U_right") {
            if (left.rows() != right.rows()) {
              throw std::runtime_error("Mixing matrix '" + node.name +
                                       "' has incompatible left/right dimensions.");
            }
            cache[node_index] = Eigen::MatrixXcd((left.adjoint() * right).eval());
          } else if (spec.convention == "U_left_U_right_dagger") {
            if (left.cols() != right.cols()) {
              throw std::runtime_error("Mixing matrix '" + node.name +
                                       "' has incompatible left/right dimensions.");
            }
            cache[node_index] = Eigen::MatrixXcd((left * right.adjoint()).eval());
          } else {
            throw std::runtime_error("Unsupported mixing matrix convention: " +
                                     spec.convention);
          }
          break;
        }

        case NodeKind::Constraint: {
          const double nll = evaluate_constraint(*node.constraint, resolver);
          if (!std::isfinite(nll)) {
            return invalid_physics_result("likelihood_input_invalid: " + node.name);
          }
          cache[node_index] = nll;
          result.likelihood_terms.emplace(node.name, nll);
          result.total_nll += nll;
          if (!std::isfinite(result.total_nll)) {
            return invalid_physics_result("non_finite_likelihood_sum");
          }
          break;
        }

        case NodeKind::Output: {
          const auto& output = *node.output;
          cache[node_index] = resolver(output.source);
          result.outputs.emplace(output.label, resolver(output.source));
          break;
        }

        case NodeKind::Function: {
          cache[node_index] = std::monostate{};
          break;
        }
      }

      if (!finite_value(cache[node_index])) {
        return invalid_physics_result("non_finite_node: " + node.name);
      }
      computed[node_index] = true;
    }
  } catch (const std::runtime_error& error) {
    result.status = PointStatus::EvaluationError;
    result.valid = false;
    result.failure_reason = error.what();
    return result;
  } catch (const std::exception& error) {
    result.status = PointStatus::NumericalError;
    result.valid = false;
    result.failure_reason = error.what();
    return result;
  }

  result.status = PointStatus::Ok;
  result.valid = true;
  return result;
}

}  // namespace bsm::core
