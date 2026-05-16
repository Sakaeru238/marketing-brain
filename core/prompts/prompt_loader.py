from pathlib import Path


class PromptLoader:
    def load(self, path):
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Prompt not found: {p}")
        return p.read_text(encoding="utf-8")

    def render(self, path, replacements):
        text = self.load(path)
        for key, value in replacements.items():
            text = text.replace("{{" + key + "}}", value)
        return text
