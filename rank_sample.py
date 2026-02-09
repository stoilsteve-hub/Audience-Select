import pandas as pd
import numpy as np
import re
import json
import os
import sys

# Optional dependency: tqdm
try:
    from tqdm import tqdm
    tqdm_available = True
except ImportError:
    tqdm_available = False
    # Simple shim if not available
    def tqdm(iterable, desc=None, **kwargs):
        if desc: print(f"{desc}...")
        return iterable
    tqdm.pandas = lambda **kwargs: None

# ==========================================
# README / INSTRUCTIONS
# ==========================================
#
# Audience Prioritization Tool
# ----------------------------
#
# DEPENDENCIES:
#   pip install pandas openpyxl numpy tqdm
#
# HOW TO RUN:
#   python rank_sample.py [optional_path_to_csv]
#
#   Example:
#   python rank_sample.py data.csv
#
# DESCRIPTION:
#   This tool ingests a CSV export from CoreSignal/Internal systems,
#   cleans and validates the data, calculates seniority and priority scores
#   based on user-defined weights, and exports a ranked list.
#
# ==========================================

# -----------------------------------------------------------------------------
# CONSTANTS & CONFIGURATION
# -----------------------------------------------------------------------------

REQUIRED_COLUMNS = [
    "id",
    "full_name",
    "linkedin_url",
    "active_experience_title",
    "management_level_1",
    "company_id_1",
    "company_name_1",
    "company_size_range_1",
    "company_categories_and_keywords_1",
    "location_country",
    "connections_count",
    "followers_count",
    "department_1",
    "active_experience_description",
    "company_industry_1",
    "company_employees_count_1",
]

EXPORT_COLUMN_ORDER = [
    "id",
    "full_name",
    "linkedin_url",
    "active_experience_title",
    "management_level_1",
    "company_id_1",
    "company_name_1",
    "company_size_range_1",
    "company_categories_and_keywords_1",
    "location_country",
    "connections_count",
    "followers_count",
    "department_1",
    "active_experience_description",
    "company_industry_1",
    "company_employees_count_1",
]

DEFAULT_SENIORITY_MAPPING = {
    # Management Levels (lower case keys)
    "management_levels": {
        "intern": 10, "co-op": 10, "apprentice": 10, "trainee": 10,
        "entry": 20, "junior": 25, "associate": 30,
        "specialist": 35, "analyst": 35,
        "senior": 50, "sr": 50,
        "manager": 60, "lead": 60, "supervisor": 60,
        "director": 70, "head": 75,
        "vp": 80, "vice president": 80, "svp": 85, "evp": 85, "president": 90,
        "cxo": 95, "c-level": 95, "c-suite": 95, "chief": 95,
        "owner": 90, "founder": 90, "partner": 80
    },
    # Title Keywords (regex patterns)
    "title_keywords": {
        r"\bintern\b": 10, r"\bco-op\b": 10, r"\btrainee\b": 10,
        r"\bjunior\b": 20, r"\bassistant\b": 20,
        r"\bassociate\b": 30,
        r"\bspecialist\b": 35, r"\banalyst\b": 35, r"\btechnician\b": 35, r"\bengineer\b": 40, r"\bscientist\b": 40,
        r"\bsenior\b": 50, r"\bsr\.?\b": 50, r"\bprincipal\b": 55, r"\bstaff\b": 50, r"\bstarszy\b": 50, # Polish
        r"\blead\b": 60, r"\bmanager\b": 60, r"\bsupervisor\b": 60, r"\bgerente\b": 60, # Spanish
        r"\bdirector\b": 70,
        r"\bhead of\b": 75,
        r"\bvp\b": 80, r"\bvice president\b": 80,
        r"\bchief\b": 90, r"\bc\s*-\s*suite\b": 90, r"\bceo\b": 95, r"\bcto\b": 95, r"\bcfo\b": 95,
        # Multilingual
        r"\boperario\b": 30, r"\bt[eé]cnico\b": 35, r"\btechnicien\b": 35,
        r"\bcharg[eé]e?\b": 40,
        r"\bm[lł]odszy\b": 20, # Polish Junior
        r"\blider\b": 60, # Polish Leader
    }
}

