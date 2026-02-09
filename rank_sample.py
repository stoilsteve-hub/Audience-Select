#!/usr/bin/env python3
"""
Audience Prioritization Tool
----------------------------
A console-based tool (with Streamlit support) to rank contacts from CSV based on Seniority, Network, Company Size, and Keywords.

Requirements:
    Python 3.10+
    pandas, numpy, openpyxl, tqdm

Usage:
    python rank_sample.py [input_file] [options]
    streamlit run app.py
"""

import sys
import os
import re
import json
import logging
import math
import argparse
from typing import List, Dict, Tuple, Optional, Any, Set, Union, NamedTuple, Pattern
from dataclasses import dataclass, field
from enum import Enum

# Third-party imports
try:
    import pandas as pd
    import numpy as np
except ImportError:
    print("Error: pandas and numpy are required. Install via: pip install pandas numpy")
    sys.exit(1)

# Optional TQDM
try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False

    def tqdm(iterable, desc=None, **kwargs):
        return iterable

    # Minimal shim for tqdm.pandas
    if hasattr(tqdm, 'pandas'):
        pass  # Real tqdm
    else:
        # Shim if we created the dummy function
        def tqdm_pandas_shim(**kwargs): pass
        tqdm.pandas = tqdm_pandas_shim


# =============================================================================
# LOGGING SETUP
# =============================================================================

logger = logging.getLogger("AudienceRanker")

def setup_logging(verbose: bool = False, quiet: bool = False) -> None:
    """Sets up file and console logging."""
    logger.setLevel(logging.DEBUG)
    
    # File Handler (Always DEBUG)
    file_fmt = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    try:
        fh = logging.FileHandler('audience_ranker.log', mode='w', encoding='utf-8')
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(file_fmt)
        logger.addHandler(fh)
    except Exception as e:
        print(f"Warning: Could not set up file logging: {e}")

    # Console Handler
    if quiet:
        console_level = logging.WARNING
    elif verbose:
        console_level = logging.DEBUG
    else:
        console_level = logging.INFO
    
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(console_level)
    console_fmt = logging.Formatter('%(message)s')
    ch.setFormatter(console_fmt)
    logger.addHandler(ch)

# =============================================================================
# CONSTANTS & CONFIGURATION
# =============================================================================

REQUIRED_COLUMNS: List[str] = [
    "id",
    "full_name",
    "linkedin_url",
    "active_experience_title",
    "management_level_1",
    "company_id_1",
    "company_name_1",
    "company_size_range_1",
    "company_categories_and_keywords_1",
    "company_industry_1",
    "company_employees_count_1",
    "department_1",
    "active_experience_description",
    "location_country",
    "connections_count",
    "followers_count",
]

RANKING_COLUMNS: List[str] = [
    "ranking_score",
    "ranking_reason",
    "final_score",
    "seniority_component",
    "raw_seniority_score",
    "seniority_tier",
    "keyword_score",
    "good_match_count",
    "bad_match_count",
    "good_matches"
]

KEYWORD_RELEVANCE_COLS: List[str] = [
    "active_experience_title",
    "active_experience_description",
    "company_categories_and_keywords_1",
    "company_industry_1",
    "department_1"
]

GOOD_WORDS: List[str] = [
    "MSAT", "MS&T", "CMC", "CMC strategy", "Manufacturing", "MFG", "Commercial Manufacturing", 
    "Clinical Manufacturing", "Sterile Manufacturing", "Production", "Process Development", "PD", 
    "DSP", "USP", "Process Science", "Process Engineering", "Upstream", "Downstream", 
    "Engineering", "Strategy", "R&D", "Research", "Development", "Technical Development", 
    "Drug Development", "Technology Transfer", "Tech Transfer", "Technical Operations", 
    "Formulation", "Lab", "Product", "Supply chain", "Principal Investigator",
    "GMP", "cGMP", "Validation", "Quality Assurance", "QA", "Technical Writing", 
    "CAPA", "Bioprocessing", "Scale-up", "Scale-down", "Fill Finish", "PAT", 
    "Automation", "CDMO", "CMO", "Tech Ops", "Operations Strategy", "Program Management", 
    "Cell Therapy", "Gene Therapy", "Biologics", "Antibodies", "mAb", "ATMP"
]

