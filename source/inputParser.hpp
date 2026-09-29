#pragma once

// Input strings for Prince of Persia 2: "|K|LRUDSC|"
//   K  any key pressed this tick (a dead prince restarts on a key); A in its place: Alt+A, the game's key that restarts
//      the level (from its checkpoint)
//   L R U D  the directions (left and right together, or up and down together, are invalid)
//   S  Shift (careful step, grab, pick up, drink)
//   C  Ctrl (draw the sword, strike; the spirit's spell on level 14). Shift and Ctrl together are invalid.
// A '.' leaves the slot unpressed.

#include <cstdint>
#include <jaffarCommon/exceptions.hpp>
#include <jaffarCommon/json.hpp>
#include <string>

namespace jaffar
{

struct input_t
{
  bool keystroke = false;
  bool restartLevel = false; // Alt+A
  int8_t x = 0;      // -1 left, 1 right
  int8_t y = 0;      // -1 up, 1 down
  uint8_t shift = 0; // 1 Shift, 2 Ctrl
};

class InputParser
{
public:

  InputParser(const nlohmann::json &config) {}

  inline input_t parseInputString(const std::string &s) const
  {
    input_t input;
    if (s.size() != 10 || s[0] != '|' || s[2] != '|' || s[9] != '|') reportBadInputString(s);

    input.restartLevel = s[1] == 'A';
    input.keystroke = input.restartLevel || check(s, 1, 'K');
    const bool l = check(s, 3, 'L'), r = check(s, 4, 'R'), u = check(s, 5, 'U'), d = check(s, 6, 'D');
    const bool sh = check(s, 7, 'S'), c = check(s, 8, 'C');
    if ((l && r) || (u && d) || (sh && c)) reportBadInputString(s);

    input.x = l ? -1 : r ? 1 : 0;
    input.y = u ? -1 : d ? 1 : 0;
    input.shift = c ? 2 : sh ? 1 : 0;
    return input;
  }

private:

  static inline bool check(const std::string &s, size_t i, char c)
  {
    if (s[i] == c) return true;
    if (s[i] != '.') reportBadInputString(s);
    return false;
  }

  static inline void reportBadInputString(const std::string &s) { JAFFAR_THROW_LOGIC("Could not decode input string: '%s'\n", s.c_str()); }
};

} // namespace jaffar
