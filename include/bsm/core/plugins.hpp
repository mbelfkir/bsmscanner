#pragma once

#include "bsm/core/types.hpp"

#include <functional>
#include <string>
#include <string_view>
#include <unordered_map>

namespace bsm::core {

using PluginArgumentMap = std::unordered_map<std::string, Value>;
using PluginOptionMap = std::unordered_map<std::string, Value>;
using PluginValueResolver = std::function<const Value&(const std::string&)>;

struct PluginInvocation {
  std::string function;
  std::string output;
  PluginArgumentMap arguments;
  PluginOptionMap options;
};

using PluginFunction = std::function<Value(const PluginInvocation&)>;

void register_plugin_function(const std::string& plugin,
                              const std::string& function,
                              PluginFunction callback);
bool has_plugin_support(std::string_view plugin) noexcept;

// Drops every registered plugin function, releasing any captured state
// (notably a Python callback's reference to its underlying object) while
// the caller is still in a position to release it safely. A Python-facing
// registration is exposed to a global registered via `register_plugin_function`,
// which has ordinary static storage duration in this shared library. If left
// to the C++ runtime's own static-destruction order, that registry can be torn
// down after the embedding Python interpreter has already finalized, so
// destroying a captured `py::function` would touch a dead interpreter. Callers
// that embed Python (see pybind_module.cpp) must call this from a module
// destructor that runs before `Py_Finalize`, not rely on this registry's own
// static lifetime.
void clear_plugin_registry() noexcept;
Value execute_plugin_function(std::string_view plugin,
                              const PluginInvocation& invocation);
Value execute_plugin_call(const PluginCallSpec& spec,
                          const PluginValueResolver& resolver);

}  // namespace bsm::core
