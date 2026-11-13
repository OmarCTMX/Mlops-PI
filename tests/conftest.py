import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cvmon import db  # noqa: E402
from cvmon.config import config_hash, load_config  # noqa: E402


@pytest.fixture()
def cfg():
    return copy.deepcopy(load_config("config/config.yaml"))


@pytest.fixture()
def conn(tmp_path, cfg):
    c = db.open_db(tmp_path / "t.db")
    c.execute("INSERT INTO config_snapshots VALUES (?,?,?)", (config_hash(cfg), db.jdump(cfg), db.utc_iso()))
    c.execute(
        "INSERT INTO runs(run_id,scenario,started_at,started_epoch,config_hash,source_id,source_type,model_id,"
        "model_version,model_sha256,model_identity_json) VALUES ('T-1','T',?,1000.0,?,'s','sequence','m','v','x','{}')",
        (db.utc_iso(1000.0), config_hash(cfg)),
    )
    return c
