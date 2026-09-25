/* makeMovie GAME_DIR LEVEL SEED TICKS [PLAN]: a test movie for the tester, one input string per line
 * ("|K|LRUDSC|"). The prince plays the plan first (explore.c's "x y shift" lines, reaching deep into the level),
 * then random held inputs for TICKS ticks: directions, Shift and Ctrl held for a few ticks at a time, and a key
 * press after a death so the level restarts. Deterministic for given arguments. Built with SDLPoP2's core only to
 * know when the prince is dead (the movie itself is just inputs). */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <core.h>

extern uint8_t Kid[];   /* (the prince's record: +0x11 alive, < 0 while alive) */

static uint32_t rng;
static uint32_t rnd(void) { rng = rng * 1103515245u + 12345u; return rng >> 16; }
static void emit(const pop2_input *in)
{
	printf("|%c|%c%c%c%c%c%c|\n", in->keystroke ? 'K' : '.', in->x < 0 ? 'L' : '.', in->x > 0 ? 'R' : '.', in->y < 0 ? 'U' : '.',
	       in->y > 0 ? 'D' : '.', in->shift == 1 ? 'S' : '.', in->shift == 2 ? 'C' : '.');
}
int main(int argc, char **argv)
{
	if (argc < 5) { fprintf(stderr, "usage: makeMovie GAME_DIR LEVEL SEED TICKS [PLAN]\n"); return 2; }
	if (!pop2_init(argv[1])) { fprintf(stderr, "cannot load the game from %s\n", argv[1]); return 1; }
	int level = atoi(argv[2]); uint32_t seed = (uint32_t)strtoul(argv[3], NULL, 10); int ticks = atoi(argv[4]);
	pop2_new_game(level, seed); rng = seed ^ 0x9E3779B9u;
	if (argc > 5) {
		FILE *f = fopen(argv[5], "r"); if (!f) { fprintf(stderr, "cannot read %s\n", argv[5]); return 1; }
		int x, y, s;
		while (fscanf(f, "%d %d %d", &x, &y, &s) == 3) { pop2_input in = {(int8_t)x, (int8_t)y, (uint8_t)s, 0}; emit(&in); pop2_frame(&in); }
		fclose(f);
	}
	pop2_input held = {0}; int hold = 0;
	for (int t = 0; t < ticks; t++) {
		if (hold-- <= 0) {
			uint32_t r = rnd();
			held.x = (int8_t)(r % 3) - 1; held.y = (int8_t)((r / 3) % 3) - 1;
			if (rnd() % 3) held.y = 0;
			held.shift = rnd() % 6 == 0 ? 1 : rnd() % 10 == 0 ? 2 : 0;
			hold = 1 + (int)(rnd() % 12);
		}
		pop2_input in = held;
		in.keystroke = ((int8_t)Kid[0x11] >= 0 && rnd() % 8 == 0) || rnd() % 400 == 0;   /* (after a death: restart; rarely anyway) */
		emit(&in);
		if (pop2_frame(&in) == POP2_QUIT) break;
	}
	return 0;
}
