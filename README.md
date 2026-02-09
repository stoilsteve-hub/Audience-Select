# Audience Prioritization Tool (v3.0)

A console-based Python tool to rank and prioritize contacts from CSV exports based on seniority, network size, company size, and keyword relevance.

## Features

-   **Interactive Console Wizard**: Prompts for file paths, filters, and scoring weights.
-   **Dynamic Seniority Engine**:
    -   Target specific levels (e.g. Juniors, Mid-Level, Seniors).
    -   Combine strategies with Multi-Mode support (e.g. Junior + Mid).
    -   Two-stage process: Raw Classification -> Dynamic Transformation.
-   **Phrase-Aware Keyword Engine**:
    -   Matches phrases (e.g. "Process Development") and acronyms.
    -   Configurable Boost (Good) and Penalty (Bad) points.
    -   Option to filter out rows with Bad words entirely.
-   **Strict Column Validation**: Automatically detects and maps required columns (handles `_one` -> `_1` automatically).
-   **CLI Support**: Full automation via command-line flags.
-   **Logging**: detailed execution logs in `audience_ranker.log`.

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

The output file will be sorted by `final_score` (descending) and include:
-   `final_score`: The sorting metric.
-   `seniority_component`: The score used in the formula.
-   `raw_seniority_score`: Unmodified level score.
-   `seniority_tier`: Human-readable level.
-   `keyword_score`: Score based on good/bad matches.
-   `good_match_count`, `bad_match_count`, `good_matches`
