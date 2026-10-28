#!/usr/bin/env python3
"""Generate QLC+ files for driving WLED over E1.31 (sACN): a fixture definition with one mode per
WLED DMX mode, and one workspace per WLED setup (a board runs one DMX mode at a time).

Usage: qlc_gen.py [--leds 7] [--segments 3] [--wled 4.3.2.1] [--iface 4.3.2.2]
                  [--midi "IAC Driver Bus 1"] [--out ..] [--fetch]
  --iface   this computer's IP on the WLED network (QLC+ picks its E1.31 output line by it)
  --midi    MIDI input line for the Virtual Console mappings (Ableton -> IAC bus -> QLC+)
  --fetch   refresh effect/palette/preset names from the board into tools/wled_names.json

Writes fixtures/WLED-<leds>x-RGBW-E131.qxf and workspaces/*.qxw under --out (default: repo root).
Workspaces (switch the board with wled_dmx.py first):
  wled-effects.qxw  WLED DMX mode 9 "Effect segment + W": 18 ch per segment, one fixture each
  wled-pixels.qxw   WLED DMX mode 6 "Multi RGBW": one fixture, one head per LED, RGB Matrix looks
  wled-presets.qxw  WLED DMX mode 10 "Preset": dimmer + preset number
"""
import argparse, json, os, xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
MANUFACTURER = "WLED"
QLC_VERSION = "5.3.0"
# MIDI input channel numbers in QLC+: CC n -> n, note n -> 128 + n (MIDI channel 1)
NOTE, CC = 128, 0
RED_BG = 0xFF400000           # VC colours are stored as ARGB integers


def el(parent, tag, text=None, **attrs):
    e = ET.SubElement(parent, tag, {k: str(v) for k, v in attrs.items()})
    if text is not None:
        e.text = str(text)
    return e


def write(root, path, doctype):
    ET.indent(root, " ")
    body = ET.tostring(root, encoding="unicode")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f'<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE {doctype}>\n{body}\n')
    print("wrote", os.path.relpath(path))


def creator(root):
    c = el(root, "Creator")
    el(c, "Name", "Q Light Controller Plus")
    el(c, "Version", QLC_VERSION)
    el(c, "Author", "wled-qlcplus tools/qlc_gen.py")


