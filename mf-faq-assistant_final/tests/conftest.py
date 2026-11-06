import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.pop("GROQ_API_KEY", None)  # tests run offline and deterministic (extractive mode)


@pytest.fixture(scope="session")
def cases():
    return json.loads((ROOT / "evaluation" / "sample_questions.json").read_text())