BAD_WORDS: List[str] = [
    "Small molecule", "Consultant", "Statistician", "Data Analyst", "Intern", "Student", 
    "Dossier", "Contractor", "Writer", "Co-op", "Oral",
    "Sales", "Marketing", "Recruiter", "Finance", "Accounting", "Retail"
]

DEFAULT_BOOST = 8.0
DEFAULT_PENALTY = 15.0

# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class KeywordConfig:
    filter_bad_rows: bool = False
    boost_per_good: float = DEFAULT_BOOST
    penalty_per_bad: float = DEFAULT_PENALTY

@dataclass
class WeightsConfig:
    seniority: float
    keyword: float
    connections: float
    followers: float
    company_size: float

    def normalize(self) -> None:
        total = (self.seniority + self.keyword + self.connections + 
                 self.followers + self.company_size)
        if total > 0:
            self.seniority /= total
            self.keyword /= total
            self.connections /= total
            self.followers /= total
            self.company_size /= total
        else:
            # Fallback to balanced if all zero
            self.seniority = self.keyword = self.connections = self.followers = self.company_size = 0.2

class SeniorityModeType(Enum):
    PREFER_SENIOR = "prefer_senior"
    PREFER_JUNIOR = "prefer_junior"
    PREFER_MID = "prefer_mid"
    BALANCED = "balanced"
    TARGET_RANGE_BONUS = "target_range_bonus"

@dataclass
class SeniorityMode:
    mode_type: SeniorityModeType
    params: Dict[str, float] = field(default_factory=dict)

@dataclass
class SeniorityPreference:
    is_multi: bool
    modes: List[SeniorityMode]
    combine_method: str = "average"  # average, max, weighted
    weights: Optional[List[float]] = None # If weighted combination

# =============================================================================
# HELPERS
# =============================================================================

def normalize_text(text: Any) -> str:
    """
    Lowercase, replace punctuation with spaces, collapse whitespace.
    """
    if not isinstance(text, str):
        return ""
    
    s = text.lower()
    # Punctuation map to space
    for char in ['&', '/', '-', '_', '.', ',', ';', ':', '(', ')', '[', ']', '!', '?']:
        s = s.replace(char, ' ')
    
    # Collapse spaces
    s = re.sub(r'\s+', ' ', s)
    return s.strip()

# =============================================================================
# ENGINES
# =============================================================================

class KeywordEngine:
    """Phrase-aware Keyword Relevance Engine."""
    
    def __init__(self, good_list: List[str], bad_list: List[str]):
        self.good_patterns: List[Tuple[str, Pattern]] = []
        self.bad_patterns: List[Tuple[str, Pattern]] = []
        
        # Compile regexes with word boundaries
        for w in good_list:
            norm = normalize_text(w)
            if norm:
                # \b matches word boundary
                pattern = re.compile(r'\b' + re.escape(norm) + r'\b')
                self.good_patterns.append((w, pattern))
                
        for w in bad_list:
            norm = normalize_text(w)
            if norm:
                pattern = re.compile(r'\b' + re.escape(norm) + r'\b')
                self.bad_patterns.append((w, pattern))

    def compute_score(self, row: pd.Series, config: KeywordConfig) -> Tuple[float, int, int, str, str]:
        """
        Returns (score, good_count, bad_count, good_matches_str, bad_matches_str)
        """
        # 1. Aggregation
        text_blobs = []
        for col in KEYWORD_RELEVANCE_COLS:
            val = row.get(col)
            if pd.notna(val):
                text_blobs.append(normalize_text(str(val)))
        
        full_text = " ".join(text_blobs)
        
        # 2. Matching
        found_good = set()
        for original, pattern in self.good_patterns:
            if pattern.search(full_text):
                found_good.add(original)
        
        found_bad = set()
        for original, pattern in self.bad_patterns:
            if pattern.search(full_text):
                found_bad.add(original)
        
        good_count = len(found_good)
        bad_count = len(found_bad)
        
        # 3. Scoring
        raw = (good_count * config.boost_per_good) - (bad_count * config.penalty_per_bad)
        score = max(0.0, min(100.0, raw))
        
        return score, good_count, bad_count, ";".join(sorted(found_good)), ";".join(sorted(found_bad))


