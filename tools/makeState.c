/* makeState GAME_DIR LEVEL SEED OUT OPS...: a starting state for a test movie (SDLPoP2's pop2_save format), made with
 * SDLPoP2's core and its cheats. OPS, in order:
 *   wN            N ticks with no input
 *   next          the level ends (DS:5CEC = the next level, as Alt+N skips): the next tick loads it
 *   at:R,ROW,COL,DIR  the prince stands in room R at a tile (DIR 0 right, -1 left), as SDLPoP2's look + teleport cheats
 *   spirit / flame    the prince leaves his body as the shadow / the flame (SDLPoP2's H / B cheats)
 *   hp:N          the prince's hit points and maximum */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <core.h>
#include <types.h>
#include <globals.h>

static void ticks(int n) { pop2_input z = {0}; for (int i = 0; i < n; i++) pop2_frame(&z); }
int main(int argc, char **argv)
{
	if (argc < 5) { fprintf(stderr, "usage: makeState GAME_DIR LEVEL SEED OUT OPS...\n"); return 2; }
	if (!pop2_init(argv[1])) { fprintf(stderr, "cannot load the game from %s\n", argv[1]); return 1; }
	int level = atoi(argv[2]);
	pop2_new_game(level, (uint32_t)strtoul(argv[3], NULL, 10));
	for (int a = 5; a < argc; a++) {
		const char *op = argv[a];
		if (op[0] == 'w') ticks(atoi(op + 1));
		else if (!strcmp(op, "next")) counter_5cec = (uint16_t)(pop2_level() + 1);
		else if (!strncmp(op, "at:", 3)) {
			int r, row, col, dir; sscanf(op + 3, "%d,%d,%d,%d", &r, &row, &col, &dir);
			cheat_view = (uint8_t)r; for (int i = 0; i < 40 && drawn_room != r; i++) ticks(1);
			Kid.curr_row = (int8_t)row; Kid.curr_col = (int8_t)col; Kid.x = col_x_left[col] + 0xE; Kid.direction = (int8_t)dir;
			loadkid(); char_y_to_floor(); Char.fall_x = Char.fall_y = 0; Kid = Char;
			if (Kid.room != r) { cheat_looking = 1; loadkid(); cheat_teleport(); Kid = Char; }
		}
		else if (!strcmp(op, "spirit") || !strcmp(op, "flame")) { loadkid(); cheat_leave_body(op[0] == 'f'); Kid = Char; }
		else if (!strncmp(op, "hp:", 3)) { Kid.f12 = Kid.f13 = (uint8_t)atoi(op + 3); }
		else { fprintf(stderr, "unknown op %s\n", op); return 2; }
	}
	size_t n = pop2_state_size(); void *b = malloc(n); pop2_save(b);
	FILE *f = fopen(argv[4], "wb"); if (!f || fwrite(b, 1, n, f) != n) { fprintf(stderr, "cannot write %s\n", argv[4]); return 1; }
	fclose(f); free(b);
	printf("%s: level %d, room %d, row %d, col %d\n", argv[4], pop2_level(), Kid.room, Kid.curr_row, Kid.curr_col);
	return 0;
}
