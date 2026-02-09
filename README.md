# Audience Prioritization Tool (v3.1)

A console-based Python tool to rank and prioritize contacts from CSV exports based on seniority, network size, company size, and keyword relevance.

## Features

-   **Interactive Console Wizard**: Prompts for file paths, filters, and scoring weights.

### 🌟 Dynamic Seniority Engine (Simplified)

We use a smart 2-stage process to ensure we find exactly who you are looking for, whether they are Interns, VPs, or anything in between.

**STAGE 1: Identify Who They Are (Raw Classification)**
First, the tool looks at every person's `Title` and `Management Level` to give them a "Raw Score" from 0 to 100.
-   *Interns* get ~10 points.
-   *Managers* get ~60 points.
-   *VPs/CXOs* get ~90+ points.
*Note: This raw score is NOT added to the final ranking yet. It just tells us "how senior" they are.*

**STAGE 2: Score Them Based on Your Goal (Dynamic Transformation)**
Now, you tell the tool who you want to target. The tool converts that Raw Score into a "Seniority Component" (0-100) that actually boosts their ranking.

**Your Options:**
1.  **Single Mode**: Pick one specific target.
    -   `prefer_senior`: Higher rank = Higher score. (Good for finding VPs).
    -   `prefer_junior`: *Inverts the score*. Interns get 100 points, VPs get 0. (Good for finding entry-level talent).
    -   `prefer_mid`: Targets a specific sweet spot (e.g., score 50). Managers get the highest points; Interns and VPs get lower points.
    -   `target_range_bonus`: You set a range (e.g., 40-60). Anyone inside gets 100 points; anyone outside gets a penalty.
    -   `balanced`: Everyone gets 50 points (Seniority doesn't matter).

2.  **Multi Mode**: Mix and match!
    -   Example: Want *Juniors* AND *Mid-Level*? Select `J,M`.
    -   The tool calculates scores for both and combines them (Average, Max, or Weighted).

---

-   **Phrase-Aware Keyword Engine**:
    -   Matches phrases (e.g. "Process Development") and acronyms.
    -   Configurable Boost (Good) and Penalty (Bad) points.
    -   Option to filter out rows with Bad words entirely.
-   **Explainable AI Ranking**:
    -   `ranking_score`: Final score rounded for readability.
    -   `ranking_reason`: Auto-generated sentence explaining *why* a candidate was ranked high (e.g. "Seniority boost: 85 (Junior-target); Keyword relevance: 64...").
-   **Strict Column Validation**: Automatically detects and maps required columns (handles `_one` -> `_1` automatically).
-   **CLI Support**: Full automation via command-line flags.
-   **Logging**: Detailed execution logs in `audience_ranker.log`.

## Prerequisites

-   Python 3.10+
-   Dependencies: `pandas`, `openpyxl`, `numpy`, `tqdm` (optional)

## Usage

1.  **Interactive Mode**:
    ```bash
    python3 rank_sample.py
    ```

2.  **CLI Automation**:
    ```bash
    python3 rank_sample.py input.csv --seniority-mode-type multi --seniority-modes J,M --combine average --export-csv --quiet
    ```

### CLI Flags
-   `--weights`: Comma-separated weights (Seniority, Keyword, Connections, Followers, CompanySize). Example: `40,20,10,10,20`.
-   `--seniority-mode-type`: `single` or `multi`.
-   `--seniority-modes`: Codes: `S` (Senior), `J` (Junior), `M` (Mid), `B` (Balanced), `TR` (Target Range).
-   `--combine`: `average`, `max`, or `weighted`.
-   `--bad-words-action`: `A` (Penalize), `B` (Filter Out).
-   `--verbose` / `-v`: Debug logging.
-   `--quiet` / `-q`: Minimal output.

## Interactive Commands Reference

When running the tool without CLI flags, you will use the **Interactive Wizard**. Here is a list of all prompts and valid inputs:

| Step | Prompt / Context | Valid Inputs | Description |
| :--- | :--- | :--- | :--- |
| **1. File Input** | `Enter input CSV path:` | File path (e.g. `data.csv`) | The path to your source file. Drag-and-drop works in most terminals. |
| **2. Column Mapping** | `Use 'X' for 'Y'? [y/n]:` | `y` or `n` | **y**: Accept the suggested column name.<br>**n**: Reject it. |
| **2. Column Mapping** | `Enter column name for 'Y':` | Column name | Manually type the correct header name from your CSV. |
| **3. Weights** | `Seniority (default 40):` | Number (0-100) | Importance of seniority. Press `Enter` to accept default |
| **3. Weights** | `Keywords (default 20):` | Number (0-100) | Importance of keyword matches. |
| **3. Weights** | `Connections...` etc. | Number (0-100) | Weights for other factors. |
| **4. Seniority Type** | `Choose 1 or 2:` | `1` or `2` | **1 (Single)**: Use one strategy.<br>**2 (Multi)**: Combine strategies. |
| **5. Single Mode** | `Choice:` | `1` or `S` | **Prefer Senior**: Higher rank = better. |
| | | `2` or `J` | **Prefer Junior**: Entry level = better. |
| | | `3` or `M` | **Prefer Mid**: Managers/Leads = better. |
| | | `4` or `B` | **Balanced**: Seniority ignored (flat score). |
| | | `5` or `TR` | **Target Range**: Bonus for specific score range. |
| **5. Multi Mode** | `Codes:` | `S, J, M, B, TR` | Comma-separated list (e.g., `J,M` for Junior + Mid). |
| **5. Multi Mode** | `Choice:` | `1`, `2`, `3` | **1**: Average<br>**2**: Max<br>**3**: Weighted |
| **6. Export** | `1) CSV, 2) Excel, 3) Both:` | `1`, `2`, `3` | Choose your output format. |

## Input CSV Format

Required columns (all lowercase):
-   `id`
-   `full_name`
-   `linkedin_url`
-   `active_experience_title`
-   `management_level_1`
-   `company_id_1`
-   `company_name_1`
-   `company_size_range_1`
-   `company_categories_and_keywords_1`
-   `company_industry_1`
-   `company_employees_count_1`
-   `department_1`
-   `active_experience_description`
-   `location_country`
-   `connections_count`
-   `followers_count`

## Output Columns

The output file (CSV/Excel) will **strictly preserve** the original Input Columns in order, followed by the Ranking Columns.

**1. Input Columns** (Preserved exactly as provided):
-   `id`, `full_name`, `linkedin_url`, `active_experience_title`, `management_level_1`, ...

**2. Ranking Columns** (Appended):
-   `ranking_score`: The final score rounded to 2 decimals.
-   `ranking_reason`: Human-readable explanation of the score.
-   `final_score`: The raw sorting metric.
-   `seniority_component`: The score used in the formula.
-   `raw_seniority_score`: Unmodified level score.
-   `seniority_tier`: Human-readable level.
-   `keyword_score`: Score based on good/bad matches.
-   `good_match_count`, `bad_match_count`, `good_matches`
