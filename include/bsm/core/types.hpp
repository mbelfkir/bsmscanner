#pragma once

#include <Eigen/Core>

#include <complex>
#include <limits>
#include <optional>
#include <string>
#include <variant>
#include <vector>

namespace bsm::core {

enum class NodeKind {
  ExternalParameter,
  Constant,
  Function,
  Derived,
  Matrix,
  Diagonalization,
  MixingMatrix,
  Observable,
  TheoryCheck,
  Constraint,
  Output
};

enum class ValueType {
  Real,
  Complex,
  Bool,
  RealVector,
  RealMatrix,
  ComplexVector,
  ComplexMatrix,
  String,
  Diagonalization,
  Unknown
};

enum class ConstraintKind {
  Gaussian,
  AsymmetricGaussian,
  UpperLimit,
  LowerLimit,
  Interval,
  HardCut,
  TableLookup,
  MultivariateGaussian,
  Custom
};

enum class TableInterpolationKind {
  Linear,
  CubicSpline
};

struct Instruction {
  std::string op;
  std::string name;
  int argc = 0;
  double value = 0.0;
  double re = 0.0;
  double im = 0.0;
  bool boolean = false;
};

struct Program {
  ValueType return_type = ValueType::Real;
  std::vector<Instruction> instructions;
  std::vector<std::string> dependencies;
};

struct LiteralSpec {
  ValueType type = ValueType::Unknown;
  double real_value = 0.0;
  bool bool_value = false;
  std::complex<double> complex_value{0.0, 0.0};
  std::string string_value;
};

struct MatrixProgram {
  int rows = 0;
  int cols = 0;
  std::vector<Program> cells;
};

struct ProjectionSpec {
  std::string source;
  std::string quantity;
  int index = -1;
  int row = -1;
  int col = -1;
};

struct PluginBindingSpec {
  std::string argument;
  std::string source;
};

struct PluginOptionSpec {
  std::string name;
  LiteralSpec value;
};

struct PluginCallSpec {
  std::string plugin;
  std::string function;
  std::string output;
  std::vector<PluginBindingSpec> bindings;
  std::vector<PluginOptionSpec> options;
};

struct DiagonalizationSpec {
  std::string input;
  std::string method;
};

struct MixingMatrixSpec {
  std::string type;
  std::string convention;
  std::string left;
  std::string right;
};

struct ConstraintSpec {
  ConstraintKind kind = ConstraintKind::Gaussian;
  TableInterpolationKind interpolation = TableInterpolationKind::Linear;
  std::string observable;
  std::vector<std::string> observables;
  double mean = 0.0;
  std::vector<double> means;
  double sigma = 1.0;
  double sigma_up = 1.0;
  double sigma_down = 1.0;
  double lower = 0.0;
  double upper = 0.0;
  std::vector<std::vector<double>> covariance;
  std::vector<std::vector<double>> table;
  std::string plugin;
  std::optional<PluginCallSpec> plugin_call;
  double out_of_range_penalty_scale = 0.0;
  double out_of_range_penalty_cap = std::numeric_limits<double>::infinity();
  double in_range_offset = 0.0;
  double quadratic_form_prefactor = 0.5;
  std::vector<double> spline_second_derivatives;
};

struct OutputSpec {
  std::string source;
  std::string label;
};

struct DiagonalizationValue {
  Eigen::VectorXd singular_values;
  Eigen::VectorXd eigenvalues;
  Eigen::MatrixXd u_real;
  Eigen::MatrixXd v_real;
  Eigen::MatrixXcd u_complex;
  Eigen::MatrixXcd v_complex;
};

using ScalarValue = std::variant<double, bool, std::complex<double>>;
using Value = std::variant<std::monostate,
                           double,
                           bool,
                           std::complex<double>,
                           Eigen::VectorXd,
                           Eigen::MatrixXd,
                           Eigen::VectorXcd,
                           Eigen::MatrixXcd,
                           std::string,
                           DiagonalizationValue>;

}  // namespace bsm::core