# ---------------------------------------------------------------- fixture definition
def fixture_def(names, leds, model):
    root = ET.Element("FixtureDefinition", xmlns="http://www.qlcplus.org/FixtureDefinition")
    creator(root)
    el(root, "Manufacturer", MANUFACTURER)
    el(root, "Model", model)
    el(root, "Type", "LED Bar (Pixels)")
    defined = set()

    def chan(name, preset=None, group=None, caps=(), default=None):
        if name in defined:
            return name
        defined.add(name)
        attrs = {"Name": name}
        if preset:
            attrs["Preset"] = preset
        if default is not None:
            attrs["Default"] = default
        c = el(root, "Channel", **attrs)
        if group:
            el(c, "Group", group, Byte=0)
        for lo, hi, text, *cp in caps:
            el(c, "Capability", text, Min=lo, Max=hi, **(cp[0] if cp else {}))
        return name

    fx, pal = names["effects"], names["palettes"]
    fx_caps = [(i, i, "Reserved" if n in ("RSVD", "-") else n) for i, n in enumerate(fx)]
    fx_caps.append((len(fx), 255, "No change"))
    pal_caps = [(i, i, n) for i, n in enumerate(pal)] + [(len(pal), 255, "Custom palette (else Default)")]
    opt_caps = [(0, 63, "Normal"), (64, 127, "Reverse"), (128, 191, "Mirror"), (192, 255, "Reverse + mirror")]
    preset_caps = [(0, 0, "No change")] + [(n, n, f"Preset {n}") for n in range(1, 250)] + [(250, 255, "Preset 250")]

    dimmer = chan("Dimmer", "IntensityMasterDimmer")
    effect = [dimmer,
              chan("Effect", group="Effect", caps=fx_caps),
              chan("Speed", group="Speed", default=128,
                   caps=[(0, 255, "Effect speed slow to fast", {"Preset": "SlowToFast"})]),
              chan("Intensity", group="Effect", default=128, caps=[(0, 255, "Effect intensity")]),
              chan("Palette", group="Colour", caps=pal_caps),
              chan("Options", group="Effect", caps=opt_caps),
              chan("Red", "IntensityRed"), chan("Green", "IntensityGreen"), chan("Blue", "IntensityBlue")]
    # secondary colours are LTP effect parameters; their names must not clash with pixel channels
    for n in (2, 3):
        effect += [chan(f"Colour {n} {c}", group="Colour", caps=[(0, 255, f"Colour {n} {c.lower()}")])
                   for c in ("Red", "Green", "Blue")]
    whites = [chan("White", "IntensityWhite")] + [
        chan(f"Colour {n} White", group="Colour", caps=[(0, 255, f"Colour {n} white")]) for n in (2, 3)]
    preset = chan("Preset", group="Effect", caps=preset_caps)

    def pixel(i, cols):
        return [chan(f"{c} {i}", f"Intensity{c}") for c in cols]

    rgb = [p for i in range(1, leds + 1) for p in pixel(i, ("Red", "Green", "Blue"))]
    rgbw = [p for i in range(1, leds + 1) for p in pixel(i, ("Red", "Green", "Blue", "White"))]

    modes = [  # (name, channels, channels per head or 0)
        ("Effect (15ch, DMX mode 3/8)", effect, 0),
        ("Effect + W (18ch, DMX mode 7/9)", effect + whites, 0),
        ("Preset (2ch, DMX mode 10)", [dimmer, preset], 0),
        ("Single RGB (3ch, DMX mode 1)", effect[6:9], 0),
        ("Single DRGB (4ch, DMX mode 2)", [dimmer] + effect[6:9], 0),
        (f"Pixels RGB ({3 * leds}ch, DMX mode 4)", rgb, 3),
        (f"Pixels DRGB ({3 * leds + 1}ch, DMX mode 5)", [dimmer] + rgb, 3),
        (f"Pixels RGBW ({4 * leds}ch, DMX mode 6)", rgbw, 4),
    ]
    for name, chans, per_head in modes:
        m = el(root, "Mode", Name=name)
        for i, c in enumerate(chans):
            el(m, "Channel", c, Number=i)
        if per_head:
            first = 1 if chans[0] == dimmer else 0
            for h in range(leds):
                head = el(m, "Head")
                for k in range(per_head):
                    el(head, "Channel", first + h * per_head + k)
    phys = el(root, "Physical")
    el(phys, "Bulb", Type="LED", Lumens=0, ColourTemperature=0)
    el(phys, "Dimensions", Weight=0, Width=0, Height=0, Depth=0)
    el(phys, "Lens", Name="Other", DegreesMin=0, DegreesMax=0)
    el(phys, "Focus", Type="Fixed", PanMax=0, TiltMax=0)
    el(phys, "Layout", Width=leds, Height=1)
    el(phys, "Technical", PowerConsumption=0, DmxConnector="Other")
    return root, {name: chans for name, chans, _ in modes}


