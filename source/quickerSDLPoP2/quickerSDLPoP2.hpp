#pragma once
// (placeholder: the port comes next)
#include <cstdint>
#include <string>
#include <jaffarCommon/serializers/base.hpp>
#include <jaffarCommon/deserializers/base.hpp>
namespace quicker
{
class QuickerSDLPoP2
{
public:
  bool initialize(const std::string &) { return false; }
  void newGame(int, uint32_t) {}
  void advance(int8_t, int8_t, uint8_t, bool) {}
  void saveState(jaffarCommon::serializer::Base &) const {}
  void loadState(jaffarCommon::deserializer::Base &) {}
  size_t stateSize() const { return 0; }
  int level() const { return 0; }
  void setRandomSeed(uint32_t) {}
};
}
