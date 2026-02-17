import streamlit as st
import pandas as pd
import io
import time
import altair as alt

# Import logic from the refactored script
from rank_sample import (
    run_ranking,
    validate_columns,
    WeightsConfig,
    KeywordConfig,
    SeniorityPreference,
    SeniorityMode,
    SeniorityModeType,
    REQUIRED_COLUMNS,
    RANKING_COLUMNS,
    sanitize_dataframe
)

# Page Conf
st.set_page_config(
    page_title="Audience Select", 
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS Styling for Modern Look
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;800&display=swap');
    
    html, body, [class*="css"]  {
        font-family: 'Inter', sans-serif;
    }

    .main-title {
        font-size: 4rem !important;
        font-weight: 800 !important;
        letter-spacing: -0.05em !important;
        color: #1E1E1E;
        margin-bottom: 0px !important;
        line-height: 1 !important;
        text-transform: uppercase;
    }
    
    .signature {
        font-size: 0.85rem !important;
        font-weight: 400 !important;
        color: #888888;
        opacity: 0.6;
        margin-top: -5px !important;
        margin-bottom: 30px !important;
        letter-spacing: 0.05em;
    }

    .kpi-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 12px;
        text-align: center;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -1px rgba(0,0,0,0.06);
        border: 1px solid #e1e4e8;
    }
    
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        height: 3.5em;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.02em;
        transition: all 0.2s ease;
    }
    
    .stButton>button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }

    /* Hide default menu */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# =============================================================================
# DOCUMENTATION PAGE
# =============================================================================
def render_docs():
    st.markdown('<p class="main-title">REFERENCE MANUAL</p>', unsafe_allow_html=True)
    st.markdown('<p class="signature">Designed and Programmed by Steve Zhelyazkov</p>', unsafe_allow_html=True)
    
    st.markdown("Everything you need to know to become a ranking expert.")
    
    tab1, tab2, tab3, tab4 = st.tabs(["💡 Core Concepts", "🎯 Seniority Strategies", "🔍 Keyword Engine", "📤 Output Types"])
    
    with tab1:
        st.header("How Scoring Works")
        st.markdown("""
        The tool calculates a **Final Score (0-100)** for every person based on 5 pillars. 
        You control the importance of each pillar using the **Weights** slider.
        """)
        
        c1, c2, c3 = st.columns(3)
        with c1:
            st.info("**1. Seniority**\n\nHow well they match your target level (e.g. VP vs Intern).")
        with c2:
            st.info("**2. Keywords**\n\nPresence of 'Good' (Boost) vs 'Bad' (Penalty) terms.")
        with c3:
            st.info("**3. Company Size**\n\nLarger companies = higher score (10-80 pts).")
            
        c1, c2 = st.columns(2)
        with c1:
            st.info("**4. Network (Connections)**\n\nLogarithmic scale (0-100). More connections = higher influence.")
        with c2:
            st.info("")

    with tab2:
        st.header("The Seniority Engine")
        st.markdown("This is the most powerful part of the tool. It works in two stages:")
        st.code("Stage 1 (Identity): Are they a VP or an Intern? (Raw Score 0-100)\nStage 2 (Target): Do I WANT a VP or an Intern? (Final Component Score)")
        
        st.divider()
        st.subheader("🛠 Single Mode Strategies")
        st.markdown("Use these when you have **one specific target**.")
        
        cols = st.columns(2)
        with cols[0]:
            st.markdown("#### `Prefer Senior` (High Level)")
            st.write("✅ **Best for:** Finding Decision Makers (VPs, Directors).")
            st.graphviz_chart('''
            digraph {
                rankdir=LR
                "VP (Raw 90)" -> "Score 90"
                "Intern (Raw 10)" -> "Score 10"
            }
            ''')
            
        with cols[1]:
            st.markdown("#### `Prefer Junior` (Entry Level)")
            st.write("✅ **Best for:** Finding talent to train.")
            st.graphviz_chart('''
            digraph {
                rankdir=LR
                "VP (Raw 90)" -> "Score 10"
                "Intern (Raw 10)" -> "Score 90"
            }
            ''')
            
        cols = st.columns(2)
        with cols[0]:
            st.markdown("#### `Prefer Mid` (Managers)")
            st.write("✅ **Best for:** Finding Team Leads / Managers.")
            st.write("Scores peak at **50** (Manager level). Both Interns and VPs get lower scores.")
            
        with cols[1]:
            st.markdown("#### `Target Range`")
            st.write("✅ **Best for:** Surgical precision.")
            st.write("Only gives 100 points if they are effectively inside your Min-Max range.")

        st.divider()
        st.subheader("⚡ Multi Mode Strategies")
        st.markdown("Use these when you want a **mix** of candidates (e.g., 'Juniors AND Managers').")
        
        st.markdown("#### Combination Methods")
        m1, m2, m3 = st.columns(3)
        
        m1.markdown("**1. Average**")
        m1.caption("The Balanced Approach")
        m1.write("Takes the average of all your targets. Good for finding 'well-rounded' matches.")
        
        m2.markdown("**2. Max**")
        m2.caption("The Inclusive Approach")
        m2.write("If they match ANY of your targets perfectly, they get a high score. Best for diverse hiring.")
        
        m3.markdown("**3. Weighted**")
        m3.caption("The Precision Approach")
        m3.write("You decide importance. e.g. 'Manager is 70% important, Junior is 30%'.")

    with tab4:
        st.header("Understanding the Output")
        st.markdown("The tool adds these columns to your CSV:")
        
        data = {
            "Column Name": ["ranking_score", "ranking_reason", "seniority_tier", "good_matches"],
            "Description": ["Final 0-100 Score. Sort by this.", "AI explanation of WHY they got that score.", "Human-readable level (e.g. 'Director').", "List of keywords found in their profile."]
        }
        st.table(data)

