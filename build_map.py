#!/usr/bin/env python
"""
build_map.py — one-time export of the canonical HIL I2C placement map.

Single source of truth: the generator + component definitions in the
`vendor/Wippersnapper_Components` submodule (branch add/hil-i2c-generator).
This script imports that generator, reproduces its conflict-free channel /
address / jumper assignment WITHOUT writing the spreadsheet (and without the
Claude jumper-fetch step), merges the firmware-side `overlay.json` (driver
names, currently-attached flags, PR #933 membership, notes), and emits:

  - hil_map.json            the canonical map both tools read
  - sensor-coach.html       the HIL_MAP array is injected between markers

Re-run after pulling a newer submodule commit or editing overlay.json:

    python build_map.py

See .claude/skills/hil-sensor-map/SKILL.md for the full workflow, including
how to (re)generate the human spreadsheet copy you maintain separately.
"""
import json
import importlib.util
from pathlib import Path

HERE = Path(__file__).parent
SUBMODULE = HERE / "vendor" / "Wippersnapper_Components"
GEN_PATH = SUBMODULE / "generate_hil_spreadsheet.py"
OVERLAY_PATH = HERE / "overlay.json"
MAP_PATH = HERE / "hil_map.json"
HTML_PATH = HERE / "sensor-coach.html"

# jumper short-settings that do NOT require soldering / pad work
NO_SOLDER = {"", "default", "mux isolation", "fixed"}


