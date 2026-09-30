#!/bin/bash
# makeStateMovies.sh GAME_DIR BUILD_DIR: test movies that start from states made with SDLPoP2's cheats (tools/makeState):
# every level's end (the transition to the next level, with its story scene choice and level load), and the places
# random play rarely reaches (level 5's bridge and lever, level 13's shadow, level 14's rooms, level 1's sea).
set -e
game=$1; build=$2
cd "$(dirname "$0")"
mkdir -p movies states
make1() {   # NAME LEVEL SEED TICKS OPS...
	name=$1; lv=$2; seed=$3; ticks=$4; shift 4
	$build/makeState "$game" $lv $seed states/$name.state "$@" > /dev/null
	MAKEMOVIE_STATE=states/$name.state $build/makeMovie "$game" $lv $seed $ticks > movies/$name.sol
	cat > $name.test <<EOF
{
  "Game Path": "",
  "Game Version": "1.1",
  "Start Level": $lv,
  "Seed": $seed,
  "Initial State File": "states/$name.state",
  "Sequence File": "movies/$name.sol"
}
EOF
}
for lv in $(seq 1 14); do n=$(printf "%02d" $lv); make1 lvl$n.next $lv $((lv * 1000 + 31)) 1500 w30 next; done
make1 lvl05.onbridge 5 5301 2500 w10 at:10,1,2,-1
make1 lvl05.lever 5 5302 2000 w10 at:3,0,5,0
make1 lvl13.merge 13 13301 2500 w10 at:4,1,3,-1 spirit
make1 lvl14.room3 14 14301 2000 w10 at:3,2,4,0
make1 lvl14.room4 14 14302 2000 w10 at:4,0,2,0
make1 lvl14.room7 14 14303 2500 w10 at:7,2,5,-1 flame hp:12
make1 lvl14.room8 14 14304 2500 w10 at:8,2,5,0 flame hp:12
make1 lvl01.sea16 1 1301 2000 w10 at:16,2,5,0
make1 lvl01.sea19 1 1302 2000 w10 at:19,2,5,0
