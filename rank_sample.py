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
# DESCRIPTION:
#   This tool ingests a CSV export, cleans/validates data, 
#   calculates Dynamic Seniority and Keyword Relevance scores,
#   and exports a ranked list.
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
        r"\bsenior\b": 50, r"\bsr\.?\b": 50, r"\bprincipal\b": 55, r"\bstaff\b": 50, r"\bstarszy\b": 50,
        r"\blead\b": 60, r"\bmanager\b": 60, r"\bsupervisor\b": 60, r"\bgerente\b": 60,
        r"\bdirector\b": 70,
        r"\bhead of\b": 75,
        r"\bvp\b": 80, r"\bvice president\b": 80,
        r"\bchief\b": 90, r"\bc\s*-\s*suite\b": 90, r"\bceo\b": 95, r"\bcto\b": 95, r"\bcfo\b": 95,
        # Multilingual
        r"\boperario\b": 30, r"\bt[eé]cnico\b": 35, r"\btechnicien\b": 35,
        r"\bcharg[eé]e?\b": 40,
        r"\bm[lł]odszy\b": 20, 
        r"\blider\b": 60,
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
# UTILS
# -----------------------------------------------------------------------------

def normalize_text(s: str) -> str:
    """Lowercases, replaces specific punctuation with spaces, collapses spaces."""
    if not isinstance(s, str):
        return ""
    s = s.lower()
    for char in ['&', '/', '-', '_', '.', ',', ';', ':', '(', ')']:
        s = s.replace(char, ' ')
    s = re.sub(r'\s+', ' ', s)
    return s.strip()

# -----------------------------------------------------------------------------
# CORE ENGINES
# -----------------------------------------------------------------------------

class KeywordEngine:
    def __init__(self, good_words, bad_words):
        self.good_patterns = []
        for word in good_words:
            norm = normalize_text(word)
            if norm:
                pattern = r'\b' + re.escape(norm) + r'\b'
                self.good_patterns.append((word, re.compile(pattern)))
                
        self.bad_patterns = []
        for word in bad_words:
            norm = normalize_text(word)
            if norm:
                pattern = r'\b' + re.escape(norm) + r'\b'
                self.bad_patterns.append((word, re.compile(pattern)))

    def compute_matches(self, row):
        combined_text = ""
        for col in KEYWORD_RELEVANCE_COLS:
            val = row.get(col)
            if pd.notna(val):
                combined_text += " " + normalize_text(str(val))
        combined_text = combined_text.strip()
        
        found_good = set()
        for original, pattern in self.good_patterns:
            if pattern.search(combined_text):
                found_good.add(original)
                
        found_bad = set()
        for original, pattern in self.bad_patterns:
            if pattern.search(combined_text):
                found_bad.add(original)
                
        return len(found_good), len(found_bad), ";".join(sorted(found_good)), ";".join(sorted(found_bad))

class SeniorityRawEngine:
    """Stage A: Raw Detection (Classification Only) - Returns 0-100 score."""
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

    def compute_raw_score(self, title, level):
        level_score = 0
        title_score = 0
        
        if pd.notna(level):
            level_str = str(level).lower()
            best_match_len = 0
            for key, val in self.mappings["management_levels"].items():
                if key in level_str:
                    if len(key) > best_match_len:
                        level_score = val
                        best_match_len = len(key)
        
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

class SeniorityTransformationEngine:
    """Stage B: Dynamic Transformation - Converts raw score to component based on preference."""
    
    @staticmethod
    def transform(raw_score, mode='prefer_senior', params=None):
        if params is None: params = {}
        
        if mode == 'prefer_senior':
            return raw_score
            
        elif mode == 'prefer_junior':
            return 100 - raw_score
            
        elif mode == 'prefer_mid':
            target = params.get('target', 50)
            # Distance from target. Multiplied by 2 to punish deviation faster.
            diff = abs(raw_score - target)
            res = 100 - (diff * 2)
            return max(0, min(100, res))
            
        elif mode == 'balanced':
            return 50
            
        elif mode == 'target_range_bonus':
            min_s = params.get('min', 40)
            max_s = params.get('max', 60)
            if min_s <= raw_score <= max_s:
                return 100
            else:
                # Penalty based on distance to nearest bound
                dist = min(abs(raw_score - min_s), abs(raw_score - max_s))
                # Soft penalty
                return max(0, 100 - (dist * 2))
                
        return raw_score # Fallback

# -----------------------------------------------------------------------------
# DATA PIPELINE
# -----------------------------------------------------------------------------

