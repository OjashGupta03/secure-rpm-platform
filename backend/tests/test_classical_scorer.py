from app.ai.classical.scorer import score_measurement_window


def test_normal_value_within_baseline_scores_low():
    history = {"heart_rate": [70, 71, 69, 72, 70, 71, 69, 70]}
    result = score_measurement_window(
        current_type="heart_rate", current_value=71, history_by_type=history, latest_by_type={}
    )
    assert result.risk_level == "normal"
    assert result.classical_score < 0.4


def test_extreme_spike_scores_high():
    history = {"heart_rate": [70, 71, 69, 72, 70, 71, 69, 70]}
    result = score_measurement_window(
        current_type="heart_rate", current_value=180, history_by_type=history, latest_by_type={}
    )
    assert result.risk_level in ("elevated", "high")
    assert "heart rate" in result.explanation


def test_insufficient_history_scores_zero():
    result = score_measurement_window(
        current_type="heart_rate", current_value=200, history_by_type={"heart_rate": [70, 71]}, latest_by_type={}
    )
    assert result.classical_score == 0.0
