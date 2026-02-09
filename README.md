# Audience Prioritization Tool

A console-based Python tool to rank and prioritize contacts from CSV exports based on seniority, network size, company size, and keyword relevance.

## Features

-   **Interactive Console Wizard**: Prompts for file paths, filters, and scoring weights.
-   **Dynamic Seniority Engine (v2.0)**:
    -   Target specific levels (e.g. Juniors, Mid-Level, Seniors).
    -   Combine strategies with Multi-Mode support.
    -   Two-stage process: Classification (Stage A) -> Transformation (Stage B).
-   **Keyword Relevance Engine**: Scores candidates based on configurable "Good" and "Bad" phrases.
-   **Fuzzy Column Mapping**: Automatically detects and suggests mappings for missing or misspelled column headers.
-   **Progress Bars & Logging (v2.1)**:
    -   Visual feedback for long-running operations (requires `tqdm`).
    -   Detailed execution logs in `audience_ranker.log`.
    -   CLI flags for verbosity (`--verbose`, `--quiet`).
-   **Multilingual Support**: Recognizes seniority terms in English, Spanish, French, Polish, etc.
-   **Customizable Weights**: User can adjust importance of Seniority, Connections, Followers, Company Size, and Keywords per run.
-   **Export**: Output ranked lists to CSV or Excel.

## Prerequisites

-   Python 3.10+
-   Dependencies: `pandas`, `openpyxl`, `numpy`, `tqdm` (optional but recommended)

## Installation

1.  Clone or download this repository.
2.  Install dependencies:
    ```bash
    pip install pandas openpyxl numpy tqdm
    ```

## Usage

1.  **Run the script**:
    ```bash
    python3 rank_sample.py
    ```
    *Optional: Pass CSV path as argument:*
    ```bash
    python3 rank_sample.py my_data.csv
    ```

2.  **CLI Flags**:
    -   `--verbose` (`-v`): Enable debug logging (see `audience_ranker.log` and console).
    -   `--quiet` (`-q`): Suppress operational logs, showing only prompts/results.

3.  **Follow the prompts**:
    -   **Input**: Path to your CSV file. If columns mismatch, the tool will verify mappings with you.
    -   **Filters**: Filter by Country, Company Size, Management Level, or Keywords (press Enter to skip).
    -   **Weights**: Set relative importance (0-100) for scoring factors.
    -   **Keyword Config**: Choose `A` to Penalize bad words or `B` to Filter them out. Set boost/penalty amounts.
    -   **Seniority Strategy**: Choose your target audience (Seniors, Juniors, Mid-Level, etc.).
    -   **Export**: Choose CSV or Excel format.

## Configuration

-   **`seniority_config_example.json`**: (Optional) Rename to `seniority_config.json` to override default seniority mappings.

## Input CSV Format

The tool expects specific column names (all lowercase), including:
-   `id`
-   `full_name`
-   `management_level_1`
-   `active_experience_title`
-   `company_size_range_1`
-   `connections_count`
-   `active_experience_description`
-   `department_1`
-   ... (see `rank_sample.py` for full list)

*Note: The tool attempts to map columns if headers don't match exactly.*

## Output

The output file will be sorted by `final_score` (descending) and include calculated fields:
-   `seniority_tier`
-   `raw_seniority_score`
-   `seniority_component`
-   `keyword_score`
-   `good_match_count`
-   `bad_match_count`
-   `network_score`
-   `company_score`
-   `final_score`
