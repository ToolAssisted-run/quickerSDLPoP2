#!/bin/bash
# run_test.sh QUICKER ORACLE SCRIPT [TESTER ARGS]: plays SCRIPT on both cores and compares the final hashes.
set -e
quicker=$1; oracle=$2; script=$3; shift 3
tmp=$(mktemp -d)
"$quicker" "$script" --hashOutputFile "$tmp/quicker.hash" "$@"
"$oracle" "$script" --hashOutputFile "$tmp/oracle.hash" "$@"
a=$(cat "$tmp/quicker.hash"); b=$(cat "$tmp/oracle.hash"); rm -rf "$tmp"
if [ "$a" = "$b" ]; then echo "[] Test Passed"; exit 0; fi
echo "[] Test Failed: quickerSDLPoP2 $a, SDLPoP2 $b"; exit 1
