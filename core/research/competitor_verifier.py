import json
import re
from pathlib import Path
from urllib.parse import urlparse

import requests

from core.config.paths import COMPETITOR_SIGNAL_DIR


class CompetitorVerifier:
    """
    Lightweight validation layer.

    Goals:
    - validate links
    - detect product-page-like signals
    - extract social links from official website if present
    - compute auto trust
    """

    SOCIAL_PATTERNS = {
        "facebook": r"https?://(?:www\.)?facebook\.com/[^\"'\s>]+",
        "instagram": r"https?://(?:www\.)?instagram\.com/[^\"'\s>]+",
        "tiktok": r"https?://(?:www\.)?tiktok\.com/[^\"'\s>]+",
    }

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

    def _is_live(self, response):
        return bool(response is not None and response.status_code < 400)

    def _extract_price_signals(self, html):
        if not html:
            return []

        patterns = [
            r"\$\s?\d+(?:\.\d{2})?",
            r"USD\s?\d+(?:\.\d{2})?",
        ]

        matches = []
        for pattern in patterns:
            matches.extend(re.findall(pattern, html, flags=re.IGNORECASE))

        return list(dict.fromkeys(matches))[:5]

    def _has_product_signal(self, html):
        if not html:
            return False

        keywords = [
            "add to cart",
            "buy now",
            "price",
            "coffee",
            "instant",
            "espresso",
            "pod",
            "capsule",
        ]
        html_l = html.lower()
        return sum(1 for kw in keywords if kw in html_l) >= 3

    def _extract_social_links(self, html):
        found = {}
        if not html:
            return found

        for key, pattern in self.SOCIAL_PATTERNS.items():
            match = re.search(pattern, html, flags=re.IGNORECASE)
            found[key] = match.group(0) if match else ""

        return found

    def _classify_trust(self, flags):
        score = 0.0

        if flags.get("website_alive"):
            score += 0.30
        if flags.get("has_price"):
            score += 0.25
        if flags.get("has_product_signal"):
            score += 0.25
        if flags.get("social_found_from_website"):
            score += 0.10
        if flags.get("amazon_alive"):
            score += 0.10

        if score >= 0.75:
            level = "high"
        elif score >= 0.45:
            level = "medium"
        else:
            level = "low"

        return level, round(score, 2)

    def verify_competitor(self, _id, competitor):
        brand_name = competitor.get("brand_name", "")
        product_name = competitor.get("product_name", "")
        product_link = competitor.get("product_link", "")

        website_resp = self._safe_get(product_link)
        website_alive = self._is_live(website_resp)
        html = website_resp.text if website_resp and website_alive else ""

        price_signals = self._extract_price_signals(html)
        has_price = len(price_signals) > 0
        has_product_signal = self._has_product_signal(html)
        social_links = self._extract_social_links(html)

        # Amazon fallback: if competitor link itself is Amazon, count as alive
        domain = urlparse(product_link).netloc.lower() if product_link else ""
        amazon_alive = website_alive and "amazon." in domain

        social_found_from_website = any(bool(v) for v in social_links.values())

        validation_flags = {
            "website_alive": website_alive,
            "has_price": has_price,
            "has_product_signal": has_product_signal,
            "amazon_alive": amazon_alive,
            "social_found_from_website": social_found_from_website,
        }

        trust_level, trust_score = self._classify_trust(validation_flags)

        payload = {
            "brand_name": brand_name,
            "product_name": product_name,
            "product_type": competitor.get("product_type", ""),
            "product_link": product_link,
            "price_range": competitor.get("price_range", ""),
            "reason": competitor.get("reason", ""),
            "website_link": product_link if website_alive else "",
            "amazon_link": product_link if amazon_alive else "",
            "facebook_link": social_links.get("facebook", ""),
            "instagram_link": social_links.get("instagram", ""),
            "tiktok_link": social_links.get("tiktok", ""),
            "validation_flags": validation_flags,
            "auto_trust_level": trust_level,
            "auto_trust_score": trust_score,
            "price_signals": price_signals,
            "confirm_status": "pending",
            "confirmed_by": "",
            "confirmed_at": "",
            "notes": "",
        }

        slug = self._slugify(f"{brand_name}_{product_name}")
        out_path = self.signal_dir / f"{_id}_{slug}_verification.json"
        self._save_json(out_path, payload)

        return payload