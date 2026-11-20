#!/usr/bin/env bash
# bggg-copy-app · ADB 环境检查
set -u
ADB="${ADB:-adb}"
echo "== adb =="; command -v "$ADB" || { echo "adb not found"; exit 1; }
echo "== devices =="; "$ADB" devices
SER="${1:-}"
if [ -n "$SER" ]; then ADB="$ADB -s $SER"; fi
echo "== android =="; $ADB shell getprop ro.build.version.release; $ADB shell getprop ro.product.model
echo "== screen =="; $ADB shell wm size; $ADB shell wm density
echo "== focus =="; $ADB shell dumpsys window | grep -m1 mCurrentFocus
echo "== stayon =="; $ADB shell svc power stayon true
echo "OK"