KEYWORD_RELEVANCE_COLS = [
    "active_experience_title",
    "active_experience_description",
    "company_categories_and_keywords_1",
    "company_industry_1",
    "department_1"
]

GOOD_WORDS = [
    "MSAT", "MS&T", "CMC", "CMC strategy", "Manufacturing", "MFG", "Commercial Manufacturing",
    "Clinical Manufacturing", "Sterile Manufacturing", "Production", "Process Development", "PD",
    "DSP", "USP", "Process Science", "Process Engineering", "Upstream", "Downstream",
    "Engineering", "Strategy", "R&D", "Research", "Development", "Technical Development",
    "Drug Development", "Technology Transfer", "Tech Transfer", "Technical Operations",
    "Formulation", "Lab", "Product", "Supply chain", "Principal Investigator"
]

BAD_WORDS = [
    "Small molecule", "Consultant", "Statistician", "Data Analyst", "Intern", "Student",
    "Dossier", "Contractor", "Writer", "Co-op", "Oral"
]

DEFAULT_BOOST_PER_GOOD = 8.0
DEFAULT_PENALTY_PER_BAD = 15.0

# -----------------------------------------------------------------------------
# CLASSES & FUNCTIONS
# -----------------------------------------------------------------------------

def normalize_text(s: str) -> str:
    """
    Lowercases, replaces specific punctuation with spaces, collapses spaces.
    Example: "MS&T" -> "ms t", "R&D" -> "r d" (depending on punctuation handled).
    Actually, user asked to replace & / - _ . , ; : ( ) with spaces.
    """
    if not isinstance(s, str):
        return ""
    
    s = s.lower()
    # Punctuation map to space
    for char in ['&', '/', '-', '_', '.', ',', ';', ':', '(', ')']:
        s = s.replace(char, ' ')
    
    # Collapse multiple spaces -> single space
    s = re.sub(r'\s+', ' ', s)
    return s.strip()

class KeywordEngine:
    def __init__(self, good_words, bad_words):
        # We pre-compile regexes for whole phrase matching
        # Regex logic: \bPHRASE\b but with normalized content
        
        self.good_patterns = []
        for word in good_words:
            norm = normalize_text(word)
            if norm:
                # Use word boundaries. Escape regex chars in the normalized string just in case
                pattern = r'\b' + re.escape(norm) + r'\b'
                self.good_patterns.append((word, re.compile(pattern)))
                
        self.bad_patterns = []
        for word in bad_words:
            norm = normalize_text(word)
            if norm:
                pattern = r'\b' + re.escape(norm) + r'\b'
                self.bad_patterns.append((word, re.compile(pattern)))

    def compute_matches(self, row):
        """
        Scans row across KEYWORD_RELEVANCE_COLS.
        Returns (good_count, bad_count, good_match_list, bad_match_list)
        """
        # 1. Combine all text
        combined_text = ""
        for col in KEYWORD_RELEVANCE_COLS:
            val = row.get(col)
            if pd.notna(val):
                combined_text += " " + normalize_text(str(val))
        
        combined_text = combined_text.strip()
        
        # 2. Find matches
        found_good = set()
        for original, pattern in self.good_patterns:
            if pattern.search(combined_text):
                found_good.add(original)
                
        found_bad = set()
        for original, pattern in self.bad_patterns:
            if pattern.search(combined_text):
                found_bad.add(original)
                
        return len(found_good), len(found_bad), ";".join(sorted(found_good)), ";".join(sorted(found_bad))

