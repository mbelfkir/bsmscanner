#include "bsm/core/plugins.hpp"

#include <mutex>
#include <stdexcept>
#include <unordered_map>

namespace bsm::core {

namespace {

using FunctionMap = std::unordered_map<std::string, PluginFunction>;
using RegistryMap = std::unordered_map<std::string, FunctionMap>;

struct PluginRegistryState {
  RegistryMap registry;
  std::mutex mutex;
};

PluginRegistryState& registry_state() {
  static PluginRegistryState instance;
  return instance;
}

Value literal_to_value(const LiteralSpec& literal) {
  switch (literal.type) {
    case ValueType::Real:
      return literal.real_value;
    case ValueType::Bool:
      return literal.bool_value;
    case ValueType::Complex:
      return literal.complex_value;
    case ValueType::String:
      return literal.string_value;
    case ValueType::Unknown:
      return std::monostate{};
    default:
      throw std::runtime_error("Unsupported plugin option literal type.");
  }
}

}  // namespace

void register_plugin_function(const std::string& plugin,
                              const std::string& function,
                              PluginFunction callback) {
  auto& state = registry_state();
  std::lock_guard<std::mutex> lock(state.mutex);
  state.registry[plugin][function] = std::move(callback);
}

bool has_plugin_support(std::string_view plugin) noexcept {
  auto& state = registry_state();
  std::lock_guard<std::mutex> lock(state.mutex);
  const auto it = state.registry.find(std::string(plugin));
  return it != state.registry.end() && !it->second.empty();
}

Value execute_plugin_function(std::string_view plugin,
                              const PluginInvocation& invocation) {
  auto& state = registry_state();
  PluginFunction callback;
  {
    std::lock_guard<std::mutex> lock(state.mutex);
    const auto plugin_it = state.registry.find(std::string(plugin));
    if (plugin_it == state.registry.end()) {
      throw std::runtime_error("Unknown plugin: " + std::string(plugin));
    }
    const auto function_it = plugin_it->second.find(invocation.function);
    if (function_it == plugin_it->second.end()) {
      throw std::runtime_error(
          "Plugin '" + std::string(plugin) + "' does not provide function '" +
          invocation.function + "'.");
    }
    callback = function_it->second;
  }
  return callback(invocation);
}

Value execute_plugin_call(const PluginCallSpec& spec,
                          const PluginValueResolver& resolver) {
  PluginInvocation invocation;
  invocation.function = spec.function;
  invocation.output = spec.output;
  invocation.arguments.reserve(spec.bindings.size());
  for (const auto& binding : spec.bindings) {
    invocation.arguments.emplace(binding.argument, resolver(binding.source));
  }
  invocation.options.reserve(spec.options.size());
  for (const auto& option : spec.options) {
    invocation.options.emplace(option.name, literal_to_value(option.value));
  }
  return execute_plugin_function(spec.plugin, invocation);
}

}  // namespace bsm::core
