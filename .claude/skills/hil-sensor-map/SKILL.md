---
name: hil-sensor-map
description: Regenerate or consume the canonical HIL I2C sensor placement map (hil_map.json) for the QT Py ESP32-S3 mux string. Use when adding/moving a sensor on the bench, updating driver/attached info, regenerating the soldering-guide PDF or the Sensor Coach voice app, refreshing from the Wippersnapper_Components generator, or maintaining the human spreadsheet copy.
---

# HIL Sensor Map

Single source of truth for which I2C sensor goes on which TCA9548A channel/address on the
QT Py ESP32-S3 N4R2 bench, and whether it needs soldering.

## Architecture (one map, many consumers)

```
vendor/Wippersnapper_Components/   git submodule @ add/hil-i2c-generator
  generate_hil_spreadsheet.py      the GENERATOR (channel/address/jumper algorithm)
  components/i2c/*/definition.json source data: addresses, sensor types, URLs
  i2c_address_jumper_info.json     cached jumper/solder descriptions
        │
        ▼  build_map.py  (imports the generator, no xlsx, no Claude fetch)
        +  overlay.json  (driver names, attached-now, PR#933, notes)
        ▼
  hil_map.json   ← CANONICAL MAP (commit this)
        ├─► make_hil_pdf.py   → hil_sensor_attachment_guide.pdf
        └─► sensor-coach.html (HIL_MAP injected between markers)
```

`hil_map.json` is a **committed export** that doubles as the **pin source**: on every run
`build_map.py` reads the previous `hil_map.json` back in and freezes every **attached** device
at its current channel + address, removing it from the generator's redistribution matrix. The
generator only ever *proposes* positions for **not-yet-attached** parts, routing them around the
pins. So already-wired devices never move; only free slots get (re)assigned. The generator +
component data come in as a submodule so the same source feeds both the map and the spreadsheet.

## Regenerate the map (the "import" step)

```sh
git submodule update --init --recursive     # first time / after cloning
python build_map.py                          # -> hil_map.json + injects sensor-coach.html
python make_hil_pdf.py                        # -> hil_sensor_attachment_guide.pdf  (needs: pip install fpdf2)
```

`build_map.py` requires `openpyxl` (imported transitively by the generator):
`pip install openpyxl fpdf2`.

## Pinning model — how attached devices stay put

- A device with `"attached": true` in `overlay.json` is **pinned** to whatever channel + address
  it currently holds in `hil_map.json`. `build_map.py` carries that position forward verbatim and
  excludes the device from the solve.
- Everything else (`attached: false`) is a **proposal** — the generator places it into the free
  space around the pins. Proposals can move freely between runs; pins never do.
- **Lifecycle of a new sensor:** it starts `attached: false` → the generator proposes a slot →
  you physically wire it there → flip `attached: true` → next `build_map.py` pins it at that slot.
  (To wire it somewhere *other* than the proposal, see "moving a pin" below.)
- Channel/address/jumper are **always** the generator's (for proposals) or the carried-over JSON's
  (for pins) — never hand-typed into `overlay.json` or `hil_map.json`.

## When to re-run (LLM reconciliation loop)

This is the workflow an LLM (or a person) follows when the bench changes — read the situation,
make the minimal `overlay.json`/submodule edit, rerun, resolve any conflict, then commit:

- **New sensor attached** → set its component key `"attached": true` in `overlay.json` → `python build_map.py`.
  It pins at its current proposed slot.
- **Sensor removed** → set `"attached": false` (or drop the key) → rerun. Its slot returns to the free pool.
- **New driver / PR membership / note** → add or edit the `overlay.json` key → rerun.
- **Upstream component or address change** → bump the submodule, then rerun:
  ```sh
  cd vendor/Wippersnapper_Components && git pull origin add/hil-i2c-generator && cd ../..
  git add vendor/Wippersnapper_Components && python build_map.py
  ```
- **Moving a pin on purpose** (rewire an attached device): temporarily set it `attached: false`,
  rerun (so the JSON no longer pins the old slot), let the generator re-propose OR hand-place by
  rewiring, then set `attached: true` and rerun to lock the new position.

`overlay.json` keys are component directory names under
`vendor/Wippersnapper_Components/components/i2c/`; `build_map.py` warns on a key with no match.

### Resolving a CONFLICT

If `build_map.py` prints `!! N CONFLICT(S)`, a **proposed** device landed on a **pinned**
channel+address (e.g. a submodule bump changed the free space). The pin is authoritative — do
**not** move the pin. Resolve the *proposed* device instead:

1. If it has another usable address (jumper) or another free channel, the generator will pick it
   automatically once the colliding slot is genuinely occupied — re-run and confirm.
2. If it's genuinely stuck, give it a different jumper address in the upstream component/jumper
   data, or accept it on a different channel, then rerun until conflicts are zero.
3. Never silently swap two devices — keep every `attached: true` device exactly where it is.

## Maintaining the human spreadsheet copy (separate from the JSON)

The JSON map is for the tools. The browsable spreadsheet (Component Matrix, Mux Layout,
Address Conflicts, Test Fixtures) is generated by the same generator but kept **separately** —
it is not committed here, so your working copy can carry hand notes without churning the repo:

```sh
cd vendor/Wippersnapper_Components
python generate_hil_spreadsheet.py -o ~/Downloads/hil_i2c_components.xlsx
# (--dual-mux to also model the 2nd TCA9544A @ 0x71)
```

Re-export to `~/Downloads/…` (or open as `.ods`) whenever you want a fresh, read-only view;
keep your annotated copy under a different name so the export never overwrites your notes. The
JSON map and the spreadsheet come from the same generator, so they stay consistent as long as
both are regenerated after a submodule bump.

## hil_map.json record shape

```jsonc
{
  "component": "sgp41", "name": "SGP41", "vendor": "Sensirion",
  "placed": true, "channel_index": 2, "channel": "8ch_mux_ch1",
  "channel_label": "TCA9548A (0x77) Ch1",
  "mux_address": "0x77", "mux_channel": 1,        // firmware Probe mux_channel value
  "address": "0x59", "default_address": "0x59", "non_default": false,
  "needs_solder": false, "jumper_setting": "", "solder_action": "",
  "jumper_info": "", "all_addresses": ["0x59"],
  "sensors": ["voc-index","nox-index","raw"], "guide_url": "...",
  "driver": "drvSgp41", "attached": false, "pr933": true,        // from overlay.json
  "note": "Needs a REAL SGP41 ..."
}
```