def validate_columns(df):
    df.columns = df.columns.str.strip().str.lower()
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    
    if missing:
        print(f"\nWarning: Missing {len(missing)} required columns.")
        print("Attempting to find best matches...")
        rename_map = {}
        for missing_col in missing:
            potential_matches = []
            for existing_col in df.columns:
                if missing_col in existing_col or existing_col in missing_col:
                    potential_matches.append(existing_col)
            
            if not potential_matches:
                if "1" in missing_col:
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
                manual = input(f"  No match found for '{missing_col}'. Enter column to map (or Enter to fail): ").strip()
                if manual and manual in df.columns:
                    rename_map[manual] = missing_col
        
        if rename_map:
            print(f"Renaming columns: {rename_map}")
            df = df.rename(columns=rename_map)
    
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        return False, missing, df
    
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
            return pd.read_csv(path) 
        except Exception as e:
            print(f"Error reading file: {e}")
            retry = input("Try again? (y/n): ").lower()
            if retry != 'y': sys.exit()
            path = ""

def get_user_input_list(prompt_text):
    val = input(prompt_text).strip()
    if not val: return []
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
    return (w_seniority / total, w_connections / total, w_followers / total, w_company / total, w_keywords / total)

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

def get_seniority_config():
    print("\n--- SENIORITY STRATEGY ---")
    print("1. Target SENIORS (Higher title = Higher score) [Default]")
    print("2. Target JUNIORS (Lower title = Higher score)")
    print("3. Target MID-LEVEL (Closer to target = Higher score)")
    print("4. Target SPECIFIC RANGE (Bonus inside range, penalty outside)")
    print("5. BALANCED (Flat score)")
    print("6. MULTI-MODE (Advanced)")
    
    choice = input("Select Strategy (1-6): ").strip()
    modes = []
    
    if choice == '2':
        modes.append({'mode': 'prefer_junior', 'params': {}})
    elif choice == '3':
        t = input("  Enter target score (0-100, default 50 for Manager/Senior): ").strip()
        target = float(t) if t.isdigit() else 50
        modes.append({'mode': 'prefer_mid', 'params': {'target': target}})
    elif choice == '4':
        mn = input("  Range MIN (default 40): ").strip()
        mx = input("  Range MAX (default 60): ").strip()
        modes.append({'mode': 'target_range_bonus', 'params': {'min': float(mn) if mn else 40, 'max': float(mx) if mx else 60}})
    elif choice == '5':
        modes.append({'mode': 'balanced', 'params': {}})
    elif choice == '6':
        print("  Enter modes separated by plus (+). Example: prefer_junior+prefer_mid")
        print("  Supported: prefer_senior, prefer_junior, prefer_mid, target_range_bonus")
        raw_modes = input("  Modes: ").strip().split('+')
        for m in raw_modes:
            m = m.strip()
            if m in ['prefer_senior', 'prefer_junior', 'balanced']:
                modes.append({'mode': m, 'params': {}})
            elif m == 'prefer_mid':
                modes.append({'mode': m, 'params': {'target': 50}}) # Default param for simplification in multi
            elif m == 'target_range_bonus':
                modes.append({'mode': m, 'params': {'min':40, 'max':60}})
        if not modes:
             modes.append({'mode': 'prefer_senior', 'params': {}})
    else:
        modes.append({'mode': 'prefer_senior', 'params': {}})
        
    combine_method = 'average'
    if len(modes) > 1:
        combine_method = input("  Combine method (average/max/weighted): ").strip().lower()
        if combine_method not in ['average', 'max', 'weighted']: combine_method = 'average'
        
    return modes, combine_method

# -----------------------------------------------------------------------------
# MAIN CALCULATION
# -----------------------------------------------------------------------------