class SeniorityRawEngine:
    """Stage 1: Raw Classification (0-100)."""
    
    DEFAULT_MAPPING = {
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
        "title_keywords": {
            r"\bintern\b": 10, r"\bco-op\b": 10, r"\btrainee\b": 10,
            r"\bjunior\b": 20, r"\bassistant\b": 20,
            r"\bassociate\b": 30,
            r"\bspecialist\b": 35, r"\banalyst\b": 35, r"\btechnician\b": 35, r"\bengineer\b": 40, r"\bscientist\b": 40,
            r"\bsenior\b": 50, r"\bsr\.?\b": 50, r"\bprincipal\b": 55, r"\bstaff\b": 50, r"\bstarszy\b": 50,
            r"\blead\b": 60, r"\bmanager\b": 60, r"\bsupervisor\b": 60, r"\bgerente\b": 60,
            r"\bdirector\b": 70, r"\bhead of\b": 75,
            r"\bvp\b": 80, r"\bvice president\b": 80,
            r"\bchief\b": 90, r"\bc\s*-\s*suite\b": 90, r"\bceo\b": 95, r"\bcto\b": 95, r"\bcfo\b": 95,
            r"\boperario\b": 30, r"\bt[eé]cnico\b": 35, r"\btechnicien\b": 35,
            r"\bcharg[eé]e?\b": 40, r"\bm[lł]odszy\b": 20, r"\blider\b": 60,
        }
    }

    def __init__(self, config_file: Optional[str] = None):
        self.levels = self.DEFAULT_MAPPING["management_levels"].copy()
        self.keywords = self.DEFAULT_MAPPING["title_keywords"].copy()
        
        if config_file and os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    data = json.load(f)
                    if "management_levels" in data:
                        self.levels.update(data["management_levels"])
                    if "title_keywords" in data:
                        self.keywords.update(data["title_keywords"])
                logger.debug(f"Loaded seniority config from {config_file}")
            except Exception as e:
                logger.warning(f"Failed to load seniority config: {e}")

    def compute_raw(self, row: pd.Series) -> Tuple[float, str]:
        level_val = str(row.get("management_level_1", "")).lower()
        title_val = str(row.get("active_experience_title", "")).lower()
        
        score_level = 0.0
        score_title = 0.0
        
        # Level matches
        best_len = 0
        for k, v in self.levels.items():
            if k in level_val:
                if len(k) > best_len:
                    score_level = float(v)
                    best_len = len(k)
        
        # Title matches
        found_vals = []
        for pat, v in self.keywords.items():
            if re.search(pat, title_val):
                found_vals.append(float(v))
        if found_vals:
            score_title = max(found_vals)
            
        # Tie-breakers
        if re.search(r"\b(vp|vice president|chief|president|head of)\b", title_val):
            score_title = max(score_title, 75.0)

        # Combine
        if score_level > 0 and score_title > 0:
            raw = (score_level * 0.6) + (score_title * 0.4)
        elif score_level > 0:
            raw = score_level
        elif score_title > 0:
            raw = score_title
        else:
            raw = 0.0
            
        return min(100.0, max(0.0, raw)), self.get_tier(raw)

    @staticmethod
    def get_tier(score: float) -> str:
        if score >= 90: return "C-Suite/Owner"
        if score >= 80: return "VP/Executive"
        if score >= 70: return "Director/Head"
        if score >= 60: return "Manager/Lead"
        if score >= 50: return "Senior"
        if score >= 30: return "Mid/Associate"
        if score >= 20: return "Junior/Entry"
        return "Support/Intern/Unknown"


