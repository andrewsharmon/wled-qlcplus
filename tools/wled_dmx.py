#!/usr/bin/env python3
"""Show or switch a WLED board's E1.31 / Art-Net DMX receive mode over HTTP.

Usage: wled_dmx.py [--host 4.3.2.1] [MODE] [--addr 1] [--dss 0] [--uni 1]
  MODE  effects (9), effects15 (8), effect (7), presets (10), pixels (6, RGBW per LED),
        pixels-rgb (4), pixels-drgb (5), rgb (1), drgb (2), off (0), or a number.
        No MODE prints the current settings.
Applies live (no reboot). Keeps nw.linked_remote (ESP-NOW senders), which any /json/cfg POST
would otherwise clear.
"""
import argparse, json, sys, urllib.request

MODES = {"off": 0, "rgb": 1, "drgb": 2, "effect15": 3, "pixels-rgb": 4, "pixels-drgb": 5,
         "pixels": 6, "effect": 7, "effects15": 8, "effects": 9, "presets": 10}
NAMES = {v: k for k, v in MODES.items()}

p = argparse.ArgumentParser()
p.add_argument("--host", default="4.3.2.1")
p.add_argument("mode", nargs="?")
p.add_argument("--addr", type=int, help="DMX start address (1-510)")
p.add_argument("--dss", type=int, help="extra channels between segments in segment modes")
p.add_argument("--uni", type=int, help="E1.31 / Art-Net universe")
a = p.parse_args()

url = f"http://{a.host}/json/cfg"


def get():
    return json.load(urllib.request.urlopen(url, timeout=5))


cfg = get()
live = cfg["if"]["live"]


def show(live):
    d = live["dmx"]
    print(f"mode {d['mode']} ({NAMES.get(d['mode'], '?')})  universe {d['uni']}  address {d['addr']}  "
          f"segment spacing {d['dss']}  port {live['port']}  receive {'on' if live['en'] else 'off'}  "
          f"timeout {live['timeout'] / 10:g} s")


if a.mode is None and a.addr is None and a.dss is None and a.uni is None:
    show(live)
    sys.exit()

dmx = {}
if a.mode is not None:
    dmx["mode"] = int(a.mode) if a.mode.isdigit() else MODES[a.mode]
for k in ("addr", "dss", "uni"):
    if getattr(a, k) is not None:
        dmx[k] = getattr(a, k)
body = {"if": {"live": {"en": True, "dmx": dmx}}}
if "linked_remote" in cfg.get("nw", {}):
    body["nw"] = {"linked_remote": cfg["nw"]["linked_remote"]}
req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
urllib.request.urlopen(req, timeout=5).read()
show(get()["if"]["live"])
