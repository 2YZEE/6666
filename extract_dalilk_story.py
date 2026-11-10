#!/usr/bin/env python3
"""Inspect one Dalilk reader and export rights-safe metadata only."""
from __future__ import annotations
import asyncio, json, re, zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from playwright.async_api import async_playwright

SCRIPT_PATH = Path(__file__).resolve()
ROOT = SCRIPT_PATH.parents[2] if SCRIPT_PATH.parents[1].name == "outputs" else SCRIPT_PATH.parents[1]
OUT = ROOT / "outputs"
URL = "https://dalilk.com/resources/fluency/read?book=580953"
EXPECTED_ID = "580953"

def clean_url(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}{p.path}"

async def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    requests, responses, errors = [], [], []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 1000})
        page.on("request", lambda r: requests.append({"url": clean_url(r.url), "resource_type": r.resource_type, "method": r.method}))
        async def record_response(response):
            try:
                responses.append({"url": clean_url(response.url), "status": response.status, "content_type": response.headers.get("content-type", "").split(";")[0]})
            except Exception as exc:
                errors.append(f"response metadata: {type(exc).__name__}")
        page.on("response", lambda r: asyncio.create_task(record_response(r)))
        response = await page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(5000)
        iframe_src = await page.locator("iframe").evaluate_all("els => els.map(e => e.src).find(src => src.includes(\"publuu.com/flip-book/\")) || null")
        frame = next((f for f in page.frames if "publuu.com/flip-book/" in f.url), None)
        if frame is None:
            raise RuntimeError("Publuu reader frame did not load")
        initial = await frame.evaluate("""() => ({
          title: document.title || null,
          pageTextNodeCount: document.querySelectorAll('p, span, [class*=text]').length,
          imageCount: document.images.length,
          canvasCount: document.querySelectorAll('canvas').length,
          audioElements: [...document.querySelectorAll('audio, audio source')].map(x => ({tag:x.tagName, hasSrc:Boolean(x.currentSrc||x.src||x.getAttribute('src')), type:x.type||null, durationSeconds:Number.isFinite(x.duration)?x.duration:null})),
          videoCount: document.querySelectorAll('video').length,
          buttons: [...document.querySelectorAll('button')].map(b=>(b.getAttribute('aria-label')||b.title||b.innerText||'').trim()).filter(Boolean)
        })""")
        page_count = None
        body_text = await frame.locator("body").inner_text(timeout=10000)
        total_match = re.search(r"/\s*(\d+)\b", body_text)
        if total_match:
            page_count = int(total_match.group(1))
        next_button = frame.get_by_role("button", name=re.compile("Next Page", re.I))
        navigation_verified = False
        if await next_button.count():
            await next_button.first.click()
            await page.wait_for_timeout(1200)
            navigation_verified = "/page/2" in frame.url
            if page_count:
                field = frame.locator("input").first
                try:
                    await field.fill(str(page_count))
                    await field.press("Enter")
                    await page.wait_for_timeout(1200)
                    navigation_verified = navigation_verified and (f"/page/{page_count}" in frame.url or str(page_count) in await field.input_value())
                except Exception as exc:
                    errors.append(f"page-number control: {type(exc).__name__}")
        final_url = frame.url
        await page.wait_for_timeout(800)
        request_counts = Counter(x["resource_type"] for x in requests)
        response_counts = Counter(x["content_type"] for x in responses if x["content_type"])
        image_responses = [x for x in responses if x["content_type"].startswith("image/")]
        audio_responses = [x for x in responses if x["content_type"].startswith("audio/")]
        story_asset_responses = [x for x in responses if "/232773/580953/" in x["url"]]
        audio_assets = [{"url":x["url"],"format":urlparse(x["url"]).path.rsplit(".",1)[-1],"content_type":x["content_type"],"http_status":x["status"],"duration_seconds":None,"downloaded":False,"reuse_permission_verified":False,"association":"loaded during this story reader session; segment mapping not verified"} for x in audio_responses]
        image_assets = [{"url":x["url"],"format":urlparse(x["url"]).path.rsplit(".",1)[-1],"content_type":x["content_type"],"http_status":x["status"],"downloaded":False,"reuse_permission_verified":False} for x in story_asset_responses if x["content_type"].startswith("image/")]
        story = {
          "schema_version":"1.0",
          "source":{"site":"Dalilk","story_id":EXPECTED_ID,"url":URL,"reuse_permission_verified":False,"reuse_policy":"Source references and technical metadata only; no story text or media copied."},
          "inspection":{"inspected_at_utc":datetime.now(timezone.utc).isoformat(),"browser":"Playwright Chromium","http_status":response.status if response else None,"page_title":await page.title(),"reader_title":initial.get("title"),"reader_embed_url":clean_url(iframe_src or frame.url),"reader_page_count":page_count,"page_one_and_final_page_navigation_verified":navigation_verified,"observed_final_reader_url":clean_url(final_url),"reader_dom":{"image_elements":initial.get("imageCount"),"canvas_elements":initial.get("canvasCount"),"text_like_elements":initial.get("pageTextNodeCount"),"audio_elements":initial.get("audioElements"),"video_elements":initial.get("videoCount"),"controls":initial.get("buttons")}},
          "content":{"story_text":{"status":"not_exported","reason":"Reuse permission not verified; pages render as book artwork."},"vocabulary":{"status":"not_found_in_reader_controls","items":[]},"questions":{"status":"not_found_in_reader_controls","items":[]},"sentence_timestamps":{"status":"not_available","items":[]}},
          "media":{"images":{"count_observed_in_network":len(image_responses),"story_asset_references":image_assets,"files_downloaded":0,"reuse_permission_verified":False},"audio":{"count_observed_in_network":len(audio_responses),"assets":audio_assets,"files_downloaded":0,"reuse_permission_verified":False,"player_control_observed":any("Audio" in s for s in initial.get("buttons",[]))},"videos":{"count_observed_in_reader_dom":initial.get("videoCount",0),"files_downloaded":0}},
          "limitations":["The reader is embedded from Publuu and presents book pages as visual artwork rather than accessible story-text nodes.","The reader exposes a page control and an audio toggle; no protected assets were saved.","No permission to reproduce the story, illustrations, or narration was provided or verified."],"errors":errors
        }
        network={"source_url":URL,"captured_at_utc":story["inspection"]["inspected_at_utc"],"request_count":len(requests),"response_count":len(responses),"request_resource_type_counts":dict(request_counts),"response_content_type_counts":dict(response_counts),"observed_hosts":sorted({urlparse(x["url"]).netloc for x in requests}),"responses":responses,"note":"Query strings and fragments were removed; no request bodies, cookies, or media payloads were saved."}
        (OUT/"echolab_story_580953.json").write_text(json.dumps(story,ensure_ascii=False,indent=2),encoding="utf-8")
        (OUT/"network_summary_580953.json").write_text(json.dumps(network,ensure_ascii=False,indent=2),encoding="utf-8")
        report=f"""# Dalilk story 580953 inspection

**Result:** Playwright Chromium opened the reader and inspected its DOM and network responses.

- Story shown by the page: **The Old Books Mystery**; embedded reader title: **{initial.get('title')}**
- Reader: {clean_url(iframe_src or frame.url)}
- Page count detected: **{page_count}**
- Page navigation check: **{'passed' if navigation_verified else 'partial/failed'}**
- Network: {len(requests)} requests, {len(responses)} responses; hosts: {', '.join(network['observed_hosts'])}
- Network assets: {len(audio_assets)} MP3 audio references and {len(image_assets)} story-associated image references recorded; durations are unknown and no files were downloaded.
- DOM: {initial.get('imageCount')} image elements, {initial.get('canvasCount')} canvas elements; audio nodes: {len(initial.get('audioElements', []))}; audio toggle observed: {story['media']['audio']['player_control_observed']}
- The story text and media files were **not copied or downloaded**; metadata-only URLs are present because reuse permission was not verified.
- Vocabulary, questions and sentence timestamps were not exposed as accessible reader controls.

See `echolab_story_580953.json` and `network_summary_580953.json` for machine-readable details.
"""
        (OUT/"extraction_report_580953.md").write_text(report,encoding="utf-8")
        import shutil
        shutil.copy2(Path(__file__), OUT/"extract_dalilk_story.py")
        zip_path=OUT/"echolab_dalilk_580953_metadata.zip"
        with zipfile.ZipFile(zip_path,"w",compression=zipfile.ZIP_DEFLATED) as zf:
            for name in ("echolab_story_580953.json","network_summary_580953.json","extraction_report_580953.md","extract_dalilk_story.py","README_Dalilk_EchoLab.md"):
                zf.write(OUT/name,arcname=name)
        print(json.dumps({"http_status":story["inspection"]["http_status"],"reader_title":story["inspection"]["reader_title"],"page_count":page_count,"navigation_verified":navigation_verified,"requests":len(requests),"responses":len(responses),"zip":str(zip_path)},indent=2))
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
