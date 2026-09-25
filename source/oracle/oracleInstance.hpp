#pragma once

// The oracle: SDLPoP2's own core (C, one instance per process), behind the common interface.

#include "../instanceBase.hpp"
#include <jaffarCommon/exceptions.hpp>
#include <vector>

extern "C"
{
#include <core.h>
extern uint32_t random_seed;
}

class PoP2Instance final : public PoP2InstanceBase
{
public:

  PoP2Instance(const nlohmann::json &config) : PoP2InstanceBase(config) {}

  void initialize() override
  {
    if (pop2_init(_gamePath.c_str()) == 0) JAFFAR_THROW_LOGIC("Could not load the game files from '%s'\n", _gamePath.c_str());
    _stateSize = pop2_state_size();
  }

  void newGame(const int level, const uint32_t seed) override { pop2_new_game(level, seed); }

  void advanceState(const jaffar::input_t &input) override
  {
    pop2_input in = {input.x, input.y, input.shift, (uint8_t)input.keystroke};
    pop2_frame(&in);
  }

  void serializeState(jaffarCommon::serializer::Base &serializer) const override
  {
    std::vector<uint8_t> buffer(_stateSize);
    pop2_save(buffer.data());
    serializer.push(buffer.data(), _stateSize);
  }

  void deserializeState(jaffarCommon::deserializer::Base &deserializer) override
  {
    std::vector<uint8_t> buffer(_stateSize);
    deserializer.pop(buffer.data(), _stateSize);
    pop2_load(buffer.data());
  }

  size_t getStateSize() const override { return _stateSize; }
  int getLevel() const override { return pop2_level(); }
  void setRNGValue(const uint32_t seed) override { random_seed = seed; }
  std::string getCoreName() const override { return "SDLPoP2"; }

private:

  size_t _stateSize = 0;
};
