import json
import re
from pathlib import Path

import requests

from core.config.paths import COMPETITOR_SIGNAL_DIR


class CompetitorSignalCollector:
    """
    Collect lightweight raw signals from verified product pages.

    V1 scope:
    - title
    - meta description
    - visible price snippets
    - bullet-like text lines
    """

    def __init__(self):
        self.signal_dir = Path(COMPETITOR_SIGNAL_DIR)

    def _save_json(self, path: Path, payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _slugify(self, text):
        text = (text or "").lower().strip()
        text = re.sub(r"[^a-z0-9]+", "_", text)
        text = re.sub(r"_+", "_", text).strip("_")
        return text or "item"

    def _safe_get(self, url, timeout=12):
        if not url:
            return None
        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
                )
            }
            return requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        except Exception:
            return None

    def _strip_html(self, html):
        if not html:
            return ""
        html = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
        html = re.sub(r"<style[\s\S]*?</style>", " ", html, flags=re.IGNORECASE)
        html = re.sub(r"<noscript[\s\S]*?</noscript>", " ", html, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _extract_title(self, html):
        if not html:
            return ""
        match = re.search(r"<title>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
        return re.sub(r"\s+", " ", match.group(1)).strip() if match else ""

    def _extract_meta_description(self, html):
        if not html:
            return ""
        match = re.search(
            r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']',
            html,
            flags=re.IGNORECASE | re.DOTALL,
        )
        return re.sub(r"\s+", " ", match.group(1)).strip() if match else ""

    def _extract_price_snippets(self, html):
        if not html:
            return []
        matches = re.findall(r"\$\s?\d+(?:\.\d{2})?", html)
        return list(dict.fromkeys(matches))[:5]

    def _extract_text_lines(self, text):
        if not text:
            return []
        chunks = re.split(r"(?<=[\.\!\?])\s+", text)
        cleaned = []
        for chunk in chunks:
            chunk = chunk.strip()
            if len(chunk) < 25:
                continue
            cleaned.append(chunk)
        return cleaned[:15]

    def collect(self, _id, verified_item):
        product_link = verified_item.get("website_link") or verified_item.get("product_link")
        resp = self._safe_get(product_link)

        if not resp or resp.status_code >= 400:
            payload = {
                "status": "failed",
                "reason": "Could not load verified product page.",
                "website_copy_raw": [],
                "review_snippets_raw": [],
                "ad_copy_raw": [],
                "title": "",
                "meta_description": "",
                "price_snippets": [],
            }
        else:
            html = resp.text
            text = self._strip_html(html)
            lines = self._extract_text_lines(text)

            payload = {
                "status": "success",
                "reason": None,
                "title": self._extract_title(html),
                "meta_description": self._extract_meta_description(html),
                "price_snippets": self._extract_price_snippets(html),
                "website_copy_raw": lines[:8],
                "review_snippets_raw": [],  # V1: chưa scrape review riêng
                "ad_copy_raw": [],          # V1: chưa scrape ads riêng
            }

        slug = self._slugify(
            f"{verified_item.get('brand_name', '')}_{verified_item.get('product_name', '')}"
        )
        out_path = self.signal_dir / f"{_id}_{slug}_signals.json"
        self._save_json(out_path, payload)

        return payload