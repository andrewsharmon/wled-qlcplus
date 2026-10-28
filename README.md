# WLED in QLC+ (7 × RGBW over E1.31)

A QLC+ fixture definition and three ready-made workspaces for running a WLED controller with
7 SK6812 RGBW LEDs as a DMX fixture over E1.31 (sACN), with Virtual Console controls mapped to MIDI.

Tested with WLED 16.0.1 (ESP32-C3) and QLC+ 5.3.0 on macOS: every look, fader and button was
checked against the board's state and LED output, and the pixel looks were decoded on the LED data
line with an oscilloscope.

| Path | What it is |
|---|---|
| `fixtures/WLED-7x-RGBW-E131.qxf` | the fixture: one mode per WLED DMX mode, WLED 16.0.1 effect and palette names on its channels |
| `workspaces/wled-effects.qxw` | WLED effects per segment (3 segments) |
| `workspaces/wled-pixels.qxw` | each LED as an RGBW head, QLC+ RGB Matrix looks |
| `workspaces/wled-presets.qxw` | trigger WLED presets and playlists |
| `tools/wled_dmx.py` | show or switch WLED's DMX mode from the command line |
| `tools/qlc_gen.py` | regenerate everything for other IPs, LED counts or MIDI ports |

## 1. Set up WLED

In WLED: **Config → Sync Interfaces → Realtime**

- Receive UDP realtime: **on**
- Network DMX input: type **E1.31 (sACN)**, port **5568**, multicast off, start universe **1**
  (port and universe changes need a reboot)
- DMX start address **1**, DMX segment spacing **0**
- DMX mode — pick the one for the workspace you'll use:

| Workspace | WLED DMX mode | Channels |
|---|---|---|
| `wled-effects.qxw` | Effect Segment + White | 18 per segment (54 for 3 segments) |
| `wled-pixels.qxw` | Multi RGBW | 28 (4 per LED) |
| `wled-presets.qxw` | Preset | 2 (dimmer, preset) |

The effects workspace expects three WLED segments (any split of the 7 LEDs). The DMX mode can also
be switched without a reboot from any computer on the same network:

```bash
python3 tools/wled_dmx.py --host 4.3.2.1 effects     # or pixels / presets; no argument shows the settings
```

## 2. Install the fixture

Copy `fixtures/WLED-7x-RGBW-E131.qxf` into QLC+'s user fixture folder and restart QLC+:

| OS | Folder |
|---|---|
| macOS | `~/Library/Application Support/QLC+/Fixtures` |
| Windows | `%USERPROFILE%\QLC+\Fixtures` |
| Linux | `~/.qlcplus/fixtures` |

It shows up as manufacturer **WLED**, model **WLED 7x RGBW (E1.31)**. Modes:

| Fixture mode in QLC+ | WLED DMX mode |
|---|---|
| Effect (15ch, DMX mode 3/8) | Effect, or Effect Segment (one fixture per segment) |
| Effect + W (18ch, DMX mode 7/9) | Effect + White, or Effect Segment + White |
| Preset (2ch, DMX mode 10) | Preset |
| Single RGB (3ch, DMX mode 1) | Single RGB |
| Single DRGB (4ch, DMX mode 2) | Single DRGB |
| Pixels RGB (21ch, DMX mode 4) | Multi RGB |
| Pixels DRGB (22ch, DMX mode 5) | Dimmer + Multi RGB |
| Pixels RGBW (28ch, DMX mode 6) | Multi RGBW |

The numbers are WLED's internal mode numbers (what `wled_dmx.py` and WLED's `/json/cfg` use).

The effect and palette channels take WLED's effect and palette numbers (named in the fixture). The
pixel modes have one head per LED, so QLC+'s RGB Matrix works on them.

## 3. Open a workspace

