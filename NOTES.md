# Ideas / future

## On-device inference — Gemma on the Android phone (future)

Today Sensor Coach calls the Anthropic API from the phone browser (API key entered
at runtime). A future version could run a **small local model (e.g. Gemma) on the
Android device that's browsing the microsite** — no API key, no network, works
offline at the bench, zero per-query cost.

Paths to explore:

- **In the browser (PWA):** MediaPipe **LLM Inference Web API** (WebGPU) or
  `transformers.js` running a quantised **Gemma** in the page. Fully client-side;
  the trade-off is a large one-time model download + WebGPU support on the phone.
- **Native Android app:** MediaPipe **LLM Inference** (`gemma-*.task`) or
  **Google AI Edge / Gemini Nano** (AICore) for a proper offline "Sensor Coach"
  app. The page's `hil_map.json` + system prompt port over directly.
- **Hybrid:** local Gemma for the common name→slot lookup (cheap, offline); fall
  back to the cloud model only for fuzzy/ambiguous strands.

Why it's cheap to do later: the **map (`hil_map.json`) and the system prompt are
already the only inputs**, and the output is a small fixed JSON schema — so the
only real work is swapping the inference backend behind the same `ask()` call.
A `MODEL = "local-gemma"` branch in `sensor-coach.html` that routes to an
on-device runner instead of `fetch(api.anthropic.com)` would be the seam.

Voice already uses the device's built-in `speechSynthesis`, so the spoken side is
already fully on-device and offline.