def validate_columns_safe(df):
    # Normalize headers
    df.columns = df.columns.astype(str).str.strip().str.lower()
    
    # Check
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    
    # Auto-fix _one -> _1
    rename_map = {}
    for m in missing:
        if m.endswith("_1"):
           legacy = m.replace("_1", "_one")
           if legacy in df.columns:
               rename_map[legacy] = m
    
    if rename_map:
        df = df.rename(columns=rename_map)
        missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]

    if missing:
        return False, missing, df

    # -------------------------------------------------------------------------
    # ENFORCE COLUMN ORDER (User Request)
    # -------------------------------------------------------------------------
    EXPECTED_ORDER = [
        "id", "first_name", "full_name", "active_experience_title", "company_name_1", 
        "linkedin_url", "company_id_1", "location_country", "connections_count", 
        "management_level_1", "company_size_range_1", "company_categories_and_keywords_1", 
        "company_industry_1", "company_employees_count_1", "department_1", 
        "active_experience_description"
    ]
    
    # Only reorder if we have all these columns (or reorder what we have)
    # We will prioritize this order, and append any extra columns at the end
    existing_cols = [c for c in EXPECTED_ORDER if c in df.columns]
    extra_cols = [c for c in df.columns if c not in existing_cols]
    
    df = df[existing_cols + extra_cols]
    
    return True, [], df

