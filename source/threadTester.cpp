// Thread safety: every movie's final hash, played alone, then again with all movies at once on many threads
// (instances created on the main thread, played on workers), then two instances interleaved step by step on one
// thread. All three must agree. Usage: threadTester SCRIPT... (POP2_GAME_PATH names the game's folder)

#include <cstdio>
#include <jaffarCommon/file.hpp>
#include <jaffarCommon/hash.hpp>
#include <jaffarCommon/json.hpp>
#include <jaffarCommon/serializers/contiguous.hpp>
#include <jaffarCommon/string.hpp>
#include <memory>
#include <string>
#include <thread>
#include <vector>
#include "quickerSDLPoP2/quickerInstance.hpp"

struct Movie
{
  nlohmann::json config;
  int level;
  uint32_t seed;
  std::vector<jaffar::input_t> inputs;
};

static jaffarCommon::hash::hash_t hashOf(const PoP2Instance &e)
{
  std::vector<uint8_t> b(e.getStateSize());
  jaffarCommon::serializer::Contiguous s(b.data(), b.size());
  e.serializeState(s);
  return jaffarCommon::hash::calculateMetroHash(b.data(), b.size());
}

int main(int argc, char *argv[])
{
  std::vector<Movie> movies;
  for (int i = 1; i < argc; i++)
  {
    std::string raw;
    if (!jaffarCommon::file::loadStringFromFile(raw, argv[i])) { fprintf(stderr, "cannot read %s\n", argv[i]); return 2; }
    Movie m;
    m.config = nlohmann::json::parse(raw);
    m.config["Game Path"] = getenv("POP2_GAME_PATH") ? getenv("POP2_GAME_PATH") : "";
    m.level = m.config["Start Level"].get<int>();
    m.seed = m.config["Seed"].get<uint32_t>();
    std::string seq;
    if (!jaffarCommon::file::loadStringFromFile(seq, m.config["Sequence File"].get<std::string>())) { fprintf(stderr, "cannot read the movie of %s\n", argv[i]); return 2; }
    PoP2Instance parser(m.config);
    for (const auto &l : jaffarCommon::string::split(seq, '\n'))
      if (l.size() >= 10) m.inputs.push_back(parser.getInputParser()->parseInputString(l.substr(0, 10)));
    movies.push_back(std::move(m));
  }

  // 1. alone
  std::vector<jaffarCommon::hash::hash_t> alone;
  for (auto &m : movies)
  {
    PoP2Instance e(m.config);
    e.initialize();
    e.newGame(m.level, m.seed);
    for (auto &in : m.inputs) e.advanceState(in);
    alone.push_back(hashOf(e));
  }

  // 2. all at once: created here, played on their own threads (each movie twice)
  const size_t n = movies.size() * 2;
  std::vector<std::unique_ptr<PoP2Instance>> instances;
  for (size_t i = 0; i < n; i++)
  {
    instances.push_back(std::make_unique<PoP2Instance>(movies[i % movies.size()].config));
    instances.back()->initialize();
  }
  std::vector<jaffarCommon::hash::hash_t> together(n);
  std::vector<std::thread> threads;
  for (size_t i = 0; i < n; i++)
    threads.emplace_back([&, i]() {
      auto &m = movies[i % movies.size()];
      auto &e = *instances[i];
      e.newGame(m.level, m.seed);
      for (auto &in : m.inputs) e.advanceState(in);
      together[i] = hashOf(e);
    });
  for (auto &t : threads) t.join();

  // 3. two instances interleaved on this thread
  int bad = 0;
  for (size_t i = 0; i + 1 < movies.size(); i += 2)
  {
    PoP2Instance a(movies[i].config), b(movies[i + 1].config);
    a.initialize(); b.initialize();
    a.newGame(movies[i].level, movies[i].seed);
    b.newGame(movies[i + 1].level, movies[i + 1].seed);
    const size_t len = std::max(movies[i].inputs.size(), movies[i + 1].inputs.size());
    for (size_t k = 0; k < len; k++)
    {
      if (k < movies[i].inputs.size()) a.advanceState(movies[i].inputs[k]);
      if (k < movies[i + 1].inputs.size()) b.advanceState(movies[i + 1].inputs[k]);
    }
    if (hashOf(a) != alone[i] || hashOf(b) != alone[i + 1]) { printf("[] interleaved %s / %s: DIFFERS\n", argv[i + 1], argv[i + 2]); bad++; }
  }
  for (size_t i = 0; i < n; i++)
    if (together[i] != alone[i % movies.size()]) { printf("[] threaded %s: DIFFERS\n", argv[1 + i % movies.size()]); bad++; }

  printf("[] %lu movies, %lu threads: %s\n", movies.size(), n, bad ? "FAILED" : "all identical");
  return bad ? 1 : 0;
}
