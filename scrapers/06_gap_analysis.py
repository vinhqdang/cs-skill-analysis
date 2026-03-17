import pandas as pd
import os

def main():
    print("Loading data...")
    # 1. Load Employer Demand
    demand_path = "data/processed/skills_extracted_llm_freq.csv"
    if not os.path.exists(demand_path):
        print(f"Error: {demand_path} not found.")
        return
    
    demand_df = pd.read_csv(demand_path)
    
    # 2. Load Curriculum Supply
    supply_path = "data/processed/curriculum_skills.csv"
    if not os.path.exists(supply_path):
        print(f"Error: {supply_path} not found.")
        return
        
    supply_df = pd.read_csv(supply_path)
    
    print(f"Loaded {len(demand_df)} demand records and {len(supply_df)} supply records.")
    
    # Analyze Curriculum Supply frequency
    # Calculate % of universities teaching each skill
    total_unis = supply_df["university"].nunique()
    if total_unis == 0:
        print("No universities found in curriculum data.")
        return
        
    supply_freq = supply_df.groupby("skill")["university"].nunique().reset_index()
    supply_freq.columns = ["skill", "uni_count"]
    # Normalize to 0-100 scale
    supply_freq["supply_pct"] = (supply_freq["uni_count"] / total_unis) * 100
    
    # Rename demand column for merging
    demand_df = demand_df.rename(columns={"skills_extracted_llm": "skill"})
    
    # Merge datasets
    # Using outer join to see what's in demand but not taught (positive gap)
    # and what's taught but not in demand (negative gap)
    gap_df = pd.merge(demand_df, supply_freq, on="skill", how="outer")
    
    # Fill NAs with 0
    gap_df["demand_pct"] = gap_df["demand_pct"].fillna(0)
    gap_df["supply_pct"] = gap_df["supply_pct"].fillna(0)
    gap_df["job_count"] = gap_df["job_count"].fillna(0)
    gap_df["uni_count"] = gap_df["uni_count"].fillna(0)
    
    # Calculate Normalization relative to the MAX observed value to put them on the same 0-10 scale
    # This prevents the raw % from skewing the results if the max demand % is only like 10%
    max_demand = gap_df["demand_pct"].max() or 1
    max_supply = gap_df["supply_pct"].max() or 1
    
    gap_df["normalized_demand"] = (gap_df["demand_pct"] / max_demand) * 10
    gap_df["normalized_supply"] = (gap_df["supply_pct"] / max_supply) * 10
    
    # Calculate Final Gap Score
    # Positive score (0 to +10) = High Demand, Low Supply (Market Gap, needs adding to curriculum)
    # Negative score (-10 to 0) = Low Demand, High Supply (Academic focus, low direct job requirement)
    gap_df["gap_score"] = gap_df["normalized_demand"] - gap_df["normalized_supply"]
    
    # Sort by gap score descending (biggest missing skills at the top)
    gap_df = gap_df.sort_values(by="gap_score", ascending=False)
    
    os.makedirs("data/output", exist_ok=True)
    out_file = "data/output/skill_gap_matrix.csv"
    gap_df.to_csv(out_file, index=False)
    
    print("\n--- Top 10 High Demand / Low Supply (Missing from Curriculum) ---")
    print(gap_df.head(10)[["skill", "normalized_demand", "normalized_supply", "gap_score"]])
    
    print("\n--- Top 10 Low Demand / High Supply (Academic Focus) ---")
    print(gap_df.tail(10)[["skill", "normalized_demand", "normalized_supply", "gap_score"]])
    
    print(f"\nGap matrix successfully saved to {out_file}")

if __name__ == "__main__":
    main()