# =============================================================================
# TOOL PAGE
# =============================================================================
def render_tool():
    st.markdown('<p class="main-title">AUDIENCE SELECT</p>', unsafe_allow_html=True)
    st.markdown('<p class="signature">Designed and Programmed by Steve Zhelyazkov</p>', unsafe_allow_html=True)
    
    # -------------------------------------------------------------
    # CONFIGURATION
    # -------------------------------------------------------------
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # 1. Weights expander
        with st.expander("⚖️ Scoring Weights", expanded=False):
            w_seniority = st.slider("Seniority", 0, 100, 40)
            w_keyword = st.slider("Keywords", 0, 100, 20)
            w_connections = st.slider("Connections", 0, 100, 20)
            w_company = st.slider("Company Size", 0, 100, 10)

        # 2. Keyword expander
        with st.expander("📝 Keyword Settings", expanded=False):
            filter_bad = st.checkbox("Filter 'Bad' Matches?", value=False, help="Remove rows containing negative keywords completely.")

        # 3. Seniority Target
        st.subheader("🎯 Seniority Strategy")
        sen_mode_type = st.selectbox("Mode Type", ["Single", "Multi"], help="Choose one specific target or combine multiple strategies.")

        sp_modes = []
        sp_combine = "average"
        sp_weights = None

        if sen_mode_type == "Single":
            mode_choice = st.radio(
                "Target Strategy",
                options=["Prefer Senior", "Prefer Junior", "Prefer Mid", "Balanced", "Target Range"],
                captions=["High Level (VP/Director)", "Entry Level", "Managers/Leads", "Ignore Seniority", "Specific Score Zone"]
            )
            
            if mode_choice == "Prefer Senior":
                sp_modes.append(SeniorityMode(SeniorityModeType.PREFER_SENIOR))
            elif mode_choice == "Prefer Junior":
                sp_modes.append(SeniorityMode(SeniorityModeType.PREFER_JUNIOR))
            elif mode_choice == "Prefer Mid":
                target_score = st.number_input("Target Score (0-100)", 0, 100, 50)
                sp_modes.append(SeniorityMode(SeniorityModeType.PREFER_MID, {"t": target_score}))
            elif mode_choice == "Balanced":
                sp_modes.append(SeniorityMode(SeniorityModeType.BALANCED))
            elif mode_choice == "Target Range":
                c1, c2 = st.columns(2)
                range_min = c1.number_input("Min", 0, 100, 40)
                range_max = c2.number_input("Max", 0, 100, 60)
                sp_modes.append(SeniorityMode(SeniorityModeType.TARGET_RANGE_BONUS, {"min": range_min, "max": range_max}))
            sp = SeniorityPreference(is_multi=False, modes=sp_modes)

        else:
            selected_options = st.multiselect(
                "Strategies to Combine",
                options=["Senior", "Junior", "Mid", "Balanced", "Range"],
                default=["Senior", "Mid"]
            )
            
            for opt in selected_options:
                if opt == "Senior": sp_modes.append(SeniorityMode(SeniorityModeType.PREFER_SENIOR))
                elif opt == "Junior": sp_modes.append(SeniorityMode(SeniorityModeType.PREFER_JUNIOR))
                elif opt == "Mid":
                    t = st.number_input(f"Target 'Mid'", 0, 100, 50, key="mid_multi")
                    sp_modes.append(SeniorityMode(SeniorityModeType.PREFER_MID, {"t": t}))
                elif opt == "Balanced": sp_modes.append(SeniorityMode(SeniorityModeType.BALANCED))
                elif opt == "Range":
                    rmin = st.number_input("Min", 0, 100, 40, key="rmin_multi")
                    rmax = st.number_input("Max", 0, 100, 60, key="rmax_multi")
                    sp_modes.append(SeniorityMode(SeniorityModeType.TARGET_RANGE_BONUS, {"min": rmin, "max": rmax}))
            
            if len(sp_modes) > 0:
                sp_combine = st.selectbox("Combine Method", ["Average", "Max", "Weighted"]).lower()
                if sp_combine == "weighted":
                    st.caption("Adjust relative importance:")
                    raw_weights = []
                    for i, m in enumerate(selected_options):
                        val = st.slider(f"{m}", 0, 100, 50, key=f"w_{i}")
                        raw_weights.append(float(val))
                    sp_weights = raw_weights
            
            sp = SeniorityPreference(is_multi=True, modes=sp_modes, combine_method=sp_combine, weights=sp_weights)

        # Config Objects
        wc = WeightsConfig(float(w_seniority), float(w_keyword), float(w_connections), float(w_company))
        wc.normalize()
        kc = KeywordConfig(filter_bad_rows=filter_bad)

    # -------------------------------------------------------------
    # MAIN UI
    # -------------------------------------------------------------
    uploaded_file = st.file_uploader("📂 Upload CSV File", type=["csv"], help="Drag and drop your LinkedIn export here.")

    if uploaded_file:
        try:
            # 1. ATTEMPT ROBUST READ
            try:
                # Try reading with Python engine which is more forgiving
                df = pd.read_csv(uploaded_file, on_bad_lines='skip', engine='python')
                
                # FIX: Auto-detect semicolon separator (common in some regions/Excel)
                if len(df.columns) == 1 and ';' in str(df.columns[0]):
                    st.toast("Detected semicolon separator. Reloading...", icon="🔄")
                    uploaded_file.seek(0)
                    df = pd.read_csv(uploaded_file, sep=';', on_bad_lines='skip', engine='python')
                
            except Exception as e_read:
                st.warning(f"⚠️ First read attempt failed: {e_read}. Retrying with fallback...")
                uploaded_file.seek(0)
                try:
                    df = pd.read_csv(uploaded_file, on_bad_lines='skip')
                except Exception as e_final:
                    st.error(f"❌ CRITICAL ERROR: Could not read this CSV file.\n\nError details: {e_final}")
                    st.stop()

            # 2. VALIDATE COLUMNS (SAFE MODE)
            valid, missing, df = validate_columns_safe(df)
            
            # -------------------------------------------------------------
            # SANITIZE DATA (Clean Names) -- Must run AFTER validation/renaming
            # -------------------------------------------------------------
            if valid:
                df = sanitize_dataframe(df)
            
            if not valid:
                st.warning(f"Debug - Found Columns: {list(df.columns)}")
                st.error(f"❌ Missing required columns: {missing}")
                st.info("The app cannot proceed without these columns. Please check your CSV headers.")
            else:
                st.success(f"✅ Successfully loaded {len(df)} candidates!")

                # -------------------------------------------------------------
                # DEDUPLICATION LOGIC
                # -------------------------------------------------------------
                if 'linkedin_url' in df.columns:
                    duplicate_count = df.duplicated(subset=['linkedin_url'], keep=False).sum()
                    if duplicate_count > 0:
                        with st.spinner(f"Found {duplicate_count} potential duplicates. Auto-cleaning..."):
                            # Calculate "Data Density" (number of non-null fields)
                            df['data_density'] = df.notnull().sum(axis=1)
                            
                            # Sort by URL (to group) and Density (desc)
                            df = df.sort_values(by=['linkedin_url', 'data_density'], ascending=[True, False])
                            
                            before_dedup = len(df)
                            # Keep the first one (highest density)
                            df = df.drop_duplicates(subset=['linkedin_url'], keep='first')
                            
                            # Cleanup helper col
                            df = df.drop(columns=['data_density'])
                            
                            removed = before_dedup - len(df)
                            if removed > 0:
                                st.info(f"🧹 Smart Cleaner: Removed **{removed}** duplicate profiles (kept the ones with most data).")


                # -------------------------------------------------------------
                # COUNTRY FILTER
                # -------------------------------------------------------------
                st.sidebar.divider()
                st.sidebar.header("🌍 Location Filter")
                
                if 'location_country' in df.columns:
                    all_countries = sorted(df['location_country'].dropna().unique().tolist())
                    
                    if not all_countries:
                        st.sidebar.warning("No country data found in CSV.")
                    else:
                        selected_countries = st.sidebar.multiselect(
                            "Select Countries to Keep",
                            options=all_countries,
                            help="Leave empty to keep EVERYONE."
                        )
                        
                        if selected_countries:
                            rows_before = len(df)
                            df = df[df['location_country'].isin(selected_countries)]
                            rows_after = len(df)
                            st.sidebar.caption(f"Filtered: {rows_before} → {rows_after} candidates")
                            
                            if df.empty:
                                st.error("⚠️ You filtered out ALL candidates! Please select more countries.")
                                st.stop()
                else:
                    st.sidebar.warning("Column 'location_country' missing. Cannot filter.")

                # Company Filter (Exclude)
                st.sidebar.header("🏢 Company Filter")
                if 'company_name_1' in df.columns:
                    # Calculate counts for display (based on current filtered data)
                    company_counts = df['company_name_1'].value_counts().to_dict()
                    all_companies = sorted(df['company_name_1'].dropna().astype(str).unique().tolist())
                    
                    exclude_companies = st.sidebar.multiselect(
                        "Select Companies to Exclude",
                        options=all_companies,
                        format_func=lambda x: f"{x} ({company_counts.get(x, 0)})",
                        help="Any company selected here will be REMOVED from the analysis."
                    )
                    
                    if exclude_companies:
                        rows_before = len(df)
                        df = df[~df['company_name_1'].isin(exclude_companies)]
                        rows_after = len(df)
                        st.sidebar.caption(f"Excluded: {rows_before - rows_after} candidates")
                        
                        if df.empty:
                            st.error("⚠️ You filtered out ALL candidates! Please check your filters.")
                            st.stop()
                else:
                    st.sidebar.warning("Column 'company_name_1' missing. Cannot filter.")
                
                # -------------------------------------------------------------
                # COMPANY DENSITY CONTROL
                # -------------------------------------------------------------
                st.sidebar.markdown("---")
                st.sidebar.header("📊 Density Control")
                
                density_enabled = st.sidebar.checkbox("Enable Density Limits", value=False, help="Limit how many people per company are shown.")
                density_mode = "Top X"
                d_top_n = 50
                d_range_min = 50
                d_range_max = 100
                
                if density_enabled:
                    density_mode = st.sidebar.radio("Strategy", ["Top X", "Range"], horizontal=True)
                    if density_mode == "Top X":
                        d_top_n = st.sidebar.number_input("Max People per Company", 1, 500, 50)
                        st.sidebar.caption(f"Keeps the top {d_top_n} highest ranked people.")
                    else:
                        d_range_min = st.sidebar.number_input("Start Rank (Min)", 1, 500, 50)
                        d_range_max = st.sidebar.number_input("End Rank (Max)", 2, 1000, 100)
                        st.sidebar.caption(f"Keeps people ranked #{d_range_min} to #{d_range_max} within their company.")
                # Big Run Button
                if st.button("🚀 Rank My Audience", type="primary"):
                    
                    # STATUS CONTAINER
                    with st.status("Processing Data...", expanded=True) as status:
                        st.write("🔍 Parsing CSV & Keywords...")
                        time.sleep(0.5) 
                        st.write("🧮 Calculating Seniority Scores...")
                        ranked_df = run_ranking(df, wc, sp, kc)
                        
                        # -----------------------------------------------------
                        # APPLY DENSITY FILTER
                        # -----------------------------------------------------
                        if density_enabled and 'company_name_1' in ranked_df.columns:
                            st.write("📉 Applying Density Limits...")
                            
                            # Sort by company and then by score (descending)
                            ranked_df = ranked_df.sort_values(by=['company_name_1', 'ranking_score'], ascending=[True, False])
                            
                            if density_mode == "Top X":
                                # Group by company and take top N
                                ranked_df = ranked_df.groupby('company_name_1').head(d_top_n)
                            else:
                                # Range Mode (e.g. 50 to 100)
                                # We need a cumulative count per group
                                ranked_df['temp_rank_in_company'] = ranked_df.groupby('company_name_1').cumcount() + 1
                                
                                # Filter range. Note: d_range_min is inclusive start (e.g. 51)
                                mask = (ranked_df['temp_rank_in_company'] >= d_range_min) & (ranked_df['temp_rank_in_company'] <= d_range_max)
                                ranked_df = ranked_df[mask].drop(columns=['temp_rank_in_company'])
                                
                            # Re-sort by final score globally for the view
                            ranked_df = ranked_df.sort_values(by="ranking_score", ascending=False)

                        st.write("📊 Generating Charts & Insights...")
                        time.sleep(0.3)
                        status.update(label="Ranking Complete!", state="complete", expanded=False)
                    
                    if ranked_df.empty:
                        st.error("No candidates remained after filtering!")
                    else:
                        st.balloons()
                        # Save to session state
                        st.session_state['ranked_df'] = ranked_df
                        st.rerun()

                # PERSISTENT RESULTS DISPLAY
                if 'ranked_df' in st.session_state:
                    ranked_df = st.session_state['ranked_df']
                    
                    # DASHBOARD (KPIs)
                    st.divider()
                    k1, k2, k3, k4 = st.columns(4)
                    k1.metric("Total Candidates", f"{len(ranked_df):,}")
                    k2.metric("Top Score", f"{ranked_df['ranking_score'].max()}", delta="Max Possible: 100")
                    k3.metric("Avg Score", f"{ranked_df['ranking_score'].mean():.1f}")
                    top_tier = ranked_df['seniority_tier'].mode()[0] if not ranked_df.empty else "N/A"
                    k4.metric("Most Common Level", top_tier)
                    
                    # CHARTS
                    st.subheader("📈 Ranking Insights")
                    c1, c2 = st.columns(2)
                    
                    with c1:
                        chart_data = ranked_df['seniority_tier'].value_counts().reset_index()
                        chart_data.columns = ['Tier', 'Count']
                        chart = alt.Chart(chart_data).mark_bar().encode(
                            x=alt.X('Count', title='Candidates'),
                            y=alt.Y('Tier', sort='-x', title=None),
                            color=alt.Color('Tier', legend=None),
                            tooltip=['Tier', 'Count']
                        ).properties(height=300, title="Seniority Distribution")
                        st.altair_chart(chart, use_container_width=True)
                        
                    with c2:
                        hist = alt.Chart(ranked_df).mark_bar().encode(
                            alt.X("ranking_score", bin=alt.Bin(maxbins=20), title="Score Range"),
                            y='count()',
                            color=alt.value("#ff4b4b")
                        ).properties(height=300, title="Score Distribution")
                        st.altair_chart(hist, use_container_width=True)

                    # MODERN TABLE
                    st.subheader("🏆 Leading Candidates")
                    
                    final_cols = []
                    for col in REQUIRED_COLUMNS: 
                        if col in ranked_df.columns: final_cols.append(col)
                    for col in RANKING_COLUMNS:
                        if col in ranked_df.columns: final_cols.append(col)
                    
                    ranked_df_display = ranked_df[final_cols]
                    
                    st.dataframe(
                        ranked_df_display,
                        column_order=("ranking_score", "full_name", "active_experience_title", "company_name_1", "seniority_tier", "linkedin_url", "ranking_reason"),
                        column_config={
                            "ranking_score": st.column_config.ProgressColumn(
                                "Score",
                                help="Final Ranking Score (0-100)",
                                format="%.1f",
                                min_value=0,
                                max_value=100,
                            ),
                            "linkedin_url": st.column_config.LinkColumn("Profile"),
                            "ranking_reason": st.column_config.TextColumn("Why?", width="large"),
                            "full_name": st.column_config.TextColumn("Name", width="medium"),
                        },
                        hide_index=True,
                        use_container_width=True,
                        height=400
                    )
                    
                    with st.expander("Show Full Data Table"):
                        st.dataframe(ranked_df_display)

                    # DOWNLOADS
                    st.divider()
                    st.header("📥 Export")
                    d1, d2, d3 = st.columns([1,1,2])
                    
                    csv = ranked_df.to_csv(index=False).encode('utf-8-sig')
                    d1.download_button("📄 Download CSV", csv, "ranked_audience.csv", "text/csv", key='dl-csv')
                    
                    buffer = io.BytesIO()

                    # Sanitize for Excel (remove illegal chars and truncate)
                    def clean_data_for_excel(val):
                        if isinstance(val, str):
                            # Remove control chars (0-31) except tab(9), newline(10), cr(13)
                            import re
                            val = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F]', '', val)
                            return val[:32000] # Truncate to safe limit
                        return val

                    df_export = ranked_df.copy()
                    for col in df_export.select_dtypes(include=['object']):
                        df_export[col] = df_export[col].apply(clean_data_for_excel)

                    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                        df_export.to_excel(writer, index=False, sheet_name='Ranked')
                    
                    excel_data = buffer.getvalue()
                    
                    d2.download_button(
                        label="📊 Download Excel", 
                        data=excel_data, 
                        file_name="ranked_audience.xlsx", 
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
                        key='dl-xlsx'
                    )

        except Exception as e:
            st.error(f"Something went wrong: {e}")

# =============================================================================
# APP ROUTER
# =============================================================================

# Sidebar Nav
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["🚀 Ranker Tool", "📚 Reference Manual"])
st.sidebar.divider()

if page == "🚀 Ranker Tool":
    render_tool()
else:
    render_docs()
