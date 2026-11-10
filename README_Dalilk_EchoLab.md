# Dalilk → EchoLab: story 580953

This package contains verified, rights-safe metadata from a Playwright Chromium inspection of the Dalilk reader.

## Files

- `echolab_story_580953.json` — EchoLab-friendly story record and verified availability/status fields.
- `network_summary_580953.json` — Sanitized request/response metadata (query strings removed; no payloads/cookies).
- `extraction_report_580953.md` — Human-readable findings and limitations.
- `extract_dalilk_story.py` — Re-runnable inspector. It does not copy or download story text or media.

## Run

Install Playwright and its Chromium browser, then run:

```sh
python3 -m pip install playwright
python3 -m playwright install chromium
python3 extract_dalilk_story.py
```

The script writes the JSON and report to this project’s `outputs/` directory and rebuilds the ZIP archive.

## Rights and coverage

No reuse permission was verified. The export therefore keeps source references and technical metadata only. It does not include the story text, images, or audio files. The visible reader exposed a 22-page book and an audio toggle; vocabulary, quiz questions, and sentence timestamps were not exposed as accessible reader controls in this inspection.