class SeniorityEngine:
    def __init__(self, config_path=None):
        self.mappings = DEFAULT_SENIORITY_MAPPING.copy()
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    user_config = json.load(f)
                    if "management_levels" in user_config:
                        self.mappings["management_levels"].update(user_config["management_levels"])
                    if "title_keywords" in user_config:
                        self.mappings["title_keywords"].update(user_config["title_keywords"])
                print(f"Loaded seniority config from {config_path}")
            except Exception as e:
                print(f"Warning: Could not load config file: {e}")

    def compute_score(self, title, level):
        """
        Computes seniority score (0-100) and tier based on title and management level.
        """
        level_score = 0
        title_score = 0
        
        # 1. Management Level Score (Base)
        if pd.notna(level):
            level_str = str(level).lower()
            best_match_len = 0
            for key, val in self.mappings["management_levels"].items():
                if key in level_str:
                    if len(key) > best_match_len:
                        level_score = val
                        best_match_len = len(key)
        
        # 2. Title Keyword Score (Boost/Override)
        if pd.notna(title):
            title_str = str(title).lower()
            found_scores = []
            for pattern, val in self.mappings["title_keywords"].items():
                if re.search(pattern, title_str):
                    found_scores.append(val)
            
            if found_scores:
                title_score = max(found_scores)
            
            # Special Tie-breakers
            if re.search(r"\b(vp|vice president|chief|president|head of)\b", title_str):
                title_score = max(title_score, 75)

        # 3. Combine Scores
        if level_score > 0 and title_score > 0:
            final_val = (level_score * 0.6) + (title_score * 0.4)
        elif level_score > 0:
            final_val = level_score
        elif title_score > 0:
            final_val = title_score
        else:
            final_val = 0

        return min(100, max(0, int(final_val)))

    def get_tier(self, score):
        if score >= 90: return "C-Suite/Owner"
        if score >= 80: return "VP/Executive"
        if score >= 70: return "Director/Head"
        if score >= 60: return "Manager/Lead"
        if score >= 50: return "Senior"
        if score >= 30: return "Mid/Associate"
        if score >= 20: return "Junior/Entry"
        return "Support/Intern/Unknown"

def validate_columns(df):
    """
    Validates existence of required columns.
    Attempts fuzzy mapping for missing columns if user approves.
    """
    # Force lowercase strip on df columns first
    df.columns = df.columns.str.strip().str.lower()
    
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    
    if missing:
        # Fuzzy mapping logic
        print(f"\nWarning: Missing {len(missing)} required columns.")
        print("Attempting to find best matches...")
        
        rename_map = {}
        for missing_col in missing:
            # Simple heuristic: substring, or maybe something like 'company' in name
            # Or ask user to select from available columns?
            # Let's try to match by partial string or look for common alternatives
            
            potential_matches = []
            for existing_col in df.columns:
                # Naive similarity: if one is substring of another or highly similar
                if missing_col in existing_col or existing_col in missing_col:
                    potential_matches.append(existing_col)
            
            # Additional heuristic replacements
            if not potential_matches:
                if "1" in missing_col:
                    # check for '_one' version or just base name
                    alt = missing_col.replace("_1", "_one")
                    if alt in df.columns: potential_matches.append(alt)
                    alt2 = missing_col.replace("_1", "")
                    if alt2 in df.columns: potential_matches.append(alt2)

            if potential_matches:
                print(f"  Missing: '{missing_col}'")
                print(f"  Found potential matches: {potential_matches}")
                choice = input(f"  Use '{potential_matches[0]}' for '{missing_col}'? (y/n/manual): ").strip().lower()
                if choice == 'y':
                    rename_map[potential_matches[0]] = missing_col
                elif choice == 'manual':
                    manual = input(f"  Enter column name to map to '{missing_col}' (or Enter to skip): ").strip()
                    if manual and manual in df.columns:
                        rename_map[manual] = missing_col
            else:
                # Manual fallback
                manual = input(f"  No match found for '{missing_col}'. Enter column to map (or Enter to fail): ").strip()
                if manual and manual in df.columns:
                    rename_map[manual] = missing_col
        
        if rename_map:
            print(f"Renaming columns: {rename_map}")
            df = df.rename(columns=rename_map)
    
    # Re-check missing after mapping
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        return False, missing, df
    
    # Reorder columns to match EXPORT_COLUMN_ORDER + any extra columns
    extra_cols = [c for c in df.columns if c not in EXPORT_COLUMN_ORDER]
    df = df[EXPORT_COLUMN_ORDER + extra_cols]
    return True, [], df

