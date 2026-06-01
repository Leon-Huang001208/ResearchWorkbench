from services.dynamic_factor_visualization_service import DynamicFactorVisualizationService


def test_dynamic_factor_visualization_overview_contains_alpha_control_room_sections():
    overview = DynamicFactorVisualizationService().build_overview()

    assert overview["success"] is True
    assert overview["data_mode"] == "demo"
    assert len(overview["closed_loop_steps"]) >= 5
    assert overview["factor_matrix"]["subjects"]
    assert overview["factor_matrix"]["factors"]
    assert overview["evaluations"]
    assert overview["dynamic_weights"]["weights"]
    assert overview["factor_scores"]
    assert overview["fusion_results"]

    top = overview["fusion_results"][0]
    assert "subject_id" in top
    assert 0 <= top["final_alpha_score"] <= 1
    assert top["top_contributors"]
