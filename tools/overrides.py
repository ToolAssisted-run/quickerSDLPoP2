"""Hand-written parts of quickerSDLPoP2.hpp (see generate.py)."""

# the public interface (inside the class)
API = r'''
  // (the buffers SDLPoP2 allocates once per program are one per instance here)
  ~QuickerSDLPoP2() { free(pop2_reset_state__zero); free(state_hash__buf); }
  QuickerSDLPoP2() = default;
  QuickerSDLPoP2(const QuickerSDLPoP2 &) = delete;
  QuickerSDLPoP2 &operator=(const QuickerSDLPoP2 &) = delete;
  // Loads the game's files from the folder with PRINCE.EXE; false if one is missing
  bool initialize(const std::string &gamePath) { return pop2_init(gamePath.c_str()) != 0; }

  // A new game at the given level (1: the start; 2..14 as the DOS game's LEVELn) with the given random seed
  void newGame(const int lv, const uint32_t seed) { pop2_new_game(lv, seed); }

  // One game tick: x / y -1..1 (left / up negative), shift 1 Shift or 2 Ctrl, keystroke: a key was pressed,
  // restartLevel: the key was Alt+A (the level starts again, from its checkpoint)
  void advance(const int8_t x, const int8_t y, const uint8_t shift, const bool keystroke, const bool restartLevel = false)
  {
    pop2_input in = {x, y, shift, (uint8_t)keystroke, (uint8_t)restartLevel};
    pop2_frame(&in);
  }

  // The savestate: SDLPoP2's pop2_save layout, byte for byte
  size_t stateSize() const { return sizeof(QuickerSDLPoP2State); }
  void saveState(jaffarCommon::serializer::Base &s) const
  {
    const_cast<QuickerSDLPoP2 *>(this)->state_save_pointers();
    s.push(static_cast<const QuickerSDLPoP2State *>(this), sizeof(QuickerSDLPoP2State));
  }
  void loadState(jaffarCommon::deserializer::Base &d)
  {
    d.pop(static_cast<QuickerSDLPoP2State *>(this), sizeof(QuickerSDLPoP2State));
    state_load_pointers();
  }

  int getLevel() const { return level_number; }
  void setRandomSeed(const uint32_t seed) { random_seed = seed; }
'''

# members that are not SDLPoP2 variables, or SDLPoP2 variables of the parts left out
MEMBER_EXTRA = '''
  // the game's files, read once per process: path -> contents (never changed after reading)
  static const std::vector<uint8_t> *shared_file(const char *path)
  {
    static std::mutex m;
    static std::map<std::string, std::unique_ptr<std::vector<uint8_t>>> files;
    std::lock_guard<std::mutex> lock(m);
    auto it = files.find(path);
    if (it != files.end()) return it->second.get();
    FILE *f = fopen(path, "rb");
    std::unique_ptr<std::vector<uint8_t>> b;
    if (f)
    {
      fseek(f, 0, SEEK_END); long n = ftell(f); fseek(f, 0, SEEK_SET);
      b = std::make_unique<std::vector<uint8_t>>((size_t)n);
      if (fread(b->data(), 1, (size_t)n, f) != (size_t)n) b.reset();
      fclose(f);
    }
    return (files[path] = std::move(b)).get();
  }
  const pop2_settings *pop2_settings_game = nullptr;   // settings.c: no frontend settings (the original game)
  uint16_t word_2ba6 = 0;                              // render_palette.c (a scene playing)
'''

# functions replaced by these texts
OVERRIDES = {
    # dat.c: the DAT files are read once per process and shared by every instance (read-only)
    'dat_open': """int dat_open(dat_file *d, const char *path)
{
	const std::vector<uint8_t> *b = shared_file(path);
	if (!b) return 0;
	d->data = const_cast<uint8_t *>(b->data()); d->size = b->size();
	return 1;
}""",
}

# small text changes inside functions (C to C++): [(old, new)] per function
PATCHES = {
    'pop2_reset_state': [('= calloc(1, n)', '= (uint8_t *)calloc(1, n)')],
    'pop2_save': [('state_save(buf)', 'state_save((uint8_t *)buf)')],
    'pop2_load': [('state_load(buf)', 'state_load((const uint8_t *)buf)')],
    'state_hash': [('= malloc(n)', '= (uint8_t *)malloc(n)')],
    # (C++: the goto may not jump over an initialisation: the rest in a block)
    'play_kid_frame': [('\tint8_t o = (int8_t)Kid.opp_index;', '\t{ int8_t o = (int8_t)Kid.opp_index;'), ('done:\n', '\t}\ndone:\n')],
}

