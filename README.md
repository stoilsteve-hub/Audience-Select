# Audience Prioritization Tool

A console-based Python tool to rank and prioritize contacts from CSV exports based on seniority, network size, company size, and keyword relevance.

## Features

-   **Interactive Console Wizard**: Prompts for file paths, filters, and scoring weights.
-   **Rule-Based Seniority Engine**: Calculates seniority tiers (e.g., Senior, VP, C-Suite) using a hybrid of `management_level_1` and title keywords.
-   **Keyword Relevance Engine**: Scores candidates based on "Good" (e.g., MS&T, CMC) and "Bad" (e.g., Intern, Student) phrases found in their profile.
-   **Multilingual Support**: Recognizes seniority terms in English, Spanish, French, Polish, etc.
-   **Customizable Weights**: User can adjust importance of Seniority, Connections, Followers, Company Size, and Keywords per run.
-   **Export**: Output ranked lists to CSV or Excel.

## Prerequisites

-   Python 3.10+
-   Dependencies: `pandas`, `openpyxl`, `numpy`

## Installation

1.  Clone or download this repository.
2.  Install dependencies:
    ```bash
    pip install pandas openpyxl numpy
    ```

## Usage

1.  Run the script:
    ```bash
    python3 rank_sample.py
    ```
    *Optional: Pass CSV path as argument:* `python3 rank_sample.py my_data.csv`

2.  **Follow the prompts**:
    -   **Input**: Path to your CSV file (must contain required columns like `id`, `full_name`, `management_level_1`, etc.).
    -   **Filters**: Filter by Country, Company Size, Management Level, or Keywords (press Enter to skip).
    -   **Weights**: Set relative importance (0-100) for scoring factors.
    -   **Keyword Config**: Choose `A` to Penalize bad words or `B` to Filter them out. Set boost/penalty amounts.
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

## Output

The output file will be sorted by `final_score` (descending) and include calculated fields:
-   `seniority_tier`
-   `seniority_score`
-   `keyword_score`
-   `good_match_count`
-   `bad_match_count`
-   `network_score`
-   `company_score`
-   `final_score`