def load_data():
    if len(sys.argv) > 1:
        path = sys.argv[1]
        print(f"Using file from argument: {path}")
    else:
        path = input("\nEnter path to CSV file: ").strip().strip('"').strip("'")
            
    while True:
        if not path:
             path = input("Please enter a path: ").strip().strip('"').strip("'")
             continue
        
        if not os.path.exists(path):
            print(f"Error: File not found at {path}")
            path = "" 
            continue
            
        try:
            print(f"Loading {path}...")
            # Detect encoding? Default usually works or utf-8
            df = pd.read_csv(path) 
            return df
        except Exception as e:
            print(f"Error reading file: {e}")
            retry = input("Try again? (y/n): ").lower()
            if retry != 'y':
                sys.exit()
            path = ""

def get_user_input_list(prompt_text):
    val = input(prompt_text).strip()
    if not val:
        return []
    return [x.strip() for x in val.split(',') if x.strip()]

def apply_filters(df):
    print("\n--- FILTERING OPTIONS (Press Enter to skip) ---")
    
    countries = get_user_input_list("Filter by Location Country (comma-separated): ")
    if countries:
        pattern = '|'.join([re.escape(c) for c in countries])
        df = df[df['location_country'].astype(str).str.contains(pattern, case=False, na=False)]
        print(f"Rows after country filter: {len(df)}")
    
    if df.empty: return df

    sizes = get_user_input_list("Filter by Company Size Range (comma-separated): ")
    if sizes:
        pattern = '|'.join([re.escape(s) for s in sizes])
        df = df[df['company_size_range_1'].astype(str).str.contains(pattern, case=False, na=False)]
        print(f"Rows after size filter: {len(df)}")

    if df.empty: return df

    levels = get_user_input_list("Filter by Management Level (comma-separated): ")
    if levels:
        pattern = '|'.join([re.escape(l) for l in levels])
        df = df[df['management_level_1'].astype(str).str.contains(pattern, case=False, na=False)]
        print(f"Rows after level filter: {len(df)}")

    # We removed old keyword filter loop here in favor of the engine? 
    # Or keep it as an additional hard filter? 
    # The prompt says "Filter by keywords in: ..." but later says "Keyword Relevance Engine..."
    # I will keep this simple filter as "Hard Include" if user wants it, separate from scoring.
    keywords = get_user_input_list("Hard Filter by Keywords (optional - comma-separated): ")
    if keywords:
        pattern = '|'.join([re.escape(k) for k in keywords])
        mask = (
            df['active_experience_title'].astype(str).str.contains(pattern, case=False, na=False) |
            df['company_industry_1'].astype(str).str.contains(pattern, case=False, na=False) |
            df['company_categories_and_keywords_1'].astype(str).str.contains(pattern, case=False, na=False)
        )
        df = df[mask]
        print(f"Rows after keyword filter: {len(df)}")

    return df

def get_weights():
    print("\n--- SCORING WEIGHTS (0-100) ---")
    print("Defaulting to balanced model if you just press Enter.")
    
    try:
        w_seniority = float(input("Weight for SENIORITY (default 40): ") or 40)
        w_connections = float(input("Weight for CONNECTIONS count (default 20): ") or 20)
        w_followers = float(input("Weight for FOLLOWERS count (default 10): ") or 10)
        w_company = float(input("Weight for COMPANY SIZE (default 10): ") or 10)
        w_keywords = float(input("Weight for KEYWORD RELEVANCE (default 20): ") or 20)
    except ValueError:
        print("Invalid input, using defaults.")
        w_seniority, w_connections, w_followers, w_company, w_keywords = 40, 20, 10, 10, 20

    total = w_seniority + w_connections + w_followers + w_company + w_keywords
    if total == 0: return 0, 0, 0, 0, 0
    
    return (
        w_seniority / total,
        w_connections / total,
        w_followers / total,
        w_company / total,
        w_keywords / total
    )

