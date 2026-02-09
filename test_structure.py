import pandas as pd
import os
from rank_sample import REQUIRED_COLUMNS, RANKING_COLUMNS, process_file, WeightsConfig, SeniorityPreference, KeywordConfig, SeniorityMode, SeniorityModeType

def test_output_structure():
    print("--- Testing Output Structure ---")
    
    # Create dummy input CSV
    dummy_data = {col: ["test_val"] for col in REQUIRED_COLUMNS}
    dummy_data['id'] = ['123']
    dummy_data['connections_count'] = [500]
    dummy_data['followers_count'] = [200]
    dummy_data['management_level_1'] = ['Manager']
    dummy_data['active_experience_title'] = ['Manager']
    
    dummy_df = pd.DataFrame(dummy_data)
    dummy_csv = "test_structure_input.csv"
    dummy_df.to_csv(dummy_csv, index=False)
    
    # Run process_file (headless)
    wc = WeightsConfig(0.2, 0.2, 0.2, 0.2, 0.2)
    sp = SeniorityPreference(False, [SeniorityMode(SeniorityModeType.BALANCED)])
    kc = KeywordConfig()
    export_opts = {'csv': True}
    
    try:
        process_file(dummy_csv, wc, sp, kc, export_opts)
        
        output_csv = "ranked_output.csv"
        if not os.path.exists(output_csv):
            print("FAILED: Output CSV not created.")
            return

        out_df = pd.read_csv(output_csv)
        print(f"Output Columns: {list(out_df.columns)}")
        
        expected_cols = REQUIRED_COLUMNS + RANKING_COLUMNS
        
        # Check presence and order
        missing = [c for c in expected_cols if c not in out_df.columns]
        if missing:
            print(f"FAILED: Missing columns: {missing}")
        else:
            # Check exact order of the relevant columns
            out_rel = [c for c in out_df.columns if c in expected_cols]
            if out_rel == expected_cols:
                print("PASSED: Output columns match expected order exactly.")
            else:
                print("FAILED: Order mismatch.")
                print(f"Expected: {expected_cols}")
                print(f"Got:      {out_rel}")

    finally:
        # Cleanup
        if os.path.exists(dummy_csv): os.remove(dummy_csv)
        if os.path.exists("ranked_output.csv"): os.remove("ranked_output.csv")

if __name__ == "__main__":
    test_output_structure()