Open one of the `workspaces/*.qxw` files in QLC+. Each one sends E1.31 to universe 1 by unicast to
**4.3.2.1** (WLED's own access point address) from the computer's address **4.3.2.2** on it.

On another network, either re-patch in QLC+ (**Inputs/Outputs** → universe → E1.31 on your network
interface → IP address = the WLED's IP, universe 1), or regenerate the files:

```bash
python3 tools/qlc_gen.py --wled 192.168.1.50 --iface 192.168.1.20
```

## 4. Controls

The Virtual Console has these controls, also mapped to MIDI notes and CCs on channel 1 (C1 = note 36):

| Workspace | Buttons (MIDI note) | Faders (MIDI CC) |
|---|---|---|
| effects | 36 Warm solid · 37 Rainbow · 38 Fire · 39 Breathe blue · 40 Chase red/blue · 41 Split RGB · 42 Strobe white · 43 Cycle (chaser) · 48 Blackout | 20 Grand Master · 21 speed · 22 intensity · 23–25 segment 0–2 dimmer |
| pixels | 36 Rainbow · 37 Sine wave · 38 Fire flicker · 39 Meteor · 40 TwinkleFox · 41 Sinelon · 42 Full white (W) · 43 Ends red (hold) · 48 Blackout | 20 Grand Master |
| presets | 36 / 37 / 38 = WLED preset 1 / 2 / 3 (tap) | 20 brightness |

Looks are one-at-a-time; pressing a look's button again turns it off.

**MIDI from a DAW (e.g. Ableton Live).** The workspaces listen on a MIDI input named
"IAC Driver Bus 1". On macOS, enable the IAC Driver in Audio MIDI Setup and send a MIDI track to it.
For Windows, see below. If your port has a different name, pick it under Inputs/Outputs, or
regenerate with `python3 tools/qlc_gen.py --midi "Your Port"`.

## Windows: Ableton → loopMIDI → QLC+

Windows has no built-in MIDI loopback yet, so use [loopMIDI](https://www.tobias-erichsen.de/software/loopmidi.html)
(free; listed for Windows 7–10, check it on Windows 11).

1. **loopMIDI:** type a port name (e.g. `QLC`) and click **+**. Ports exist only while loopMIDI
   runs, so enable autostart from its tray icon. Keep the name to 31 characters or fewer.
2. **Ableton:** Preferences → Link, Tempo & MIDI → for the `QLC` port turn **Track on for the
   Output** and leave its **Input off**. A loopback returns everything Ableton sends, so both on
   makes a MIDI feedback loop. Set a MIDI track's *MIDI To* to `QLC`, channel 1.
3. **Workspaces:** QLC+ matches the input by its exact name, and Windows won't necessarily get
   4.3.2.2 on WLED's access point (check with `ipconfig`). Regenerate with both:

   ```bash
   py tools\qlc_gen.py --midi "QLC" --iface 4.3.2.3
   ```

4. **Fixture:** copy `fixtures\WLED-7x-RGBW-E131.qxf` to `%USERPROFILE%\QLC+\Fixtures`.
5. Start loopMIDI, then QLC+ and Ableton. In QLC+, Inputs/Outputs should show the `QLC` input on
   the universe; if not, select it there.

loopMIDI ports can be opened by several apps at once (up to 8), so Ableton and QLC+ share one
port. E1.31 from QLC+ is outgoing UDP, which the Windows firewall allows by default.

## Good to know

- **While QLC+ runs, it owns the board.** In the effect modes WLED re-applies every DMX channel that
  differs from its state on each packet, so changes from WLED's app are overwritten. In the pixel
  modes, WLED's own effects pause until about 2.5 s after QLC+ stops sending.
- **Held preset values re-fire playlists.** In Preset mode WLED re-applies a playlist each time it
  ends if the DMX value is still on it. The preset buttons are momentary and the preset channel is
  forced HTP, so a tap plays a playlist once.
- **Use E1.31, not Art-Net**, unless you switch WLED to Art-Net: QLC+ sends Art-Net to port 6454,
  and WLED listens on the one port set above.
- **Some RGB Matrix scripts are 2-D only.** On a 1-row strip "Fire" and "Pacifica" stay dark and
  "Marquee" doesn't move; the ones in the pixels workspace all work.
- **Other LED counts:** the effect and preset modes don't depend on LED count; for the pixel modes,
  regenerate with `python3 tools/qlc_gen.py --leds 30` (re-copy the new fixture file). Use
  `--fetch --wled <ip>` to pull effect, palette and preset names from your own board first.
- The tools need Python 3.9+ and no extra packages (on Windows run them with `py`).