def get_keyword_config():
    print("\n--- KEYWORD ENGINE CONFIG ---")
    mode = input("Bad word handling: A) Penalize only [default], B) Filter out completely? (A/B): ").strip().upper()
    filter_bad = (mode == 'B')
    
    try:
        boost = float(input(f"Boost points per GOOD term (default {DEFAULT_BOOST_PER_GOOD}): ") or DEFAULT_BOOST_PER_GOOD)
        penalty = float(input(f"Penalty points per BAD term (default {DEFAULT_PENALTY_PER_BAD}): ") or DEFAULT_PENALTY_PER_BAD)
    except ValueError:
        print("Invalid input, using defaults.")
        boost = DEFAULT_BOOST_PER_GOOD
        penalty = DEFAULT_PENALTY_PER_BAD
        
    return filter_bad, boost, penalty

def calculate_scores(df, weights, seniority_engine, keyword_engine, filter_bad, boost_per_good, penalty_per_bad):
    w_sen, w_conn, w_foll, w_comp, w_key = weights
    
    if tqdm_available:
        tqdm.pandas(desc="Calculating Seniority")

    # 1. Seniority
    print("Calculating Seniority Scores...")
    # Use progress_apply if tqdm available and working, else fallback
    try:
        if tqdm_available:
            seniority_results = df.progress_apply(
                lambda row: seniority_engine.compute_score(
                    row.get('active_experience_title'), 
                    row.get('management_level_1')
                ), axis=1
            )
        else:
            raise ImportError("tqdm not available")
    except Exception:
        # Fallback if tqdm.pandas() failed or not available
        seniority_results = df.apply(
            lambda row: seniority_engine.compute_score(
                row.get('active_experience_title'), 
                row.get('management_level_1')
            ), axis=1
        )

    df['seniority_score'] = seniority_results
    df['seniority_tier'] = df['seniority_score'].apply(seniority_engine.get_tier)
    
    # 2. Network (Connections + Followers)
    for col in ['connections_count', 'followers_count']:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    df['connections_score'] = 0
    df['followers_score'] = 0
    
    if df['connections_count'].max() > 0:
        c_log = np.log1p(df['connections_count'])
        df['connections_score'] = (c_log / c_log.max()) * 100
        
    if df['followers_count'].max() > 0:
        f_log = np.log1p(df['followers_count'])
        df['followers_score'] = (f_log / f_log.max()) * 100
    
    df['network_score'] = (df['connections_score'] + df['followers_score']) / 2 

    # 3. Company Score
    size_map = {
        '1-10': 10, '11-50': 20, '51-200': 30, '201-500': 40, '501-1000': 50,
        '1001-5000': 60, '5001-10000': 70, '10000+': 80
    }
    def get_comp_score(val):
        val_str = str(val)
        for k, v in size_map.items():
            if k in val_str: return v
        return 0
    df['company_score'] = df['company_size_range_1'].apply(get_comp_score)

    # 4. Keyword Match Score (New Logic)
    print("Calculating Keyword Relevance...")
    
    if tqdm_available:
        try:
            tqdm.pandas(desc="Keywords")
            kw_results = df.progress_apply(keyword_engine.compute_matches, axis=1, result_type='expand')
        except Exception:
            kw_results = df.apply(keyword_engine.compute_matches, axis=1, result_type='expand')
    else:
        kw_results = df.apply(keyword_engine.compute_matches, axis=1, result_type='expand')

    kw_results.columns = ['good_match_count', 'bad_match_count', 'good_matches', 'bad_matches']
    
    df = pd.concat([df, kw_results], axis=1)
    
    # Filter if mode B
    if filter_bad:
        initial_len = len(df)
        df = df[df['bad_match_count'] == 0]
        print(f"Filtered out {initial_len - len(df)} rows containing bad words.")
        
    if df.empty: return df

    # Compute keyword_score
    raw_kw_score = (df['good_match_count'] * boost_per_good) - (df['bad_match_count'] * penalty_per_bad)
    df['keyword_score'] = raw_kw_score.clip(lower=0, upper=100)

    # 5. Final Score
    df['final_score'] = (
        (df['seniority_score'] * w_sen) +
        (df['connections_score'] * w_conn) +
        (df['followers_score'] * w_foll) +
        (df['company_score'] * w_comp) +
        (df['keyword_score'] * w_key)
    )

    return df.sort_values(by='final_score', ascending=False)