def calculate_scores(df, weights, seniority_engine, keyword_engine, kw_config, sen_config):
    w_sen, w_conn, w_foll, w_comp, w_key = weights
    filter_bad, boost, penalty = kw_config
    modes, combine_method = sen_config
    
    # ---------------------------
    # 1. Seniority (Two Stages)
    # ---------------------------
    print("Calculating Seniority (Stage A: Raw)...")
    
    # helper for apply
    def calc_raw(row):
        return seniority_engine.compute_raw_score(
            row.get('active_experience_title'), 
            row.get('management_level_1')
        )
            
    # Stage A: Raw Score (0-100 Classification)
    if tqdm_available:
        try:
            tqdm.pandas(desc="Seniority Raw")
            raw_scores = df.progress_apply(calc_raw, axis=1)
        except Exception:
            raw_scores = df.apply(calc_raw, axis=1)
    else:
        raw_scores = df.apply(calc_raw, axis=1)
        
    df['raw_seniority_score'] = raw_scores
    df['seniority_tier'] = df['raw_seniority_score'].apply(seniority_engine.get_tier)
    
    # Stage B: Dynamic Transformation
    print(f"Calculating Seniority (Stage B: Transformation) - Modes: {len(modes)}")
    
    def transform_row(score):
        vals = []
        for m in modes:
            vals.append(SeniorityTransformationEngine.transform(score, m['mode'], m['params']))
        
        if not vals: return 0
        
        if combine_method == 'max':
            return max(vals)
        elif combine_method == 'weighted':
             # Simplified equal weight for now, or could ask user. Default to average implementation for 'weighted' unless specific weights passed
             return sum(vals) / len(vals)
        else: # average
            return sum(vals) / len(vals)

    df['seniority_component'] = df['raw_seniority_score'].apply(transform_row)
    
    # Diagnostics columns
    df['selected_modes'] = str([m['mode'] for m in modes])
    df['combine_method'] = combine_method

    # ---------------------------
    # 2. Network
    # ---------------------------
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

    # ---------------------------
    # 3. Company Score
    # ---------------------------
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

    # ---------------------------
    # 4. Keyword Relevance
    # ---------------------------
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
    
    if filter_bad:
        initial_len = len(df)
        df = df[df['bad_match_count'] == 0]
        print(f"Filtered out {initial_len - len(df)} rows containing bad words.")
    if df.empty: return df

    raw_kw_score = (df['good_match_count'] * boost) - (df['bad_match_count'] * penalty)
    df['keyword_score'] = raw_kw_score.clip(lower=0, upper=100)

    # ---------------------------
    # 5. Final Score
    # ---------------------------
    # USING seniority_component instead of seniority_score
    df['final_score'] = (
        (df['seniority_component'] * w_sen) +
        (df['connections_score'] * w_conn) +
        (df['followers_score'] * w_foll) +
        (df['company_score'] * w_comp) +
        (df['keyword_score'] * w_key)
    )

    return df.sort_values(by='final_score', ascending=False)

def print_diagnostics(df):
    print("\n--- DIAGNOSTICS ---")
    print(f"Total processed rows: {len(df)}")
    print(f"Seniority Strategy: {df['selected_modes'].iloc[0]} (Merge: {df['combine_method'].iloc[0]})")
    
    print("\nSample Scores (Top 3):")
    cols = ['full_name', 'raw_seniority_score', 'seniority_component', 'final_score']
    print(df[cols].head(3).to_string(index=False))
    
    rows_with_good = len(df[df['good_match_count'] > 0])
    print(f"\nRows with >= 1 GOOD term: {rows_with_good}")
    
    all_good = ";".join(df['good_matches'].dropna()).split(";")
    all_good = [x for x in all_good if x] 
    from collections import Counter
    top_good = Counter(all_good).most_common(5)
    print("Top matches:", top_good)

def export_data(df):
    print("\n--- EXPORT ---")
    limit_str = input("How many top results to export? (Enter for all): ").strip()
    if limit_str and limit_str.isdigit():
        df = df.head(int(limit_str))
        
    choice = input("Export format: 1) CSV 2) Excel 3) Both (Enter 1, 2, or 3): ").strip()
    filename = input("Output file name/prefix (default 'ranked_leads'): ").strip() or "ranked_leads"
    
    if choice in ['1', '3']:
        df.to_csv(f"{filename}.csv", index=False)
        print(f"Exported {filename}.csv")
    if choice in ['2', '3']:
        try:
            df.to_excel(f"{filename}.xlsx", index=False)
            print(f"Exported {filename}.xlsx")
        except Exception as e:
            print(f"Excel export failed: {e}")

def main():
    print("Welcome to the Audience Prioritization Tool (v2.0 - Dynamic Seniority).")
    
    df = load_data()
    valid, missing, df = validate_columns(df)
    if not valid:
        print(f"CRITICAL ERROR: Missing {missing}")
        return

    df = apply_filters(df)
    if df.empty:
        print("No rows left.")
        return

    seniority_engine = SeniorityRawEngine("seniority_config.json")
    keyword_engine = KeywordEngine(GOOD_WORDS, BAD_WORDS)
    
    weights = get_weights()
    kw_config = get_keyword_config()
    sen_config = get_seniority_config()
    
    df = calculate_scores(df, weights, seniority_engine, keyword_engine, kw_config, sen_config)
    
    if df.empty:
        print("All rows filtered out!")
        return

    print_diagnostics(df)
    
    print("\n--- PREVIEW (Top 10) ---")
    preview_cols = ['full_name', 'active_experience_title', 'seniority_tier', 'raw_seniority_score', 'seniority_component', 'final_score']
    print(df[preview_cols].head(10).to_string(index=False))
    
    export_data(df)
    print("\nDone!")

if __name__ == "__main__":
    main()
