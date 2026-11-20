#!/usr/bin/env bash
# 截图归档：cap.sh <名称> [输出目录]
set -u
ADB="${ADB:-adb}"
NAME="${1:?usage: cap.sh <name> [dir]}"
DIR="${2:-evidence/screens-native}"
mkdir -p "$DIR"
TS=$(date +%H%M%S)
FILE="$DIR/${NAME}-${TS}.png"
$ADB exec-out screencap -p > "$FILE"
echo "$FILE"
