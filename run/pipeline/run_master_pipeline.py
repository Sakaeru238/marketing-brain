from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.pipeline.master_pipeline import MasterPipeline


def main():
    result = MasterPipeline().run()
    print(result)


if __name__ == "__main__":
    main()
