# hil-bench-tools

Bench tooling for the WipperSnapper hardware-in-the-loop I2C sensor string on a
**QT Py ESP32-S3 N4R2** with a TCA9548A multiplexer @ `0x77` (device
`mcu-qtpy-esp32s3-n4r2-hil006`).

Everything keys off one **canonical placement map**, `hil_map.json`, generated from the
`Wippersnapper_Components` sensor generator (a git submodule) plus a small firmware-side
`overlay.json`. No hand-maintained sensor tables.

> 🎙️ **Live Sensor Coach app:** <https://gundry-consultancy.github.io/hil-bench-tools/>
> Open it on your phone at the bench, paste an Anthropic API key (stored only in your browser),
> and say a sensor. Auto-deployed from `main` by `.github/workflows/pages.yml`.

## Contents

| File | What |
|---|---|
| `hil_map.json` | Canonical map: per-sensor channel, address, jumper/solder, driver, attached, PR#933. **Generated — commit it.** |
| `build_map.py` | One-time export: imports the submodule generator, merges `overlay.json`, writes `hil_map.json`, injects `sensor-coach.html`. |
| `overlay.json` | Firmware-side facts the component data lacks: driver names, currently-attached flags, PR #933 membership, notes. |
| `make_hil_pdf.py` | Renders `hil_sensor_attachment_guide.pdf` from the map (soldering section + per-channel attachment list). |
| `sensor-coach.html` | Claude-powered **voice** helper: say a sensor, hear its channel + soldering. Map injected from `hil_map.json`. |
| `vendor/Wippersnapper_Components` | Submodule → `tyeth-ai-assisted/Wippersnapper_Components @ add/hil-i2c-generator` (the generator + component definitions). |
| `.claude/skills/hil-sensor-map/` | Skill documenting the regenerate/import/spreadsheet workflow. |

## Quick start

```sh
git clone --recurse-submodules <this repo>
pip install openpyxl fpdf2
python build_map.py          # -> hil_map.json + injects sensor-coach.html
python make_hil_pdf.py       # -> hil_sensor_attachment_guide.pdf
# open sensor-coach.html in Chrome/Edge, paste an Anthropic API key, hold the mic
```

If you cloned without `--recurse-submodules`: `git submodule update --init --recursive`.

See [`.claude/skills/hil-sensor-map/SKILL.md`](.claude/skills/hil-sensor-map/SKILL.md) for the
full workflow, including how to maintain the browsable spreadsheet copy separately from the JSON.

## Sensor Coach (voice app)

Open `sensor-coach.html` in a Chromium browser, paste your Anthropic API key (kept only in
`localStorage`), then hold the mic (or press Space) and say e.g. *"I've got the SGP41"* or
*"the three INAs and a BMP585"*. It speaks back the mux channel, address, and any soldering,
and shows a card per sensor (amber = needs soldering, green = already attached). It calls the
Claude API directly from the browser; the placement map is the only source of truth, so it
matches names but never invents a channel. Model is `claude-opus-4-8` (a one-line `MODEL`
const switches to `claude-haiku-4-5` for faster turns).
