import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os

# ─────────────────────────────────────────────
# Global style: white background for ALL charts
# ─────────────────────────────────────────────
sns.set_theme(style="whitegrid", context="talk")
plt.rcParams.update({
    "figure.facecolor": "white",
    "axes.facecolor":   "white",
    "savefig.facecolor": "white",
    "font.family": "sans-serif",
})

OUT_DIR = "data/output/report_figures"
os.makedirs(OUT_DIR, exist_ok=True)

def main():
    print("Loading dataset...")
    df = pd.read_json("data/processed/jobs_with_skills_both.json")

    # ── Dates ──────────────────────────────────────────────────────────────
    df["date"] = pd.to_datetime(df["date_posted"], unit="ms", errors="coerce")
    df_dated   = df.dropna(subset=["date"]).copy()
    # Filter to 2025+ only — 2023/2024 have <5 jobs and add no signal
    df_dated   = df_dated[df_dated["date"] >= "2025-01-01"]
    df_dated["month"] = df_dated["date"].dt.to_period("M")

    # ── Region from 'region' column or fallback from location ───────────────
    if "region" not in df_dated.columns or df_dated["region"].isnull().all():
        def _region(loc):
            s = str(loc).lower()
            if any(k in s for k in ("vn", "vietnam", "hanoi", "ho chi minh")):
                return "Vietnam"
            elif any(k in s for k in ("sg", "singapore", "asia")):
                return "Asia"
            return "Global"
        df_dated["region"] = df_dated["location"].apply(_region)
    df_dated["region"] = df_dated["region"].fillna("Global")

    # ── Normalise case ──────────────────────────────────────────────────────
    def _title_list(x):
        return [str(s).strip().title() for s in x if str(s).strip()] if isinstance(x, list) else []

    df_dated["hard_skills"] = df_dated["hard_skills"].apply(_title_list)
    df_dated["soft_skills"] = df_dated["soft_skills"].apply(_title_list)
    df["hard_skills"] = df["hard_skills"].apply(_title_list)
    df["soft_skills"] = df["soft_skills"].apply(_title_list)

    # ── Monthly totals ────────────────────────────────────────────────────────
    month_totals = df_dated.groupby("month").size()
    MIN_N = 1
    valid_months = month_totals[month_totals >= MIN_N].index
    df_m = df_dated[df_dated["month"].isin(valid_months)].copy()

    region_totals = df.groupby("region").size()

    # ────────────────────────────────────────────────────────────────────────
    # Helper: quarterly time-series for a skill column
    # ────────────────────────────────────────────────────────────────────────
    def monthly_trend(df_source, skill_col, top_n):
        exp = df_source.explode(skill_col).dropna(subset=[skill_col])
        exp = exp[exp[skill_col] != ""]
        top = exp[skill_col].value_counts().head(top_n).index.tolist()
        exp = exp[exp[skill_col].isin(top)]
        counts = exp.groupby(["month", skill_col]).size().reset_index(name="count")
        counts["demand_pct"] = counts.apply(
            lambda r: r["count"] / month_totals[r["month"]] * 100, axis=1
        )
        counts["date_plot"] = counts["month"].dt.start_time
        return counts.rename(columns={skill_col: "skill"})

    # ────────────────────────────────────────────────────────────────────────
    # Helper: geographic frequency for a skill column
    # ────────────────────────────────────────────────────────────────────────
    def geo_freq(df_source, skill_col, top_n):
        exp = df_source.explode(skill_col).dropna(subset=[skill_col])
        exp = exp[exp[skill_col] != ""]
        top = exp[skill_col].value_counts().head(top_n).index.tolist()
        exp = exp[exp[skill_col].isin(top)]
        counts = exp.groupby([skill_col, "region"]).size().reset_index(name="count")
        counts["demand_pct"] = counts.apply(
            lambda r: r["count"] / region_totals.get(r["region"], 1) * 100, axis=1
        )
        return counts.rename(columns={skill_col: "skill"})

    # ═══════════════════════════════════════════════════════════════════════
    # Chart 1 – Combined Hard & Soft Skills Over Time (quarterly)
    # ═══════════════════════════════════════════════════════════════════════
    print("Generating Chart 1: Combined skills over time (quarterly)...")
    hard_t = monthly_trend(df_m, "hard_skills", 4)
    hard_t["type"] = "Hard"
    soft_t = monthly_trend(df_m, "soft_skills", 3)
    soft_t["type"] = "Soft"
    combined_t = pd.concat([hard_t, soft_t])

    fig, ax = plt.subplots(figsize=(14, 7))
    sns.lineplot(
        data=combined_t, x="date_plot", y="demand_pct",
        hue="skill", style="type",
        markers=True, dashes={"Hard": (1,0), "Soft": (3,2)},
        linewidth=2.5, palette="tab10", markersize=9, ax=ax
    )
    ax.set_title("Quarterly Skill Demand Trends: Hard vs. Soft Skills", fontsize=17, fontweight="bold")
    ax.set_xlabel("Quarter", fontsize=13)
    ax.set_ylabel("% of Job Postings", fontsize=13)
    if not combined_t.empty:
        ax.set_xlim(combined_t["date_plot"].min(), combined_t["date_plot"].max())
    plt.xticks(rotation=45, ha="right")
    ax.annotate(
        f"Quarters with N ≥ {MIN_N} jobs shown",
        xy=(0.02, 0.97), xycoords="axes fraction",
        fontsize=10, verticalalignment="top",
        bbox=dict(boxstyle="round,pad=0.3", fc="#f0f0f0", ec="gray")
    )
    plt.legend(title="Skill  (-- Hard  .. Soft)", bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=11)
    plt.tight_layout()
    plt.savefig(f"{OUT_DIR}/combined_skills_over_time.png", dpi=300)
    plt.close()

    # ═══════════════════════════════════════════════════════════════════════
    # Chart 2 – Combined Geographic Bar Chart (Hard + Soft)
    # ═══════════════════════════════════════════════════════════════════════
    print("Generating Chart 2: Combined skills by geography...")
    hard_g = geo_freq(df, "hard_skills", 8)
    hard_g["Type"] = "Hard"
    soft_g = geo_freq(df, "soft_skills", 5)
    soft_g["Type"] = "Soft"
    combined_g = pd.concat([hard_g, soft_g])
    combined_g["skill_label"] = combined_g["skill"] + " [" + combined_g["Type"] + "]"

    # Sort by overall demand
    order = combined_g.groupby("skill_label")["demand_pct"].mean().sort_values(ascending=False).index

    fig, ax = plt.subplots(figsize=(14, 10))
    sns.barplot(
        data=combined_g, x="demand_pct", y="skill_label",
        hue="region", palette="Set2", order=order, ax=ax
    )
    ax.set_title("Top Skill Demand by Region — Hard [H] & Soft [S]", fontsize=17, fontweight="bold")
    ax.set_xlabel("% of Job Postings", fontsize=13)
    ax.set_ylabel("")
    plt.yticks(fontsize=11)
    ax.set_yticklabels([t.get_text() for t in ax.get_yticklabels()], rotation=30, ha="right")
    plt.legend(title="Region", bbox_to_anchor=(1.02, 1), loc="upper left")
    plt.tight_layout()
    plt.savefig(f"{OUT_DIR}/combined_skills_by_geography.png", dpi=300)
    plt.close()

    # ═══════════════════════════════════════════════════════════════════════
    # Chart 3 – Individual Hard Skills by Geography (top 15)
    # ═══════════════════════════════════════════════════════════════════════
    print("Generating Chart 3: Hard skills by geography...")
    hard_g15 = geo_freq(df, "hard_skills", 15)
    order_h = hard_g15.groupby("skill")["demand_pct"].mean().sort_values(ascending=False).index

    fig, ax = plt.subplots(figsize=(14, 9))
    sns.barplot(data=hard_g15, x="demand_pct", y="skill", hue="region",
                palette="magma", order=order_h, ax=ax)
    ax.set_title("Top 15 Hard (Technical) Skills Demand by Region", fontsize=17, fontweight="bold")
    ax.set_xlabel("% of Job Postings", fontsize=13)
    ax.set_ylabel("")
    ax.set_yticklabels([t.get_text() for t in ax.get_yticklabels()], rotation=30, ha="right")
    plt.legend(title="Region", bbox_to_anchor=(1.02, 1), loc="upper left")
    plt.tight_layout()
    plt.savefig(f"{OUT_DIR}/hard_skills_by_geography.png", dpi=300)
    plt.close()

    # ═══════════════════════════════════════════════════════════════════════
    # Chart 4 – Individual Soft Skills by Geography (top 10)
    # ═══════════════════════════════════════════════════════════════════════
    print("Generating Chart 4: Soft skills by geography...")
    soft_g10 = geo_freq(df, "soft_skills", 10)
    order_s = soft_g10.groupby("skill")["demand_pct"].mean().sort_values(ascending=False).index

    fig, ax = plt.subplots(figsize=(14, 8))
    sns.barplot(data=soft_g10, x="demand_pct", y="skill", hue="region",
                palette="viridis", order=order_s, ax=ax)
    ax.set_title("Top 10 Soft (Interpersonal) Skills Demand by Region", fontsize=17, fontweight="bold")
    ax.set_xlabel("% of Job Postings", fontsize=13)
    ax.set_ylabel("")
    ax.set_yticklabels([t.get_text() for t in ax.get_yticklabels()], rotation=30, ha="right")
    plt.legend(title="Region", bbox_to_anchor=(1.02, 1), loc="upper left")
    plt.tight_layout()
    plt.savefig(f"{OUT_DIR}/soft_skills_by_geography.png", dpi=300)
    plt.close()

    # ═══════════════════════════════════════════════════════════════════════
    # Chart 5 – Hard skills over time individually (quarterly)
    # ═══════════════════════════════════════════════════════════════════════
    print("Generating Chart 5: Hard skills trend over time...")
    hard_t5 = monthly_trend(df_m, "hard_skills", 6)
    fig, ax = plt.subplots(figsize=(14, 7))
    sns.lineplot(data=hard_t5, x="date_plot", y="demand_pct", hue="skill",
                 markers=True, linewidth=2.5, palette="tab10", markersize=9, ax=ax)
    ax.set_title("Top Hard Skills — Quarterly Demand Trend", fontsize=17, fontweight="bold")
    ax.set_xlabel("Quarter", fontsize=13)
    ax.set_ylabel("% of Job Postings", fontsize=13)
    if not hard_t5.empty:
        ax.set_xlim(hard_t5["date_plot"].min(), hard_t5["date_plot"].max())
    plt.xticks(rotation=45, ha="right")
    plt.legend(title="Skill", bbox_to_anchor=(1.02, 1), loc="upper left")
    plt.tight_layout()
    plt.savefig(f"{OUT_DIR}/hard_skills_over_time.png", dpi=300)
    plt.close()

    # ═══════════════════════════════════════════════════════════════════════
    # Chart 6 – Soft skills over time individually (quarterly)
    # ═══════════════════════════════════════════════════════════════════════
    print("Generating Chart 6: Soft skills trend over time...")
    soft_t5 = monthly_trend(df_m, "soft_skills", 5)
    fig, ax = plt.subplots(figsize=(14, 7))
    sns.lineplot(data=soft_t5, x="date_plot", y="demand_pct", hue="skill",
                 markers=True, linewidth=2.5, palette="tab10", markersize=9, ax=ax)
    ax.set_title("Top Soft Skills — Quarterly Demand Trend", fontsize=17, fontweight="bold")
    ax.set_xlabel("Quarter", fontsize=13)
    ax.set_ylabel("% of Job Postings", fontsize=13)
    if not soft_t5.empty:
        ax.set_xlim(soft_t5["date_plot"].min(), soft_t5["date_plot"].max())
    plt.xticks(rotation=45, ha="right")
    plt.legend(title="Skill", bbox_to_anchor=(1.02, 1), loc="upper left")
    plt.tight_layout()
    plt.savefig(f"{OUT_DIR}/soft_skills_over_time.png", dpi=300)
    plt.close()

    # ═══════════════════════════════════════════════════════════════════════
    # Chart 7 – Emerging / Rising Skills (excluding evergreen classics)
    # ═══════════════════════════════════════════════════════════════════════
    print("Generating Chart 7: Emerging / Rising skills...")

    # Evergreen skills that have been dominant for 10-20+ years — exclude these
    EVERGREEN = {
        "Python", "Java", "Javascript", "Sql", "Html", "Css", "C++", "C#",
        "Php", "Ruby", "Git", "Linux", "Aws", "Docker", "Mysql", "Postgresql",
        "Mongodb", "React", "Angular", "Nodejs", "Node.Js", "Springboot",
        "Spring Boot", "Agile", "Scrum", "Restful Apis", "Rest Api",
        "Html5", "Css3", "Software Development", "Software Engineering",
        "Oop", "Object-Oriented", "Ci/Cd", "Devops",
    }

    exp_em = df_m.explode("hard_skills").dropna(subset=["hard_skills"])
    exp_em = exp_em[exp_em["hard_skills"].str.strip() != ""]
    exp_em["skill"] = exp_em["hard_skills"].str.strip().str.title()
    exp_em = exp_em[~exp_em["skill"].isin(EVERGREEN)]

    # Monthly demand %
    em_counts = exp_em.groupby(["month", "skill"]).size().reset_index(name="count")
    em_counts = em_counts[em_counts["month"].isin(valid_months)]
    em_counts["demand_pct"] = em_counts.apply(
        lambda r: r["count"] / month_totals[r["month"]] * 100, axis=1
    )

    # Pick top 15 by recent average (last 3 months)
    recent_months = sorted(em_counts["month"].unique())[-3:]
    recent_em = em_counts[em_counts["month"].isin(recent_months)]
    top_emerging = (
        recent_em.groupby("skill")["demand_pct"].mean()
        .sort_values(ascending=False)
        .head(15).index.tolist()
    )

    em_top = em_counts[em_counts["skill"].isin(top_emerging)]
    em_top["date_plot"] = em_top["month"].dt.start_time

    fig, ax = plt.subplots(figsize=(14, 7))
    sns.lineplot(
        data=em_top, x="date_plot", y="demand_pct",
        hue="skill", markers=True, linewidth=2.5,
        palette="tab20", markersize=9, ax=ax
    )
    ax.set_title("Emerging & Rising Skills in 2025–2026\n(Evergreen classics excluded)", fontsize=17, fontweight="bold")
    ax.set_xlabel("Month", fontsize=13)
    ax.set_ylabel("% of Job Postings", fontsize=13)
    if not em_top.empty:
        ax.set_xlim(em_top["date_plot"].min(), em_top["date_plot"].max())
    plt.xticks(rotation=45, ha="right")
    plt.legend(title="Skill", bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=10)
    plt.tight_layout()
    plt.savefig(f"{OUT_DIR}/emerging_skills_over_time.png", dpi=300)
    plt.close()

    print(f"\nAll 7 charts saved to {OUT_DIR}/")

if __name__ == "__main__":
    main()
