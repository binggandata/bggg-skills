#!/usr/bin/env python3
"""uiautomator XML 解析小工具。
用法：
  ui.py show <xml>                列出可点击元素
  ui.py tap  <xml> <text|desc>    输出该元素中心坐标（交由 adb input tap）
  ui.py find <xml> <keyword>      模糊查找文本
"""
import sys, re
import xml.etree.ElementTree as ET

def node_attr(n, k):
    return n.get(k) or ""

def match(n, q):
    return q.lower() in (node_attr(n, "text") + " " + node_attr(n, "content-desc")).lower()

def center(bounds):
    m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds or "")
    if not m: return None
    x1,y1,x2,y2 = map(int, m.groups())
    return ((x1+x2)//2, (y1+y2)//2)

def main():
    if len(sys.argv) < 3:
        print(__doc__); return
    cmd, path = sys.argv[1], sys.argv[2]
    root = ET.parse(path).getroot()
    if cmd == "show":
        for n in root.iter("node"):
            if n.get("clickable") == "true":
                c = center(n.get("bounds"))
                label = (n.get("text") or "").strip() or (n.get("content-desc") or "").strip()
                print(f"{n.get('bounds')} {c} {label!r}")
    elif cmd in ("tap", "find"):
        q = sys.argv[3]
        for n in root.iter("node"):
            if match(n, q):
                c = center(n.get("bounds"))
                if cmd == "tap" and c:
                    print(f"{c[0]} {c[1]}"); return
                print(f"{n.get('bounds')} {c} {n.get('text')!r} {n.get('content-desc')!r}")
        if cmd == "tap":
            print("NOT_FOUND"); sys.exit(1)
    else:
        print(__doc__)

if __name__ == "__main__":
    main()
