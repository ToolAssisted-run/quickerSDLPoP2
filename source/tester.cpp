// Plays an input sequence on one core and writes the final state's hash (and optionally every step's), so the
// quickerSDLPoP2 core can be compared with SDLPoP2's own (the oracle). Built once per core (INSTANCE_HEADER).

#include <argparse/argparse.hpp>
#include <chrono>
#include <cstdio>
#include <jaffarCommon/deserializers/contiguous.hpp>
#include <jaffarCommon/exceptions.hpp>
#include <jaffarCommon/file.hpp>
#include <jaffarCommon/hash.hpp>
#include <jaffarCommon/json.hpp>
#include <jaffarCommon/serializers/contiguous.hpp>
#include <jaffarCommon/string.hpp>
#include <string>
#include <vector>
#include INSTANCE_HEADER

static jaffarCommon::hash::hash_t stateHash(const PoP2Instance &e, std::vector<uint8_t> &buffer)
{
  jaffarCommon::serializer::Contiguous s(buffer.data(), buffer.size());
  e.serializeState(s);
  return jaffarCommon::hash::calculateMetroHash(buffer.data(), buffer.size());
}

int main(int argc, char *argv[])
{
  argparse::ArgumentParser program("tester", "1.0");
  program.add_argument("scriptFile").help("Path to the test script file to run.").required();
  program.add_argument("--cycleType")
    .help("Per input: 'Simple' advances only, 'Rerecord' loads / advances / saves, 'Full' loads / advances / saves / advances.")
    .default_value(std::string("Simple"));
  program.add_argument("--hashOutputFile").help("Path to write the final hash to.").default_value(std::string(""));
  program.add_argument("--traceOutputFile").help("Path to write every step's hash to (one per line).").default_value(std::string(""));
  program.add_argument("--gamePath").help("Overrides the script's game path (the folder with PRINCE.EXE).").default_value(std::string(""));

  try { program.parse_args(argc, argv); }
  catch (const std::runtime_error &err) { JAFFAR_THROW_LOGIC("%s\n%s", err.what(), program.help().str().c_str()); }

  const std::string scriptFilePath = program.get<std::string>("scriptFile");
  const std::string hashOutputFile = program.get<std::string>("--hashOutputFile");
  const std::string traceOutputFile = program.get<std::string>("--traceOutputFile");
  const std::string cycleType = program.get<std::string>("--cycleType");
  if (cycleType != "Simple" && cycleType != "Rerecord" && cycleType != "Full") JAFFAR_THROW_LOGIC("Unknown cycle type '%s'\n", cycleType.c_str());

  std::string scriptJsRaw;
  if (jaffarCommon::file::loadStringFromFile(scriptJsRaw, scriptFilePath) == false) JAFFAR_THROW_LOGIC("Could not find/read script file: %s\n", scriptFilePath.c_str());
  auto scriptJs = nlohmann::json::parse(scriptJsRaw);
  if (program.get<std::string>("--gamePath") != "") scriptJs["Game Path"] = program.get<std::string>("--gamePath");
  else if (getenv("POP2_GAME_PATH") != nullptr) scriptJs["Game Path"] = getenv("POP2_GAME_PATH");

  const int startLevel = jaffarCommon::json::getNumber<int>(scriptJs, "Start Level");
  const uint32_t seed = jaffarCommon::json::getNumber<uint32_t>(scriptJs, "Seed");
  const std::string sequenceFilePath = jaffarCommon::json::getString(scriptJs, "Sequence File");

  PoP2Instance e(scriptJs);
  e.initialize();
  e.newGame(startLevel, seed);

  std::string sequenceRaw;
  if (jaffarCommon::file::loadStringFromFile(sequenceRaw, sequenceFilePath) == false) JAFFAR_THROW_LOGIC("Could not find or read from input sequence file: %s\n", sequenceFilePath.c_str());
  std::vector<jaffar::input_t> sequence;
  for (const auto &line : jaffarCommon::string::split(sequenceRaw, '\n'))
  {
    std::string s = line;
    while (!s.empty() && (s.back() == '\r' || s.back() == ' ')) s.pop_back();
    if (!s.empty()) sequence.push_back(e.getInputParser()->parseInputString(s));
  }

  const size_t stateSize = e.getStateSize();
  std::vector<uint8_t> currentState(stateSize), scratch(stateSize);
  {
    jaffarCommon::serializer::Contiguous s(currentState.data(), stateSize);
    e.serializeState(s);
  }

  printf("[] -----------------------------------------\n");
  printf("[] Running Script:          '%s'\n", scriptFilePath.c_str());
  printf("[] Cycle Type:              '%s'\n", cycleType.c_str());
  printf("[] Emulation Core:          '%s'\n", e.getCoreName().c_str());
  printf("[] Start Level / Seed:      %d / %u\n", startLevel, seed);
  printf("[] Sequence Length:         %lu\n", sequence.size());
  printf("[] State Size:              %lu bytes\n", stateSize);
  printf("[] Initial State Hash:      %s\n", jaffarCommon::hash::hashToString(stateHash(e, scratch)).c_str());
  fflush(stdout);

  const bool doDeserialize = cycleType != "Simple", doSerialize = cycleType != "Simple", doPostAdvance = cycleType == "Full";
  std::string trace;

  auto t0 = std::chrono::high_resolution_clock::now();
  for (const auto &input : sequence)
  {
    if (doDeserialize)
    {
      jaffarCommon::deserializer::Contiguous d(currentState.data(), stateSize);
      e.deserializeState(d);
    }
    e.advanceState(input);
    if (doSerialize)
    {
      jaffarCommon::serializer::Contiguous s(currentState.data(), stateSize);
      e.serializeState(s);
    }
    if (doPostAdvance)
    {
      // (an advance whose result is thrown away: the next load must undo it completely)
      e.advanceState(input);
    }
    if (traceOutputFile != "")
    {
      if (doPostAdvance)
      {
        jaffarCommon::deserializer::Contiguous d(currentState.data(), stateSize);
        e.deserializeState(d);
      }
      trace += jaffarCommon::hash::hashToString(stateHash(e, scratch)) + "\n";
    }
  }
  auto tf = std::chrono::high_resolution_clock::now();

  if (doPostAdvance)
  {
    jaffarCommon::deserializer::Contiguous d(currentState.data(), stateSize);
    e.deserializeState(d);
  }

  const double dt = std::chrono::duration_cast<std::chrono::nanoseconds>(tf - t0).count() * 1.0e-9;
  const auto hashString = jaffarCommon::hash::hashToString(stateHash(e, scratch));
  printf("[] Elapsed time:            %3.3fs\n", dt);
  printf("[] Performance:             %.3f inputs / s\n", (double)sequence.size() / dt);
  printf("[] Final Level:             %d\n", e.getLevel());
  printf("[] Final State Hash:        %s\n", hashString.c_str());

  if (hashOutputFile != "") jaffarCommon::file::saveStringToFile(hashString, hashOutputFile.c_str());
  if (traceOutputFile != "") jaffarCommon::file::saveStringToFile(trace, traceOutputFile.c_str());
  return 0;
}