# functions left out
DROP = set()

# routines from outside the game logic (SDLPoP2's shell.c) that the logic calls, as the headless core runs them
# (the shell not running: no drawing hooks, no demo, no scene files), and the API's helpers
STUBS = {
    # 15DB:000C: no demo plays in the core
    'demo_timing_check': 'int demo_timing_check(void) { return -2; }',
    # 0823:02BE: the shell not running
    'hotkeys_02be': 'int hotkeys_02be(void) { return hotkeys_02be_core(); }',
    # the status line (shell.c), dispatched to text.c
    'shell_status': """void shell_status(int op)
{
	switch (op) {
	case 0: time_message(); break;
	case 1: status_clear(1); break;
	case 2: status_clear(0); break;
	case 3: status_press_key(); break;
	}
}""",
    # shell.c's core_play_scene -> sh_scene, with no scene files to play: only its state effects
    'core_play_scene': """int core_play_scene(int n)
{
	last_scene = n;
	word_2ba6 = 1;
	if (n != 100 && n < 0x14 && n != 6) checkpoint_free();
	word_2ba6 = 0;
	return 1;
}""",
    # text.c's status line: only the message timers (DS:5CDC / 5CDA) are game state
    'status_clear': 'void status_clear(int reset) { if (reset) word_5cdc = word_5cda = 0; }',
    'status_erase_line': 'void status_erase_line(void) { }',
    'status_message': 'void status_message(const char *s) { (void)s; word_5cdc = word_5cda = 0; }',
    'status_press_key': 'void status_press_key(void) { }',
    'time_message': 'void time_message(void) { status_message(""); }',
    # 169B:123E, the shell not running
    'restart_prompt': 'void restart_prompt(void) { sound_stop_all(); }',
    # state.c's state_save / state_load pointer conversions (curr_room_tiles / attrs as offsets)
    'state_save_pointers': """void state_save_pointers(void)
{
	room_ptr_tiles = !curr_room_tiles ? -1 : curr_room_tiles >= tiles0 && curr_room_tiles < tiles0 + 30 ? (int16_t)(curr_room_tiles - tiles0) : (int16_t)(30 + (curr_room_tiles - (uint8_t *)&level));
	room_ptr_attrs = curr_room_attrs ? (int16_t)((uint8_t *)curr_room_attrs - (uint8_t *)level.attrs) : -1;
}""",
    'state_load_pointers': """void state_load_pointers(void)
{
	curr_room_tiles = room_ptr_tiles < 0 ? NULL : room_ptr_tiles < 30 ? tiles0 + room_ptr_tiles : (uint8_t *)&level + (room_ptr_tiles - 30);
	curr_room_attrs = room_ptr_attrs < 0 ? NULL : (uint32_t *)((uint8_t *)level.attrs + room_ptr_attrs);
}""",
}

# changes to type definitions: [(old, new)]
TYPE_PATCHES = [
    # settings.h's frontend names (keys, buttons, scaling, sound devices) would clash with ncurses' macros (KEY_UP...)
    ('KEY_', 'POP2_KEY_'), ('BUTTON_', 'POP2_BUTTON_'), ('SCALING_', 'POP2_SCALING_'), ('SOUND_DEVICE_', 'POP2_SOUND_DEVICE_'),
    # the savestate keeps 7 bytes of cur_frame (its padding byte is never used): the type is 7 bytes here
    ('typedef struct frame_type {', 'typedef struct __attribute__((packed)) frame_type {'),
]

# changes to whole source files before they are split: {file: [(old, new)]}
FILE_PATCHES = {
    # the program's memory image (640 KB) only ever holds the data segment (DS at 0x3B250, 64 KB): keep that only
    'core': [
        ('static uint8_t ram[655360];', 'static uint8_t ram_ds[0x10000];'),
        ('fread(ram + 0x3B250, 1, 0x27BF, f)', 'fread(ram_ds, 1, 0x27BF, f)'),
        ('glue_load_ds_tables(ram);', 'glue_load_ds_tables(ram_ds);'),
        ('state_load_ds_statics(ram + 0x3B250);', 'state_load_ds_statics(ram_ds);'),
    ],
    'glue': [('ram + 0x3B250', 'ram'), ('ram[0x3B250 + ', 'ram[')],
}
