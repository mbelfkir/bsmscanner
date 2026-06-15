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
Value execute_plugin_function(std::string_view plugin,
                              const PluginInvocation& invocation);
Value execute_plugin_call(const PluginCallSpec& spec,
                          const PluginValueResolver& resolver);

}  // namespace bsm::core