# ---------------------------------------------------------------- workspace building blocks
class Workspace:
    def __init__(self, a, model, title):
        self.a, self.model = a, model
        self.root = ET.Element("Workspace", xmlns="http://www.qlcplus.org/Workspace", CurrentWindow="VC")
        creator(self.root)
        self.engine = el(self.root, "Engine")
        iomap = el(self.engine, "InputOutputMap")
        uni = el(iomap, "Universe", Name=title, ID=0)
        el(uni, "Input", Plugin="MIDI", Name=a.midi, UID="", Line=0)
        out = el(uni, "Output", Plugin="E1.31", Name=a.iface, UID="", Line=0)
        el(out, "PluginParameters", ucastIP=a.wled, ucastPort=5568, universe=1, multicast=0,
           transmitMode="Full", priority=100)
        self.fixtures, self.functions = [], []
        self.vc = el(self.root, "VirtualConsole")
        self.page = el(self.vc, "Frame", Caption=title)
        self._appearance(self.page)
        self.next_widget = 0

    def fixture(self, name, mode, chans, address, forced_htp=()):
        fid = len(self.fixtures)
        f = el(self.engine, "Fixture")
        el(f, "Manufacturer", MANUFACTURER)
        el(f, "Model", self.model)
        el(f, "Mode", mode)
        el(f, "ID", fid)
        el(f, "Name", name)
        el(f, "Universe", 0)
        el(f, "Address", address)
        el(f, "Channels", len(chans))
        if forced_htp:
            el(f, "ForcedHTP", ",".join(str(chans.index(c)) for c in forced_htp))
        self.fixtures.append((fid, chans))
        return fid

    def ch(self, fid, name):
        return self.fixtures[fid][1].index(name)

    def scene(self, name, values, path="Looks", hidden=False):
        """values: {fixture id: {channel name: value}}"""
        fn = self._function("Scene", name, path, hidden)
        el(fn, "Speed", FadeIn=0, FadeOut=0, Duration=0)
        for fid, vals in values.items():
            pairs = sorted((self.ch(fid, c), v) for c, v in vals.items())
            el(fn, "FixtureVal", ",".join(f"{c},{v}" for c, v in pairs), ID=fid)
        return int(fn.get("ID"))

    def chaser(self, name, steps, hold_ms, fade_ms=0):
        fn = self._function("Chaser", name, "Looks")
        el(fn, "Speed", FadeIn=fade_ms, FadeOut=fade_ms, Duration=hold_ms)
        el(fn, "Direction", "Forward")
        el(fn, "RunOrder", "Loop")
        el(fn, "SpeedModes", FadeIn="Common", FadeOut="Common", Duration="Common")
        for i, fid in enumerate(steps):
            el(fn, "Step", fid, Number=i, FadeIn=fade_ms, Hold=hold_ms, FadeOut=fade_ms)
        return int(fn.get("ID"))

    def matrix(self, name, script, group, colours=(), duration=100, props=None, mode="RGB"):
        fn = self._function("RGBMatrix", name, "Matrices")
        el(fn, "Tempo", "Time")
        el(fn, "Speed", FadeIn=0, FadeOut=0, Duration=duration)
        el(fn, "Direction", "Forward")
        el(fn, "RunOrder", "Loop")
        el(fn, "Algorithm", script, Type="Script")
        for i, rgb in enumerate(colours):
            el(fn, "Color", 0xFF000000 | rgb, Index=i)
        el(fn, "ControlMode", mode)
        el(fn, "FixtureGroup", group)
        for k, v in (props or {}).items():
            el(fn, "Property", Name=k, Value=v)
        return int(fn.get("ID"))

    def group(self, name, fid, leds):
        g = el(self.engine, "FixtureGroup", ID=0)
        el(g, "Name", name)
        el(g, "Size", X=leds, Y=1)
        for h in range(leds):
            el(g, "Head", h, X=h, Y=0, Fixture=fid)
        return 0

    def _function(self, kind, name, path, hidden=False):
        fn = el(self.engine, "Function", ID=len(self.functions), Type=kind, Name=name, Path=path,
                **({"Hidden": "True"} if hidden else {}))
        self.functions.append(fn)
        return fn

    # Virtual Console
    def _appearance(self, w, bg=None):
        ap = el(w, "Appearance")
        el(ap, "FrameStyle", "None")
        el(ap, "ForegroundColor", "Default")
        el(ap, "BackgroundColor", bg or "Default")
        el(ap, "BackgroundImage", "None")
        el(ap, "Font", "Default")

    def _widget(self, parent, tag, caption, x, y, w, h, bg=None):
        wid = self.next_widget
        self.next_widget += 1
        e = el(parent, tag, Caption=caption, ID=wid)
        el(e, "WindowState", Visible="True", X=x, Y=y, Width=w, Height=h)
        self._appearance(e, bg)
        return e

    def solo_frame(self, caption, x, y, w, h):
        f = self._widget(self.page, "SoloFrame", caption, x, y, w, h)
        el(f, "ShowHeader", "True")
        return f

    def button(self, parent, caption, function, x, y, action="Toggle", note=None, bg=None):
        b = self._widget(parent, "Button", caption, x, y, 110, 60, bg)
        if function is not None:
            el(b, "Function", ID=function)
        el(b, "Action", action)
        if note is not None:
            el(b, "Input", ID=0, Universe=0, Channel=NOTE + note)
        return int(b.get("ID"))

    def slider(self, caption, x, y, mode, channels=(), cc=None, value=0, function=None, monitor=False):
        """monitor: follow the channel and take over when moved. Needed on LTP channels, where a
        scene started after the slider was first moved would otherwise keep winning."""
        s = self._widget(self.page, "Slider", caption, x, y, 70, 260)
        el(s, "SliderMode", mode, ValueDisplayStyle="Exact", **({"Monitor": "true"} if monitor else {}))
        if mode == "Level":
            lvl = el(s, "Level", LowLimit=0, HighLimit=255, Value=value)
            for fid, c in channels:
                el(lvl, "Channel", self.ch(fid, c), Fixture=fid)
        elif mode == "Adjust":
            el(s, "Adjust", Attribute=0, Function=function)
        if cc is not None:
            el(s, "Input", ID=0, Universe=0, Channel=CC + cc)
        return int(s.get("ID"))

    def label(self, text, x, y, w=560, h=40):
        self._widget(self.page, "Label", text, x, y, w, h)

    def save(self, path):
        write(self.root, path, "Workspace")


