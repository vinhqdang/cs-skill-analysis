import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os

def main():
    print("Loading LLM processed skills dataset...")
    df = pd.read_json("data/processed/jobs_with_skills_both.json")
    
    # 1. Prepare Spatial and Temporal data
    # Convert epoch millis to datetime
    df["date"] = pd.to_datetime(df["date_posted"], unit="ms", errors="coerce")
    
    # Filter dates: remove outliers before 2025 and futures
    df = df[(df["date"] >= "2025-10-01") & (df["date"] <= "2026-12-31")]
    
    # Resample by week instead of month since most live job board data is recent (last 30-90 days)
    df["time_period"] = df["date"].dt.to_period("W")
    
    # If the region column isn't properly populated from jobspy, deduce from location or file origin
    if "region" not in df.columns or df["region"].isnull().all():
        # Fallback to text matching for basic region assignment if missing
        def get_region(loc):
            loc_str = str(loc).lower()
            if "vn" in loc_str or "vietnam" in loc_str or "hanoi" in loc_str or "ho chi minh" in loc_str:
                return "Vietnam"
            elif "sg" in loc_str or "singapore" in loc_str or "asia" in loc_str:
                return "Asia"
            else:
                return "Global"
        df["region"] = df["location"].apply(get_region)
    
    # Ensure case-insensitivity formatting
    df["hard_skills"] = df["hard_skills"].apply(lambda x: [str(s).title() for s in x] if isinstance(x, list) else [])
    df["soft_skills"] = df["soft_skills"].apply(lambda x: [str(s).title() for s in x] if isinstance(x, list) else [])

    # Filter out periods with too few jobs to avoid high-variance spikes mimicking a "downward trend"
    period_totals = df.groupby("time_period").size()
    valid_periods = period_totals[period_totals >= 50].index
    df_valid = df[df["time_period"].isin(valid_periods)].copy()

    def get_top_skills(df_source, skill_col, top_n=3):
        exploded = df_source.explode(skill_col).dropna(subset=[skill_col])
        exploded = exploded[exploded[skill_col] != ""]
        top_skills = exploded[skill_col].value_counts().head(top_n).index.tolist()
        
        time_df = exploded[exploded[skill_col].isin(top_skills)].dropna(subset=["time_period", "date"])
        time_counts = time_df.groupby(["time_period", skill_col]).size().reset_index(name="count")
        time_counts["demand_pct"] = time_counts.apply(lambda r: (r["count"] / period_totals[r["time_period"]]) * 100, axis=1)
        time_counts["date_plot"] = time_counts["time_period"].dt.start_time
        time_counts = time_counts.rename(columns={skill_col: "skill"})
        return time_counts

    # Setup Output Dir
    out_dir = "data/output/report_figures"
    os.makedirs(out_dir, exist_ok=True)
    
    # Set seaborn style
    sns.set_theme(style="darkgrid", context="talk")
    plt.style.use("dark_background")

    # --- Combined Chart: Top 3 Hard vs Soft Skills Over Time ---
    print("Generating Combined Time Series Chart...")
    hard_time = get_top_skills(df_valid, "hard_skills", 3)
    hard_time["type"] = "Hard Skill"
    
    soft_time = get_top_skills(df_valid, "soft_skills", 3)
    soft_time["type"] = "Soft Skill"
    
    combined_time = pd.concat([hard_time, soft_time])
    
    plt.figure(figsize=(15, 8))
    ax = sns.lineplot(
        data=combined_time, 
        x="date_plot", 
        y="demand_pct", 
        hue="skill", 
        style="type", 
        markers=["o", "s"], 
        dashes=[(1, 0), (2, 2)],
        linewidth=3, 
        palette="husl",
        markersize=10
    )
    plt.title("Weekly Evolution of Top Demands: Hard vs. Soft Skills", fontsize=18, fontweight="bold")
    plt.xlabel("Date Posted (Week)", fontsize=14)
    plt.ylabel("Percentage of Job Postings (%)", fontsize=14)
    
    if not combined_time.empty:
        plt.xlim(combined_time["date_plot"].min(), combined_time["date_plot"].max())
        ax.xaxis.set_major_locator(plt.MaxNLocator(8))
    
    plt.xticks(rotation=45)
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left', title="Skill (line=Hard, dash=Soft)")
    plt.annotate(
        "Low-volume weeks (N < 50)\nfiltered to reduce noise", 
        xy=(0.02, 0.95), xycoords='axes fraction', 
        fontsize=11, bbox=dict(boxstyle="round,pad=0.3", fc="gray", alpha=0.3)
    )
    plt.tight_layout()
    plt.savefig(f"{out_dir}/combined_skills_over_time.png", dpi=300)
    plt.close()

    # --- Combined Geographic Chart: Top Hard + Soft Skills by Region ---
    print("Generating Combined Geographic Chart...")

    def get_geo_skills(df_source, skill_col, top_n=8):
        exploded = df_source.explode(skill_col).dropna(subset=[skill_col])
        exploded = exploded[exploded[skill_col] != ""]
        top_skills = exploded[skill_col].value_counts().head(top_n).index.tolist()
        geo = exploded[exploded[skill_col].isin(top_skills)]
        geo_counts = geo.groupby([skill_col, "region"]).size().reset_index(name="count")
        region_totals = df_source.groupby("region").size()
        geo_counts["demand_pct"] = geo_counts.apply(lambda r: (r["count"] / region_totals[r["region"]]) * 100, axis=1)
        geo_counts = geo_counts.rename(columns={skill_col: "skill"})
        return geo_counts, top_skills

    hard_geo, hard_top = get_geo_skills(df, "hard_skills", 8)
    hard_geo["type"] = "Hard"
    soft_geo, soft_top = get_geo_skills(df, "soft_skills", 5)
    soft_geo["type"] = "Soft"

    combined_geo = pd.concat([hard_geo, soft_geo])
    # Create skill label with type for legend
    combined_geo["skill_label"] = combined_geo["skill"] + " [" + combined_geo["type"] + "]"

    plt.figure(figsize=(14, 10))
    ax2 = sns.barplot(
        data=combined_geo,
        x="demand_pct",
        y="skill_label",
        hue="region",
        palette="magma",
        orient="h"
    )
    plt.title("Top Skills Demand by Region: Hard & Soft (2026)", fontsize=18, fontweight="bold")
    plt.xlabel("% of Job Postings Requiring Skill", fontsize=14)
    plt.ylabel("")
    plt.yticks(rotation=45, ha="right", fontsize=11)
    plt.legend(title="Region", title_fontsize="12", bbox_to_anchor=(1.02, 1), loc='upper left')
    plt.tight_layout()
    plt.savefig(f"{out_dir}/combined_skills_by_geography.png", dpi=300)
    plt.close()
    
    print(f"All charts successfully generated in {out_dir}/")

if __name__ == "__main__":
    main()
