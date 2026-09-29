#pragma once

// quickerSDLPoP2 behind the common interface. Each instance owns its whole game (no globals): any number of
// instances, on any threads.

#include "../instanceBase.hpp"
#include "quickerSDLPoP2.hpp"
#include <jaffarCommon/exceptions.hpp>

class PoP2Instance final : public PoP2InstanceBase
{
public:

  PoP2Instance(const nlohmann::json &config) : PoP2InstanceBase(config) { _emu = std::make_unique<quicker::QuickerSDLPoP2>(); }

  void initialize() override
  {
    if (_emu->initialize(_gamePath) == false) JAFFAR_THROW_LOGIC("Could not load the game files from '%s'\n", _gamePath.c_str());
  }

  void newGame(const int level, const uint32_t seed) override { _emu->newGame(level, seed); }

  void advanceState(const jaffar::input_t &input) override { _emu->advance(input.x, input.y, input.shift, input.keystroke, input.restartLevel); }

  void serializeState(jaffarCommon::serializer::Base &serializer) const override { _emu->saveState(serializer); }
  void deserializeState(jaffarCommon::deserializer::Base &deserializer) override { _emu->loadState(deserializer); }
  size_t getStateSize() const override { return _emu->stateSize(); }

  int getLevel() const override { return _emu->getLevel(); }
  void setRNGValue(const uint32_t seed) override { _emu->setRandomSeed(seed); }
  std::string getCoreName() const override { return "quickerSDLPoP2"; }

  quicker::QuickerSDLPoP2 *getCore() const { return _emu.get(); }

private:

  std::unique_ptr<quicker::QuickerSDLPoP2> _emu;
};
