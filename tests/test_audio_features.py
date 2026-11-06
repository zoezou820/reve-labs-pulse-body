import numpy as np

from render_pulse_body import FPS, audio_features


def test_audio_features_match_video_frame_count():
    sample_rate = 48000
    audio = np.zeros(sample_rate * 2, dtype=np.float32)
    features = audio_features(audio, sample_rate)
    assert features["n"] == FPS * 2
    assert len(features["hit"]) == FPS * 2


def test_transient_produces_finite_features():
    sample_rate = 48000
    audio = np.zeros(sample_rate, dtype=np.float32)
    audio[sample_rate // 2:sample_rate // 2 + 128] = 1.0
    features = audio_features(audio, sample_rate)
    assert np.isfinite(features["hit"]).all()
    assert np.isfinite(features["tail"]).all()