class SeniorityTransformationEngine:
    """Stage 2: Dynamic Transformation."""
    
    @staticmethod
    def transform_single(raw: float, mode: SeniorityMode) -> float:
        mt = mode.mode_type
        
        if mt == SeniorityModeType.PREFER_SENIOR:
            return raw
            
        elif mt == SeniorityModeType.PREFER_JUNIOR:
            return 100.0 - raw
            
        elif mt == SeniorityModeType.PREFER_MID:
            target = mode.params.get("t", 50.0)
            diff = abs(raw - target)
            # Example logic: 100 - (diff * 2), clamped
            val = 100.0 - (diff * 2.0)
            return max(0.0, min(100.0, val))
            
        elif mt == SeniorityModeType.BALANCED:
            return 50.0
            
        elif mt == SeniorityModeType.TARGET_RANGE_BONUS:
            mn = mode.params.get("min", 40.0)
            mx = mode.params.get("max", 60.0)
            if mn <= raw <= mx:
                return 100.0
            # Distance penalty
            dist = min(abs(raw - mn), abs(raw - mx))
            val = 100.0 - (dist * 2.0)
            return max(0.0, min(100.0, val))
            
        return raw

    def compute_component(self, raw: float, pref: SeniorityPreference) -> float:
        if not pref.is_multi:
            return self.transform_single(raw, pref.modes[0])
        
        # Multi calculation
        components = [self.transform_single(raw, m) for m in pref.modes]
        
        if pref.combine_method == "max":
            return max(components)
        elif pref.combine_method == "weighted" and pref.weights:
            # Weighted average
            total_w = sum(pref.weights)
            if total_w == 0: return sum(components) / len(components)
            w_sum = sum(c * w for c, w in zip(components, pref.weights))
            return w_sum / total_w
        else:
            # Default average
            return sum(components) / len(components)


# =============================================================================
# WORKFLOW FUNCTIONS
# =============================================================================

def validate_columns(df: pd.DataFrame) -> Tuple[bool, List[str], pd.DataFrame]:
    """Ensures required columns exist, mapping _one -> _1 where necessary."""
    # Normalize headers
    df.columns = df.columns.astype(str).str.strip().str.lower()
    
    # 1. First pass check
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    
    # 2. Fuzzy Map Attempt (including manual confirmation)
    if missing:
        logger.warning(f"Missing {len(missing)} required columns.")
        
        rename_map = {}
        for mcol in missing:
            # Suggestions
            candidates = []
            
            # Legacy _one fix
            if mcol.endswith("_1"):
                legacy = mcol.replace("_1", "_one")
                if legacy in df.columns: candidates.append(legacy)
                
            # Common partials
            if mcol == "management_level_1":
                if "level" in df.columns: candidates.append("level")
            
            # General fuzzy
            for col in df.columns:
                if col not in candidates and (mcol in col or col in mcol):
                     candidates.append(col)
            
            if candidates:
                print(f"Missing: {mcol}. Candidates: {candidates}")
                # Interactive fix
                if sys.stdin.isatty():
                    ans = input(f"Use '{candidates[0]}' for '{mcol}'? [y/n]: ").lower()
                    if ans == 'y':
                        rename_map[candidates[0]] = mcol
                        continue
            
            # Manual
            if sys.stdin.isatty():
                ans = input(f"Enter column name for '{mcol}' (or Enter to fail): ").strip()
                if ans and ans in df.columns:
                    rename_map[ans] = mcol

        if rename_map:
            logger.info(f"Renaming columns: {rename_map}")
            df = df.rename(columns=rename_map)

    # 3. Final Check
    final_missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if final_missing:
        return False, final_missing, df
    
    return True, [], df

def get_weights_interactive() -> WeightsConfig:
    print("\n--- SCORING WEIGHTS (0-100) ---")
    try:
        s = float(input("Seniority (default 40): ") or 40)
        k = float(input("Keywords (default 20): ") or 20)
        c = float(input("Connections (default 20): ") or 20)
        f = float(input("Followers (default 10): ") or 10)
        z = float(input("Company Size (default 10): ") or 10)
    except ValueError:
        print("Invalid input, using defaults.")
        s, k, c, f, z = 40, 20, 20, 10, 10
    
    wc = WeightsConfig(s, k, c, f, z)
    wc.normalize()
    return wc

