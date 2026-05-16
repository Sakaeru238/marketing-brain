import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from core.pipeline.master_pipeline import MasterPipeline


def test_step_56():

    pipeline = MasterPipeline()

    learning = pipeline.learn_from_claude()

    print("LEARNING RESULT:")
    print(learning)


if __name__ == "__main__":
    test_step_56()