# ---------------------------------------------------------------- the three workspaces
def fx_index(names, name):
    return names["effects"].index(name)


def colour(rgb, n=None):
    p = f"Colour {n} " if n else ""
    return dict(zip((f"{p}Red", f"{p}Green", f"{p}Blue"), rgb))


def effects_ws(a, names, model, modes):
    mode = "Effect + W (18ch, DMX mode 7/9)"
    chans = modes[mode]
    ws = Workspace(a, model, "WLED effects")
    segs = [ws.fixture(f"WLED seg {s}", mode, chans, s * len(chans)) for s in range(a.segments)]
    fx = lambda n: fx_index(names, n)

    def look(effect, c1, c2=(0, 0, 0), sx=128, ix=128, pal=0, per_seg=None):
        vals = {}
        for i, s in enumerate(segs):
            v = {"Effect": effect, "Speed": sx, "Intensity": ix, "Palette": pal,   # dimmers: faders
                 **colour(c1), **colour(c2, 2)}
            v.update((per_seg or {}).get(i, {}))
            vals[s] = v
        return vals

    looks = [
        ("Warm solid", look(fx("Solid"), (255, 110, 20))),
        ("Rainbow", look(fx("Rainbow"), (255, 255, 255), sx=160)),
        ("Fire", look(fx("Fire 2012"), (255, 60, 0), sx=180, ix=160, pal=names["palettes"].index("Fire"))),
        ("Breathe blue", look(fx("Breathe"), (0, 40, 255), sx=100)),
        ("Chase red/blue", look(fx("Chase"), (255, 0, 0), (0, 0, 255), sx=200)),
        ("Split RGB", look(fx("Solid"), (0, 0, 0), per_seg={
            0: colour((255, 0, 0)), 1: {**colour((0, 255, 0)), "Effect": fx("Blink"), "Speed": 200},
            2: colour((0, 0, 255))})),
        ("Strobe white", look(fx("Strobe"), (0, 0, 0), sx=230, per_seg={i: {"White": 255} for i in range(a.segments)})),
    ]
    ids = [ws.scene(n, v) for n, v in looks]
    # the chaser runs hidden copies: a solo frame stops all its buttons' functions, the chaser
    # included, whenever one of those scenes starts
    steps = [ws.scene(f"{n} (cycle)", v, path="Looks/Cycle", hidden=True) for n, v in looks[:5]]
    cycle = ws.chaser("Cycle looks", steps, hold_ms=2000)

    ws.label("WLED DMX mode 9 (Effect segment + W), universe 1, address 1. Notes 36+ pick looks.", 10, 10)
    frame = ws.solo_frame("Looks (one at a time)", 10, 60, 480, 290)
    for i, (n, _) in enumerate(looks):
        ws.button(frame, n, ids[i], 10 + (i % 4) * 115, 40 + (i // 4) * 70, note=36 + i)
    ws.button(frame, "Cycle", cycle, 10 + 3 * 115, 110, note=36 + len(looks))
    ws.button(ws.page, "Blackout", None, 10, 360, action="Blackout", note=48, bg=RED_BG)
    all_ch = lambda c: [(s, c) for s in segs]
    ws.slider("Master", 500, 60, "GrandMaster", cc=20)
    ws.slider("Speed", 575, 60, "Level", all_ch("Speed"), cc=21, monitor=True)
    ws.slider("Intensity", 650, 60, "Level", all_ch("Intensity"), cc=22, monitor=True)
    for i, s in enumerate(segs):
        ws.slider(f"Seg {i}", 725 + i * 75, 60, "Level", [(s, "Dimmer")], cc=23 + i, value=255)
    ws.save(os.path.join(a.out, "workspaces", "wled-effects.qxw"))


def pixels_ws(a, names, model, modes):
    mode = f"Pixels RGBW ({4 * a.leds}ch, DMX mode 6)"
    ws = Workspace(a, model, "WLED pixels")
    fid = ws.fixture("WLED pixels", mode, modes[mode], 0)
    grp = ws.group("Strip", fid, a.leds)
    mats = [
        ("Rainbow", ws.matrix("Rainbow", "Gradient", grp, duration=60, props={"presetIndex": "Rainbow", "presetSize": a.leds})),
        ("Sine wave", ws.matrix("Sine wave", "Sine Wave", grp, [0xFF0000, 0x0000FF], duration=80)),
        ("Fire flicker", ws.matrix("Fire flicker", "Fire Flicker", grp, [0xFF4000], duration=60)),  # "Fire" is 2-D: dark on 1 row
        ("Meteor", ws.matrix("Meteor", "Meteor", grp, [0x00FF80], duration=80)),
        ("TwinkleFox", ws.matrix("TwinkleFox", "TwinkleFox", grp, duration=60)),
        ("Sinelon", ws.matrix("Sinelon", "Sinelon", grp, [0xFFAA00], duration=60)),  # "Marquee" is static on 1 row
    ]
    white = ws.scene("Full white (W)", {fid: {f"White {i}": 255 for i in range(1, a.leds + 1)}})
    ends = ws.scene("Ends red", {fid: {"Red 1": 255, f"Red {a.leds}": 255}})

    ws.label(f"WLED DMX mode 6 (Multi RGBW), {a.leds} LEDs from address 1. Notes 36+ pick looks.", 10, 10)
    frame = ws.solo_frame("Matrices (one at a time)", 10, 60, 480, 220)
    for i, (n, m) in enumerate(mats):
        ws.button(frame, n, m, 10 + (i % 4) * 115, 40 + (i // 4) * 70, note=36 + i)
    ws.button(ws.page, "Full white (W)", white, 10, 290, note=36 + len(mats))
    ws.button(ws.page, "Ends red", ends, 125, 290, action="Flash", note=37 + len(mats))
    ws.button(ws.page, "Blackout", None, 240, 290, action="Blackout", note=48, bg=RED_BG)
    ws.slider("Master", 500, 60, "GrandMaster", cc=20)
    ws.save(os.path.join(a.out, "workspaces", "wled-pixels.qxw"))


def presets_ws(a, names, model, modes, presets):
    mode = "Preset (2ch, DMX mode 10)"
    ws = Workspace(a, model, "WLED presets")
    # HTP so the preset value drops back to 0 ("no change") when a Flash button is released; LTP
    # would hold it, and WLED re-applies a held playlist preset every time the playlist ends
    fid = ws.fixture("WLED presets", mode, modes[mode], 0, forced_htp=["Preset"])
    ws.label("WLED DMX mode 10 (Preset). Flash buttons: a held value re-fires a playlist when it ends.", 10, 10)
    for i, (num, name) in enumerate(presets):
        sid = ws.scene(f"Preset {num} {name}", {fid: {"Preset": num}})
        ws.button(ws.page, f"{num} {name}", sid, 10 + (i % 4) * 115, 60 + (i // 4) * 70,
                  action="Flash", note=36 + i)
    ws.slider("Brightness", 480, 60, "Level", [(fid, "Dimmer")], cc=20, value=255)
    ws.save(os.path.join(a.out, "workspaces", "wled-presets.qxw"))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--leds", type=int, default=7)
    ap.add_argument("--segments", type=int, default=3)
    ap.add_argument("--wled", default="4.3.2.1", help="board IP (E1.31 unicast target)")
    ap.add_argument("--iface", default="4.3.2.2", help="this computer's IP on the WLED network")
    ap.add_argument("--midi", default="IAC Driver Bus 1", help="MIDI input line name")
    ap.add_argument("--out", default=os.path.join(HERE, ".."))
    ap.add_argument("--fetch", action="store_true", help="refresh names (and presets) from the board")
    a = ap.parse_args()

    names_path = os.path.join(HERE, "wled_names.json")
    if a.fetch:
        import urllib.request
        get = lambda p: json.load(urllib.request.urlopen(f"http://{a.wled}{p}", timeout=5))
        info = get("/json/info")
        presets = {k: v.get("n", f"Preset {k}") for k, v in get("/presets.json").items() if k != "0"}
        json.dump({"_source": f"WLED {info['ver']} on {info['arch']} (/json/eff, /json/pal, /presets.json)",
                   "effects": get("/json/eff"), "palettes": get("/json/pal"), "presets": presets},
                  open(names_path, "w"), indent=0)
    with open(names_path) as f:
        names = json.load(f)
    presets = sorted((int(k), v) for k, v in names.get("presets", {"1": "Full", "2": "Idle", "3": "Zap"}).items())

    for d in ("fixtures", "workspaces"):
        os.makedirs(os.path.join(a.out, d), exist_ok=True)
    model = f"WLED {a.leds}x RGBW (E1.31)"
    fdef, modes = fixture_def(names, a.leds, model)
    write(fdef, os.path.join(a.out, "fixtures", f"WLED-{a.leds}x-RGBW-E131.qxf"), "FixtureDefinition")
    effects_ws(a, names, model, modes)
    pixels_ws(a, names, model, modes)
    presets_ws(a, names, model, modes, presets)


if __name__ == "__main__":
    main()
