import pandas as pd
from pathlib import Path

from core.config.paths import DATA_DIR


class BrandIntakeLoader:
    """
    Load brand intake data từ Excel control panel.

    Nguồn dữ liệu chính:
    data/control_panels/marketing_brain_control_panel.xlsx

    Thiết kế:
    - đọc theo test_id trong sheet Test_Runs
    - join dữ liệu từ nhiều sheet:
        Brands
        Brand_Core_Truth
        Brand_Guardrails
        Products
        Product_Benefits
        Product_Usage
        Offers
        Audiences_Input
        Audiences_AI_Expanded
    """

    def __init__(self, workbook_path=None):
        if workbook_path is None:
            workbook_path = (
                DATA_DIR / "control_panels" / "marketing_brain_control_panel.xlsx"
            )

        self.workbook_path = Path(workbook_path)

        if not self.workbook_path.exists():
            raise FileNotFoundError(
                f"Không tìm thấy file Excel control panel: {self.workbook_path}"
            )

    # -----------------------------------------------------
    # INTERNAL HELPERS
    # -----------------------------------------------------

    def _read_sheet(self, sheet_name):
        df = pd.read_excel(self.workbook_path, sheet_name=sheet_name)
        df = df.where(pd.notnull(df), None)
        return df.to_dict(orient="records")

    def _find_one(self, rows, key, value):
        for row in rows:
            if row.get(key) == value:
                return row
        return None

    def _find_many(self, rows, key, value):
        return [row for row in rows if row.get(key) == value]

    def _normalize_bool(self, value):
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        return str(value).strip().lower() in {"true", "1", "yes", "y"}

    # -----------------------------------------------------
    # LOAD RAW TEST PACKAGE
    # -----------------------------------------------------

    def load_test_run_package(self, test_id):
        """
        Load toàn bộ package dữ liệu theo test_id.
        """

        brands = self._read_sheet("Brands")
        brand_truths = self._read_sheet("Brand_Core_Truth")
        brand_guardrails = self._read_sheet("Brand_Guardrails")
        products = self._read_sheet("Products")
        product_benefits = self._read_sheet("Product_Benefits")
        product_usage = self._read_sheet("Product_Usage")
        offers = self._read_sheet("Offers")
        audiences_input = self._read_sheet("Audiences_Input")
        audiences_ai = self._read_sheet("Audiences_AI_Expanded")
        test_runs = self._read_sheet("Runs")

        test_run = self._find_one(test_runs, "test_id", test_id)
        if not test_run:
            raise ValueError(f"Không tìm thấy test_id: {test_id}")

        brand_id = test_run["brand_id"]
        product_id = test_run["product_id"]
        offer_id = test_run["offer_id"]
        seed_audience_id = test_run["seed_audience_id"]
        ai_audience_id = test_run["ai_audience_id"]

        brand = self._find_one(brands, "brand_id", brand_id)
        if not brand:
            raise ValueError(f"Không tìm thấy brand_id: {brand_id}")

        product = self._find_one(products, "product_id", product_id)
        if not product:
            raise ValueError(f"Không tìm thấy product_id: {product_id}")

        offer = self._find_one(offers, "offer_id", offer_id)
        if not offer:
            raise ValueError(f"Không tìm thấy offer_id: {offer_id}")

        seed_audience = self._find_one(audiences_input, "audience_id", seed_audience_id)
        if not seed_audience:
            raise ValueError(f"Không tìm thấy seed_audience_id: {seed_audience_id}")

        # ưu tiên match đúng ID expanded audience
        ai_audience = self._find_one(
            audiences_ai, "expanded_audience_id", ai_audience_id
        )

        # fallback nếu file Test_Runs chưa sửa đúng ai_audience_id
        if not ai_audience:
            ai_candidates = [
                row
                for row in audiences_ai
                if row.get("brand_id") == brand_id
                and row.get("source_audience_id") == seed_audience_id
            ]
            ai_audience = ai_candidates[0] if ai_candidates else None

        package = {
            "test_run": test_run,
            "brand": brand,
            "brand_truths": self._find_many(brand_truths, "brand_id", brand_id),
            "brand_guardrails": self._find_many(brand_guardrails, "brand_id", brand_id),
            "product": product,
            "product_benefits": self._find_many(
                product_benefits, "product_id", product_id
            ),
            "product_usage": self._find_many(product_usage, "product_id", product_id),
            "offer": offer,
            "seed_audience": seed_audience,
            "ai_audience": ai_audience,
        }

        return package
