import pandas as pd
from rank_sample import SeniorityRawEngine, SeniorityTransformationEngine, KeywordEngine, KeywordConfig
from rank_sample import SeniorityMode, SeniorityModeType, SeniorityPreference

def test_new_engines():
    print("--- Testing New Engine Logic ---")
    
    # 1. Keyword Engine (Phrase Aware)
    print("\n[Keyword Engine]")
    ke = KeywordEngine(
        good_list=["MS&T", "Process Development"], 
        bad_list=["Small molecule", "Intern"]
    )
    
    # Matches "Process Development" exactly as phrase
    row1 = pd.Series({"active_experience_title": "Head of Process Development"})
    score1, g1, b1, _, _ = ke.compute_score(row1, KeywordConfig())
    print(f"  'Head of Process Development': Good={g1}, Bad={b1} -> Score={score1}")
    assert g1 == 1
    
    # "Process" and "Development" separately shouldn't match "Process Development"
    # Test normalization: "MS&T" should match "MS&T" (normalized to "ms t")
    row2 = pd.Series({"active_experience_description": "Worked in MS&T department"})
    score2, g2, b2, _, _ = ke.compute_score(row2, KeywordConfig())
    print(f"  'Worked in MS&T department': Good={g2} -> Score={score2}")
    assert g2 == 1

    # 2. Seniority Engine (Stage 1 & 2)
    print("\n[Seniority Engine]")
    raw_eng = SeniorityRawEngine()
    trans_eng = SeniorityTransformationEngine()
    
    # Raw
    row_vp = pd.Series({"active_experience_title": "VP of Sales", "management_level_1": "VP"})
    raw_vp, tier_vp = raw_eng.compute_raw(row_vp)
    print(f"  VP Raw: {raw_vp} ({tier_vp})")
    assert raw_vp >= 80

    row_intern = pd.Series({"active_experience_title": "Intern", "management_level_1": "Intern"})
    raw_intern, tier_intern = raw_eng.compute_raw(row_intern)
    print(f"  Intern Raw: {raw_intern} ({tier_intern})")
    assert raw_intern <= 20

    # Transform: Junior Mode (Intern should be high)
    mode_j = SeniorityMode(SeniorityModeType.PREFER_JUNIOR)
    pref_j = SeniorityPreference(False, [mode_j])
    val_j = trans_eng.compute_component(raw_intern, pref_j)
    print(f"  Intern in PREFER_JUNIOR: {val_j}")
    assert val_j >= 80

    # Transform: Multi Mode (Mid + Junior)
    modes = [
        SeniorityMode(SeniorityModeType.PREFER_MID, {'t': 50}), # Intern(10)->Diff(40)->20
        SeniorityMode(SeniorityModeType.PREFER_JUNIOR) # Intern(10)->90
    ]
    # Average: (20 + 90) / 2 = 55
    pref_multi = SeniorityPreference(True, modes, "average")
    val_multi = trans_eng.compute_component(raw_intern, pref_multi)
    print(f"  Intern in Multi (Mid+Junior): {val_multi}")
    assert 50 <= val_multi <= 60

    print("\nALL TESTS PASSED!")

if __name__ == "__main__":
    test_new_engines()