def load_generator():
    if not GEN_PATH.exists():
        raise SystemExit(
            f"Generator not found at {GEN_PATH}.\n"
            "Run:  git submodule update --init --recursive"
        )
    spec = importlib.util.spec_from_file_location("hil_generator", GEN_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def hexs(a):
    return f"0x{a:02X}" if a is not None else None


def mux_for_channel(g, ch):
    """(mux_address_str, mux_channel_int) for a channel index, or (None, None)."""
    if ch == 0:
        return (None, None)
    if ch <= 8:
        return (hexs(g.MUXES[0]["address"]), ch - 1)
    return (hexs(g.MUXES[1]["address"]), ch - 9)


def _attached_set():
    if not OVERLAY_PATH.exists():
        return set()
    ov = json.loads(OVERLAY_PATH.read_text(encoding="utf-8"))
    return {k for k, v in ov.items()
            if not k.startswith("_") and isinstance(v, dict) and v.get("attached")}


def _prior_positions():
    """Pins come from the committed hil_map.json — attached devices keep their
    current channel + address ('the JSON import IS the pinning')."""
    if not MAP_PATH.exists():
        return {}
    prior = json.loads(MAP_PATH.read_text(encoding="utf-8"))
    out = {}
    for r in prior:
        if r.get("channel_index", -1) >= 0 and r.get("address"):
            out[r["component"]] = (r["channel_index"], int(r["address"], 16))
    return out


def _detect_conflicts(comps, assignment, picked_addr):
    """Same-channel+address collisions, or a mux device clashing with the
    always-visible direct bus. These mean a proposed device landed on a pin —
    resolve per the hil-sensor-map skill, don't silently reshuffle a pin."""
    msgs = []
    direct = {picked_addr[c["dir"]] for c in comps
              if assignment.get(c["dir"]) == 0 and picked_addr.get(c["dir"]) is not None}
    seen = {}
    for c in comps:
        ch = assignment.get(c["dir"], -1)
        pa = picked_addr.get(c["dir"])
        if ch < 0 or pa is None:
            continue
        if (ch, pa) in seen:
            msgs.append(f"CONFLICT ch{ch} 0x{pa:02X}: {seen[(ch, pa)]} AND {c['dir']}")
        else:
            seen[(ch, pa)] = c["dir"]
        if ch > 0 and pa in direct:
            msgs.append(f"CONFLICT mux ch{ch} {c['dir']} 0x{pa:02X} clashes with direct bus")
    return msgs


def build_records(g):
    """Generator placement for PROPOSALS, with attached devices PINNED to their
    current position carried over from hil_map.json (frozen out of the matrix)."""
    g.configure_muxes(False)  # single TCA9548A @ 0x77, matching the bench
    comps = g.load_components(SUBMODULE)
    assignment, picked_addr, _channel_addrs = g.assign_channels(comps)

    # ── Pinning: freeze attached devices at their committed position ──
    attached = _attached_set()
    pins = {d: pos for d, pos in _prior_positions().items() if d in attached}
    for d, (ch, addr) in pins.items():
        if d in assignment:
            assignment[d] = ch
            picked_addr[d] = addr
    build_records.pins = sorted(pins)
    build_records.conflicts = _detect_conflicts(comps, assignment, picked_addr)

    records = []
    for c in comps:
        ch = assignment.get(c["dir"], -1)
        pa = picked_addr.get(c["dir"])
        default_addr = c["all_addresses"][0] if c["all_addresses"] else None
        non_default = pa is not None and default_addr is not None and pa != default_addr
        short, full = g._jumper_setting(c, pa) if non_default else ("", "")
        needs_solder = bool(non_default and short.lower() not in NO_SOLDER)
        mux_addr, mux_ch = mux_for_channel(g, ch) if ch >= 0 else (None, None)

        if needs_solder:
            solder_action = f"set jumper '{short}' (default {hexs(default_addr)} -> {hexs(pa)})"
        else:
            solder_action = ""

        records.append({
            "component": c["dir"],
            "name": c["displayName"],
            "vendor": c.get("vendor", ""),
            "placed": ch >= 0,
            "channel_index": ch,                       # 0=direct, 1..8 = mux ch0..7
            "channel": g.channel_short_label(ch) if ch >= 0 else "unplaceable",
            "channel_label": g.channel_label(ch) if ch >= 0 else "UNPLACEABLE",
            "mux_address": mux_addr,                    # "0x77" or null (direct)
            "mux_channel": mux_ch,                      # firmware mux_channel value, or null
            "address": hexs(pa),
            "default_address": hexs(default_addr),
            "non_default": non_default,
            "needs_solder": needs_solder,
            "jumper_setting": short,                    # concise pad notation, e.g. "A0:1"
            "solder_action": solder_action,            # human phrasing for needs_solder
            "jumper_info": full,                        # full jumper text from the cache
            "all_addresses": [hexs(a) for a in c["all_addresses"]],
            "sensors": c.get("sensors", []),
            "guide_url": c.get("guide_url", ""),
            # firmware-side fields, filled from overlay.json below:
            "driver": None,
            "attached": False,
            "pr933": False,
            "note": "",
        })
    records.sort(key=lambda r: (r["channel_index"], r["address"] or "0xZZ"))
    return records


def merge_overlay(records):
    if not OVERLAY_PATH.exists():
        print(f"  (no {OVERLAY_PATH.name}; map has no driver/attached info)")
        return
    overlay = {k: v for k, v in json.loads(OVERLAY_PATH.read_text(encoding="utf-8")).items()
               if not k.startswith("_")}
    by_dir = {r["component"]: r for r in records}
    unknown = [k for k in overlay if k not in by_dir]
    if unknown:
        print(f"  WARNING: overlay keys not in component data: {', '.join(unknown)}")
    for dir_name, extra in overlay.items():
        r = by_dir.get(dir_name)
        if r:
            r.update({k: v for k, v in extra.items() if v is not None})


def inject_html(records):
    if not HTML_PATH.exists():
        print(f"  (no {HTML_PATH.name}; skipping inject)")
        return
    html = HTML_PATH.read_text(encoding="utf-8")
    start = "/*__HIL_MAP_START__*/"
    end = "/*__HIL_MAP_END__*/"
    if start not in html or end not in html:
        print(f"  WARNING: markers not found in {HTML_PATH.name}; not injected")
        return
    blob = json.dumps(records, ensure_ascii=False)
    pre = html[: html.index(start) + len(start)]
    post = html[html.index(end):]
    HTML_PATH.write_text(pre + blob + post, encoding="utf-8")
    print(f"  injected {len(records)} records into {HTML_PATH.name}")


def main():
    g = load_generator()
    records = build_records(g)
    merge_overlay(records)
    MAP_PATH.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    placed = sum(1 for r in records if r["placed"])
    solder = sum(1 for r in records if r["needs_solder"])
    pr = sum(1 for r in records if r["pr933"])
    print(f"WROTE {MAP_PATH.name}: {len(records)} components "
          f"({placed} placed, {solder} need soldering, {pr} PR#933 drivers)")
    print(f"  pinned (attached, frozen out of the matrix): {len(build_records.pins)}"
          + (f" -> {', '.join(build_records.pins)}" if build_records.pins else ""))
    if build_records.conflicts:
        print(f"  !! {len(build_records.conflicts)} CONFLICT(S) — a proposed device landed on a pin.")
        print("     Resolve per .claude/skills/hil-sensor-map/SKILL.md (move the NEW one, not the pin):")
        for m in build_records.conflicts:
            print("       " + m)
    inject_html(records)


if __name__ == "__main__":
    main()
