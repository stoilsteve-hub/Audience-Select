import pandas as pd
from rank_sample import build_ranking_reason, SeniorityModeType

def test_explainability():
    print("--- Testing Explainability Logic ---")
    
    # Mock row 1: Junior target, good keywords
    row1 = pd.Series({
        'seniority_component': 85.5,
        'seniority_mode_type': 'single',
        'seniority_modes_selected': "['prefer_junior']",
        'keyword_score': 64.0,
        'good_matches': 'MSAT;DSP',
        'connections_score_norm': 80.0,
        'followers_score_norm': 20.0,
        'company_size_score': 10.0
    })
    
    reason1 = build_ranking_reason(row1)
    print(f"\nRow 1 Reason:\n{reason1}")
    
    assert "Seniority boost: 85 (Junior-target)" in reason1
    assert "Keyword relevance: 64 (matched: MSAT, DSP)" in reason1
    assert "High network influence" in reason1
    
    # Mock row 2: Balanced, no keywords, large company
    row2 = pd.Series({
        'seniority_component': 50.0,
        'seniority_mode_type': 'single',
        'seniority_modes_selected': "['balanced']",
        'keyword_score': 0.0,
        'good_matches': '',
        'connections_score_norm': 10.0,
        'followers_score_norm': 10.0,
        'company_size_score': 80.0
    })
    
    reason2 = build_ranking_reason(row2)
    print(f"\nRow 2 Reason:\n{reason2}")
    
    assert "Seniority score: 50 (Balanced)" in reason2
    assert "Keyword" not in reason2
    assert "Large company profile" in reason2

    print("\nALL EXPLAINABILITY CHECKS PASSED!")

if __name__ == "__main__":
    test_explainability()
