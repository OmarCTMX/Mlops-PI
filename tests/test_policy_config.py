import pytest

from cvmon.config import ConfigError, apply_overrides, config_hash, validate_thresholds
from cvmon.policy import classify_zone


@pytest.mark.parametrize("score,zone", [
    (1.0, "accepted"), (0.80, "accepted"), (0.7999, "doubt"), (0.60, "doubt"),
    (0.5999, "low"), (0.0, "low"),
])
def test_zonas_ejemplo_060_080(score, zone):
    assert classify_zone(score, 0.60, 0.80) == zone


def test_zonas_con_umbrales_distintos_a_los_de_ejemplo():
    assert classify_zone(0.45, 0.30, 0.50) == "doubt"
    assert classify_zone(0.50, 0.30, 0.50) == "accepted"
    assert classify_zone(0.29, 0.30, 0.50) == "low"


@pytest.mark.parametrize("bad", [None, float("nan"), float("inf"), -0.1, 1.1, "0.5", True])
def test_sin_puntuacion_valida_no_es_zona(bad):
    assert classify_zone(bad, 0.4, 0.7) is None


@pytest.mark.parametrize("lo,up", [(0.8, 0.6), (0.5, 0.5), (-0.1, 0.5), (0.2, 1.1)])
def test_umbrales_invalidos(lo, up):
    with pytest.raises(ConfigError):
        validate_thresholds(lo, up)


def test_umbrales_limite_validos():
    validate_thresholds(0.0, 1.0)
    validate_thresholds(0.0, 0.01)


def test_config_hash_cambia_con_umbral_y_overrides(cfg):
    h0 = config_hash(cfg)
    apply_overrides(cfg, ["thresholds.upper=0.75"])
    assert config_hash(cfg) != h0
    with pytest.raises(ConfigError):
        apply_overrides(cfg, ["thresholds.lower=0.9"])