def get_seniority_pref_interactive() -> SeniorityPreference:
    print("\n--- SENIORITY PREFERENCE ---")
    print("Selection type:")
    print("  1) single")
    print("  2) multi")
    stype = input("Choose 1 or 2: ").strip()
    
    is_multi = (stype == "2")
    modes: List[SeniorityMode] = []
    
    # Helper to parse one code
    def parse_mode_code(code: str) -> SeniorityMode:
        c = code.upper()
        if c.startswith("S") or code == "1":
            return SeniorityMode(SeniorityModeType.PREFER_SENIOR)
        elif c.startswith("J") or code == "2":
            return SeniorityMode(SeniorityModeType.PREFER_JUNIOR)
        elif c.startswith("M") or code == "3":
            t_str = input("  Target score (0-100, default 50): ").strip()
            t = float(t_str) if t_str.isdigit() else 50.0
            return SeniorityMode(SeniorityModeType.PREFER_MID, {"t": t})
        elif c.startswith("B") or code == "4":
            return SeniorityMode(SeniorityModeType.BALANCED)
        elif c.startswith("TR") or c.startswith("T") or code == "5":
            mn_str = input("  Min (default 40): ").strip()
            mx_str = input("  Max (default 60): ").strip()
            mn = float(mn_str) if mn_str.isdigit() else 40.0
            mx = float(mx_str) if mx_str.isdigit() else 60.0
            return SeniorityMode(SeniorityModeType.TARGET_RANGE_BONUS, {"min": mn, "max": mx})
        return SeniorityMode(SeniorityModeType.PREFER_SENIOR)

    if not is_multi:
        print("Pick exactly one:")
        print("  1) prefer_senior (S)")
        print("  2) prefer_junior (J)")
        print("  3) prefer_mid (M)")
        print("  4) balanced (B)")
        print("  5) target_range_bonus (TR)")
        choice = input("Choice: ").strip()
        modes.append(parse_mode_code(choice))
        return SeniorityPreference(False, modes)
    else:
        print("Enter codes (S, J, M, B, TR) separated by comma:")
        line = input("Codes: ").strip()
        parts = [p.strip() for p in line.split(',') if p.strip()]
        for p in parts:
            modes.append(parse_mode_code(p))
            
        print("Combine method:")
        print("  1) average")
        print("  2) max")
        print("  3) weighted")
        cm_in = input("Choice: ").strip()
        
        method = "average"
        weights = None
        
        if cm_in == "2": method = "max"
        elif cm_in == "3":
            method = "weighted"
            print(f"Enter {len(modes)} weights (comma separated):")
            w_str = input("Weights: ").strip()
            try:
                weights = [float(x) for x in w_str.split(',')]
            except:
                weights = [1.0] * len(modes)
                
        return SeniorityPreference(True, modes, method, weights)

