from pathlib import Path


class CustomerFeedbackLoader:
    """
    Loads raw customer feedback / Voice of Customer text.

    This loader is intentionally simple:
    - It reads a plain .txt file.
    - It returns raw text.
    - It does not parse, summarize, clean, or transform the feedback.

    Parsing and extraction should happen inside the Strategy prompt,
    because Claude needs the original customer language.
    """

    def __init__(self, feedback_file="data/input/customer_feedback_raw.txt"):
        self.feedback_file = Path(feedback_file)

    def load(self):
        """
        Return raw customer feedback text.

        If the file does not exist or is empty, return an empty string.
        This keeps the main pipeline safe when VOC data is not available.
        """

        if not self.feedback_file.exists():
            return ""

        text = self.feedback_file.read_text(encoding="utf-8").strip()

        if not text:
            return ""

        return text

    def exists(self):
        """
        Check whether the feedback file exists.
        """

        return self.feedback_file.exists()

    def has_content(self):
        """
        Check whether the feedback file exists and contains non-empty text.
        """

        if not self.feedback_file.exists():
            return False

        text = self.feedback_file.read_text(encoding="utf-8").strip()
        return bool(text)