def print_diagnostics(df):
    print("\n--- DIAGNOSTICS ---")
    print(f"Total processed rows: {len(df)}")
    
    rows_with_good = len(df[df['good_match_count'] > 0])
    rows_with_bad = len(df[df['bad_match_count'] > 0])
    
    print(f"Rows with >= 1 GOOD term: {rows_with_good}")
    print(f"Rows with >= 1 BAD term:  {rows_with_bad}")
    
    # Top terms
    all_good = ";".join(df['good_matches'].dropna()).split(";")
    all_good = [x for x in all_good if x] # filter empty
    from collections import Counter
    top_good = Counter(all_good).most_common(10)
    
    all_bad = ";".join(df['bad_matches'].dropna()).split(";")
    all_bad = [x for x in all_bad if x]
    top_bad = Counter(all_bad).most_common(10)
    
    print("\nMost frequent GOOD terms:")
    for term, count in top_good:
        print(f"  - {term}: {count}")
        
    print("\nMost frequent BAD terms:")
    for term, count in top_bad:
        print(f"  - {term}: {count}")

def export_data(df):
    print("\n--- EXPORT ---")
    limit_str = input("How many top results to export? (Enter for all): ").strip()
    if limit_str and limit_str.isdigit():
        df = df.head(int(limit_str))
        
    choice = input("Export format: 1) CSV 2) Excel 3) Both (Enter 1, 2, or 3): ").strip()
    filename = input("Output file name/prefix (default 'ranked_leads'): ").strip() or "ranked_leads"
    
    if choice in ['1', '3']:
        out_csv = f"{filename}.csv"
        df.to_csv(out_csv, index=False)
        print(f"Exported {out_csv}")
        
    if choice in ['2', '3']:
        out_xlsx = f"{filename}.xlsx"
        try:
            df.to_excel(out_xlsx, index=False)
            print(f"Exported {out_xlsx}")
        except Exception as e:
            print(f"Could not export Excel: {e}")

def main():
    print("Welcome to the Audience Prioritization Tool.")
    
    # 1. Load
    df = load_data()
    
    # 2. Validate
    valid, missing, df = validate_columns(df)
    if not valid:
        print(f"CRITICAL ERROR: Missing required columns: {missing}")
        return

    # 3. Filter
    df = apply_filters(df)
    if df.empty:
        print("No rows left after filtering! Exiting.")
        return

    # 4. Weights & Config
    seniority_engine = SeniorityEngine("seniority_config.json")
    keyword_engine = KeywordEngine(GOOD_WORDS, BAD_WORDS)
    
    weights = get_weights()
    filter_bad, boost, penalty = get_keyword_config()
    
    # 5. Score
    df = calculate_scores(df, weights, seniority_engine, keyword_engine, filter_bad, boost, penalty)
    
    if df.empty:
        print("All rows filtered out by keyword engine!")
        return

    # 6. Diagnostics
    print_diagnostics(df)
    
    # 7. Preview
    print("\n--- PREVIEW (Top 10) ---")
    preview_cols = ['full_name', 'active_experience_title', 'seniority_tier', 'keyword_score', 'final_score']
    print(df[preview_cols].head(10).to_string(index=False))
    
    # 8. Export
    export_data(df)
    print("\nDone!")

if __name__ == "__main__":
    main()