def get_cli_args():
    parser = argparse.ArgumentParser(description="Audience Ranking Tool")
    parser.add_argument("input_file", nargs="?", help="Input CSV file")
    parser.add_argument("--weights", help="Comma-sep weights: Seniority,Keyword,Conn,Foll,Size")
    parser.add_argument("--seniority-mode-type", choices=["single", "multi"], help="Single or Multi mode")
    parser.add_argument("--seniority-modes", help="Comma-sep codes (S,J,M,B,TR)")
    # For simplicity, complex parsing of params via CLI is limited in this implementation
    # but we support basic mode codes.
    parser.add_argument("--combine", choices=["average", "max", "weighted"], default="average")
    parser.add_argument("--bad-words-action", choices=["A", "B"], default="A", help="A=Penalize, B=Filter")
    parser.add_argument("--export-csv", action="store_true")
    parser.add_argument("--export-excel", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("-q", "--quiet", action="store_true")
    
    return parser.parse_args()


# =============================================================================
# MAIN LOGIC
# =============================================================================

def build_ranking_reason(row: pd.Series) -> str:
    """Generates a human-readable explanation for the ranking score."""
    parts = []
    
    # 1. Seniority Explanation
    sen_val = float(row.get('seniority_component', 0))
    sen_mode = str(row.get('seniority_mode_type', 'unknown'))
    sen_sel = str(row.get('seniority_modes_selected', ''))
    
    # Clean up display of mode
    if "prefer_senior" in sen_sel: mode_disp = "Senior-target"
    elif "prefer_junior" in sen_sel: mode_disp = "Junior-target"
    elif "prefer_mid" in sen_sel: mode_disp = "Mid-target"
    elif "target_range" in sen_sel: mode_disp = "Range-target"
    elif "balanced" in sen_sel: mode_disp = "Balanced"
    else: mode_disp = sen_mode
    
    if sen_val > 50:
        parts.append(f"Seniority boost: {int(sen_val)} ({mode_disp})")
    else:
        parts.append(f"Seniority score: {int(sen_val)} ({mode_disp})")
        
    # 2. Keyword Explanation
    kw_val = float(row.get('keyword_score', 0))
    good_matches = str(row.get('good_matches', ''))
    
    if kw_val > 0:
        match_list = [m for m in good_matches.split(';') if m]
        top_matches = ", ".join(match_list[:3])
        if len(match_list) > 3: top_matches += "..."
        parts.append(f"Keyword relevance: {int(kw_val)} (matched: {top_matches})")
    
    # 3. Network
    conn_norm = float(row.get('connections_score_norm', 0))
    foll_norm = float(row.get('followers_score_norm', 0))
    
    if conn_norm > 70 or foll_norm > 70:
        parts.append("High network influence")
    elif conn_norm > 40:
        parts.append("Moderate network presence")
        
    # 4. Company
    comp_score = float(row.get('company_size_score', 0))
    if comp_score > 60:
        parts.append("Large company profile")
        
    return "; ".join(parts) + "."

def run_ranking(
    df: pd.DataFrame,
    weights_config: WeightsConfig,
    sen_pref: SeniorityPreference,
    kw_config: KeywordConfig
) -> pd.DataFrame:
    """
    Pure ranking logic. Accepts a dataframe and config objects,
    returns a ranked dataframe with new columns.
    Does NOT perform I/O or exports.
    """
    
    # Engines
    k_engine = KeywordEngine(GOOD_WORDS, BAD_WORDS)
    raw_sen_engine = SeniorityRawEngine("seniority_config.json")
    trans_sen_engine = SeniorityTransformationEngine()
    
    # -----------------------------
    # 1. Keyword Scoring
    # -----------------------------
    logger.info("Computing Keyword Scores...")
    
    def kw_wrapper(row):
        return k_engine.compute_score(row, kw_config)

    kw_res = None
    if TQDM_AVAILABLE:
        try:
            tqdm.pandas(desc="Keywords")
            kw_res = df.progress_apply(kw_wrapper, axis=1, result_type='expand')
        except Exception as e:
            logger.warning(f"TQDM progress bar failed ({e}), falling back to standard apply.")
            kw_res = df.apply(kw_wrapper, axis=1, result_type='expand')
    else:
        kw_res = df.apply(kw_wrapper, axis=1, result_type='expand')
        
    df['keyword_score'] = kw_res[0]
    df['good_match_count'] = kw_res[1].astype(int)
    df['bad_match_count'] = kw_res[2].astype(int)
    df['good_matches'] = kw_res[3]
    df['bad_matches'] = kw_res[4]

    # Filter bad words if requested
    if kw_config.filter_bad_rows:
        initial_len = len(df)
        df = df[df['bad_match_count'] == 0]
        logger.info(f"Filtered {initial_len - len(df)} rows due to bad words.")
        if df.empty:
            logger.warning("All rows filtered output due to Keywords.")
            return df # Return empty to handle upstream

    # -----------------------------
    # 2. Seniority Scoring
    # -----------------------------
    logger.info("Computing Seniority...")
    
    # Stage 1: Raw
    def sen_raw_wrapper(row):
        return raw_sen_engine.compute_raw(row)
        
    raw_res = None
    if TQDM_AVAILABLE:
        try:
            tqdm.pandas(desc="Seniority Raw")
            raw_res = df.progress_apply(sen_raw_wrapper, axis=1, result_type='expand')
        except Exception:
            raw_res = df.apply(sen_raw_wrapper, axis=1, result_type='expand')
    else:
        raw_res = df.apply(sen_raw_wrapper, axis=1, result_type='expand')
        
    df['raw_seniority_score'] = raw_res[0]
    df['seniority_tier'] = raw_res[1]
    
    # Stage 2: Transform
    def sen_trans_wrapper(val):
        return trans_sen_engine.compute_component(val, sen_pref)
        
    df['seniority_component'] = df['raw_seniority_score'].apply(sen_trans_wrapper)
    
    # Explainability
    df['seniority_mode_type'] = "multi" if sen_pref.is_multi else "single"
    df['seniority_modes_selected'] = str([m.mode_type.value for m in sen_pref.modes])
    df['seniority_combine_method'] = sen_pref.combine_method
    if sen_pref.weights:
        df['seniority_weights_used'] = str(sen_pref.weights)
    else:
        df['seniority_weights_used'] = ""

    # -----------------------------
    # 3. Other Components (Network, Company)
    # -----------------------------
    
    # Normalize safely
    def safe_log_scale(series: pd.Series) -> pd.Series:
        # fillna 0, log1p, min-max scale 0-100
        filled = pd.to_numeric(series, errors='coerce').fillna(0)
        log_vals = np.log1p(filled)
        mx = log_vals.max()
        if mx == 0: return log_vals * 0
        return (log_vals / mx) * 100.0

    df['connections_score_norm'] = safe_log_scale(df['connections_count'])
    df['followers_score_norm'] = safe_log_scale(df['followers_count'])
    
    # Company Size Map
    size_map = {
        '1-10': 10, '11-50': 20, '51-200': 30, '201-500': 40, '501-1000': 50,
        '1001-5000': 60, '5001-10000': 70, '10000+': 80
    }
    def map_size(val):
        s = str(val)
        for k, v in size_map.items():
            if k in s: return v
        return 0
    df['company_size_score'] = df['company_size_range_1'].apply(map_size)

    # -----------------------------
    # 4. Final Scoring
    # -----------------------------
    # final = w1*c1 + w2*c2 ... (components are 0-100)
    
    df['final_score'] = (
        (df['seniority_component'] * weights_config.seniority) +
        (df['keyword_score'] * weights_config.keyword) +
        (df['connections_score_norm'] * weights_config.connections) +
        (df['followers_score_norm'] * weights_config.followers) +
        (df['company_size_score'] * weights_config.company_size)
    )
    
    # -----------------------------
    # 5. Explainability
    # -----------------------------
    logger.info("Generating ranking explanations...")
    
    df['ranking_score'] = df['final_score'].round(2)
    df['ranking_reason'] = df.apply(build_ranking_reason, axis=1)
    
    print("Ranking explanation columns generated successfully.")
    
    # Sort
    df = df.sort_values(by="final_score", ascending=False)
    
    return df

def process_file(
    file_path: str,
    weights_config: WeightsConfig,
    sen_pref: SeniorityPreference,
    kw_config: KeywordConfig,
    export_opts: Dict[str, bool]
) -> None:
    
    logger.info(f"Loading {file_path}...")
    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        logger.error(f"Failed to read CSV: {e}")
        return

    # Validation
    valid, missing, df = validate_columns(df)
    if not valid:
        logger.error(f"Critical Error: Missing columns {missing}")
        return

    # RUN RANKING
    df = run_ranking(df, weights_config, sen_pref, kw_config)
    
    if df.empty:
        logger.warning("Dataframe is empty after ranking (possible filtering).")
        return

    # -----------------------------
    # Diagnostics & Export
    # -----------------------------
    
    # Basic Diagnostics
    print("\n--- DIAGNOSTICS ---")
    print(f"Total Rows: {len(df)}")
    print(f"Top Frequent GOOD matches:")
    all_good = [x for x in ";".join(df['good_matches']).split(";") if x]
    from collections import Counter
    print(Counter(all_good).most_common(5))
    
    print("\n--- PREVIEW (Top 5) ---")
    cols_preview = ['full_name', 'active_experience_title', 
                    'raw_seniority_score', 'seniority_component', 
                    'ranking_score', 'ranking_reason']
    # Use only columns that exist for preview
    valid_preview = [c for c in cols_preview if c in df.columns]
    print(df[valid_preview].head(5).to_string(index=False))

    # Reorder columns for export
    final_cols = []
    
    # 1. Required Inputs
    for col in REQUIRED_COLUMNS:
        if col in df.columns:
            final_cols.append(col)
            
    # 2. Ranking Outputs
    for col in RANKING_COLUMNS:
        if col in df.columns:
            final_cols.append(col)
            
    final_cols = list(dict.fromkeys(final_cols))
    
    df_export = df[final_cols]
    
    prefix = "ranked_output"
    if export_opts.get('csv'):
        f = f"{prefix}.csv"
        df_export.to_csv(f, index=False)
        logger.info(f"Exported {f}")
        
    if export_opts.get('excel'):
        f = f"{prefix}.xlsx"
        try:
            df_export.to_excel(f, index=False)
            logger.info(f"Exported {f}")
        except ImportError:
            logger.error("openpyxl needed for Excel export")

# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main() -> None:
    args = get_cli_args()
    setup_logging(args.verbose, args.quiet)
    
    # 1. Input File
    if args.input_file:
        fpath = args.input_file
    else:
        if sys.stdin.isatty():
            fpath = input("Enter input CSV path: ").strip().strip('"')
        else:
            logger.error("No input file provided")
            sys.exit(1)
            
    if not os.path.exists(fpath):
        logger.error(f"File not found: {fpath}")
        sys.exit(1)

    # 2. Configs (Non-interactive fallback if args missing)
    
    # Weights
    if args.weights:
        try:
            wlist = [float(x) for x in args.weights.split(',')]
            if len(wlist) != 5: raise ValueError
            wc = WeightsConfig(*wlist)
            wc.normalize()
        except:
            logger.warning("Bad weights arg, using balanced defaults.")
            wc = WeightsConfig(0.2, 0.2, 0.2, 0.2, 0.2)
    elif sys.stdin.isatty():
        wc = get_weights_interactive()
    else:
        wc = WeightsConfig(0.4, 0.2, 0.2, 0.1, 0.1)
        wc.normalize()
        
    # Keyword Config
    if args.bad_words_action == "B":
        kw_config = KeywordConfig(filter_bad_rows=True)
    else:
        kw_config = KeywordConfig(filter_bad_rows=False)
        
    # Seniority Pref
    if args.seniority_mode_type:
        # CLI Mode
        is_multi = (args.seniority_mode_type == "multi")
        modes = []
        if args.seniority_modes:
            # Parse codes
            # Simple parser reusing logic
            codes = args.seniority_modes.split(',')
            for c in codes:
                if c == 'S': modes.append(SeniorityMode(SeniorityModeType.PREFER_SENIOR))
                elif c == 'J': modes.append(SeniorityMode(SeniorityModeType.PREFER_JUNIOR))
                elif c == 'M': modes.append(SeniorityMode(SeniorityModeType.PREFER_MID, {'t': 50}))
                elif c == 'B': modes.append(SeniorityMode(SeniorityModeType.BALANCED))
                elif c == 'TR': modes.append(SeniorityMode(SeniorityModeType.TARGET_RANGE_BONUS, {'min':40,'max':60}))
        
        if not modes: modes.append(SeniorityMode(SeniorityModeType.PREFER_SENIOR))
        
        sp = SeniorityPreference(is_multi, modes, args.combine)
    elif sys.stdin.isatty():
        sp = get_seniority_pref_interactive()
    else:
        # Default
        sp = SeniorityPreference(False, [SeniorityMode(SeniorityModeType.PREFER_SENIOR)])

    # Export
    export_opts = {}
    if args.export_csv or args.export_excel:
        export_opts['csv'] = args.export_csv
        export_opts['excel'] = args.export_excel
    elif sys.stdin.isatty():
        print("\n--- EXPORT ---")
        ch = input("1) CSV, 2) Excel, 3) Both: ").strip()
        if ch in ['1', '3']: export_opts['csv'] = True
        if ch in ['2', '3']: export_opts['excel'] = True
    else:
        export_opts['csv'] = True

    process_file(fpath, wc, sp, kw_config, export_opts)
    logger.info("Done.")

if __name__ == "__main__":
    main()
