#pragma once

// What both cores offer the tester (and JaffarPlus): the original SDLPoP2 core (the oracle) and quickerSDLPoP2.

#include "inputParser.hpp"
#include <jaffarCommon/exceptions.hpp>
#include <jaffarCommon/deserializers/base.hpp>
#include <jaffarCommon/hash.hpp>
#include <jaffarCommon/json.hpp>
#include <jaffarCommon/serializers/base.hpp>
#include <memory>
#include <string>

class PoP2InstanceBase
{
public:

  PoP2InstanceBase(const nlohmann::json &config)
  {
    _gamePath    = jaffarCommon::json::getString(config, "Game Path");
    // "Game Version" (optional): the DOS release to play, "1.1", "1.0" or "IR" (the initial release); "Auto" (the
    // default) plays the release the game's files are
    if (config.contains("Game Version"))
    {
      const auto v = jaffarCommon::json::getString(config, "Game Version");
      if (v == "Auto") _gameVersion = -1;
      else if (v == "1.1") _gameVersion = 0;
      else if (v == "1.0") _gameVersion = 1;
      else if (v == "IR") _gameVersion = 2;
      else JAFFAR_THROW_LOGIC("Game Version '%s' is not Auto, 1.1, 1.0 or IR\n", v.c_str());
    }
    _inputParser = std::make_unique<jaffar::InputParser>(config);
  }

  virtual ~PoP2InstanceBase() = default;

  // Loads the game's files (PRINCE.EXE, SEQUENCE.DAT, the DATs) from the game path
  virtual void initialize() = 0;

  // A new game at the given level (1: the start; 2..14 as the DOS game's LEVELn) with the given random seed
  virtual void newGame(const int level, const uint32_t seed) = 0;

  // One game tick with the given input
  virtual void advanceState(const jaffar::input_t &input) = 0;

  virtual void serializeState(jaffarCommon::serializer::Base &serializer) const = 0;
  virtual void deserializeState(jaffarCommon::deserializer::Base &deserializer) = 0;
  virtual size_t getStateSize() const = 0;

  // The level being played and the random seed (for configurations)
  virtual int getLevel() const = 0;
  virtual void setRNGValue(const uint32_t seed) = 0;

  virtual std::string getCoreName() const = 0;

  inline jaffar::InputParser *getInputParser() const { return _inputParser.get(); }

protected:

  std::string _gamePath;
  int _gameVersion = -1; // POP2_VER_*: -1 the game files' own, 0 1.1, 1 1.0, 2 the initial release

private:

  std::unique_ptr<jaffar::InputParser> _inputParser;
};
