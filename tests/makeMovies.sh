#!/bin/bash
# makeMovies.sh GAME_DIR BUILD_DIR EXPLORE: regenerates the test movies and their scripts (movies/, *.test) with the
# oracle. EXPLORE is SDLPoP2's explorer (tools/explore). Two movies per level: "explore" (a Go-Explore plan deep
# into the level, then random play) and "random" (random play from the start, with deaths and restarts).
set -e
game=$1; build=$2; explore=$3
cd "$(dirname "$0")"
mkdir -p movies
for lv in $(seq 1 14); do
	n=$(printf "%02d" $lv); seed=$((lv * 1000 + 7))
	$explore "$game" $lv $seed 200000 movies/lvl$n.plan > /dev/null
	$build/makeMovie "$game" $lv $seed 2000 movies/lvl$n.plan > movies/lvl$n.explore.sol
	$build/makeMovie "$game" $lv $((seed + 1)) 6000 > movies/lvl$n.random.sol
	rm -f movies/lvl$n.plan
	for kind in explore random; do
		s=$seed; [ $kind = random ] && s=$((seed + 1))
		cat > lvl$n.$kind.test <<EOF
{
  "Game Path": "",
  "Game Version": "1.1",
  "Start Level": $lv,
  "Seed": $s,
  "Sequence File": "movies/lvl$n.$kind.sol"
}
EOF
	done
done
