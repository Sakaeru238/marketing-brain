import json
import re
from pathlib import Path
from typing import Dict, Iterable, List


class OrganicLearningMemoryStore:
    """
    Local JSONL organic learning store.

    Folder structure:
      data/knowledge/organic_learning/{brand_id}/{brand_id}_{page_id}.jsonl

    Upsert key for reruns:
      date + facebook_post_id
    """

    def __init__(self, root_dir: str = "data/knowledge/organic_learning"):
        self.root_dir = Path(root_dir)

    def _safe_component(self, value) -> str:
        value = str(value or "unknown").strip()
        value = re.sub(r"[^A-Za-z0-9._-]+", "_", value)
        return value or "unknown"

    def _file_for(self, brand_id: str, page_id: str) -> Path:
        brand = self._safe_component(brand_id)
        page = self._safe_component(page_id)
        return self.root_dir / brand / f"{brand}_{page}.jsonl"

    def _record_identity(self, record: Dict) -> str:
        return f"{record.get('date', '')}|{record.get('facebook_post_id', '')}"

    def _read_existing(self, path: Path) -> List[Dict]:
        if not path.exists():
            return []
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
        return rows

    def _write_jsonl(self, path: Path, rows: Iterable[Dict]):
        path.parent.mkdir(parents=True, exist_ok=True)
        content = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
        if content:
            content += "\n"
        path.write_text(content, encoding="utf-8")

    def _to_learning_record(self, result: Dict) -> Dict:
        brand_id = result.get("brand_id", "")
        niche_id = result.get("niche_id", "")
        campaign_id = result.get("campaign_id", "")
        organic_run_id = result.get("organic_run_id", "")
        learning_key = f"{brand_id}_{niche_id}_{campaign_id}_{organic_run_id}"

        return {
            "learning_key": learning_key,
            "date": result.get("date", ""),
            "brand_id": brand_id,
            "niche_id": niche_id,
            "page_id": result.get("page_id", ""),
            "campaign_id": campaign_id,
            "organic_run_id": organic_run_id,
            "platform_id": result.get("platform_id", ""),
            "post_id": result.get("post_id", ""),
            "facebook_post_id": result.get("facebook_post_id", ""),
            "metrics": {
                "likes": result.get("likes", 0),
                "comments": result.get("comments", 0),
                "shares": result.get("shares", 0),
                "reach": result.get("reach", 0),
                "impressions": result.get("impressions", 0),
                "clicks": result.get("clicks", 0),
                "engagement_rate": result.get("engagement_rate", 0),
            },
            # Local JSONL memory stays in English so the next organic generation job learns from a canonical language layer.
            "ai_result_summary": result.get("ai_result_summary_en") or result.get("ai_result_summary", ""),
            "ai_learning": result.get("ai_learning_en") or result.get("ai_learning", ""),
            "ai_next_action": result.get("ai_next_action_en") or result.get("ai_next_action", ""),
            "collected_at": result.get("collected_at", ""),
        }


    def load_recent(self, brand_id: str, page_id: str, limit: int = 20) -> List[Dict]:
        path = self._file_for(brand_id, page_id)
        rows = self._read_existing(path)
        rows.sort(key=lambda x: (str(x.get("date", "")), str(x.get("collected_at", ""))), reverse=True)
        return rows[: max(0, int(limit))]

    def upsert_from_results(self, results: List[Dict]) -> Dict:
        grouped = {}
        for result in results:
            brand_id = result.get("brand_id", "")
            page_id = result.get("page_id", "")
            if not brand_id or not page_id:
                continue
            grouped.setdefault((brand_id, page_id), []).append(self._to_learning_record(result))

        summary = {"files_updated": [], "records_written": 0}
        for (brand_id, page_id), new_rows in grouped.items():
            path = self._file_for(brand_id, page_id)
            existing_rows = self._read_existing(path)
            indexed = {self._record_identity(row): row for row in existing_rows}
            for row in new_rows:
                indexed[self._record_identity(row)] = row
            final_rows = list(indexed.values())
            final_rows.sort(key=lambda x: (str(x.get("date", "")), str(x.get("facebook_post_id", ""))))
            self._write_jsonl(path, final_rows)
            summary["files_updated"].append(str(path))
            summary["records_written"] += len(new_rows)
        return summary
