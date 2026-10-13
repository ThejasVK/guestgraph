from pathlib import Path

import pytest

from guestgraph.generate import generate
from guestgraph.warehouse import build


@pytest.fixture(scope="session")
def data_dir(tmp_path_factory) -> Path:
    d = tmp_path_factory.mktemp("data")
    generate(d, n_people=400, days=90, seed=3)
    return d


@pytest.fixture(scope="session")
def built(data_dir):
    return build(data_dir / "loyalty_members.csv", data_dir / "transactions.csv")
