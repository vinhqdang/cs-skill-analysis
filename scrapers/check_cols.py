import pandas as pd

df = pd.read_json("data/processed/jobs_with_llm_skills.json")
print(df.columns.tolist())
print(df.head(2)[["location", "date_posted"] if "date_posted" in df.columns else ["location"]])
if "date_posted" in df.columns:
    print(df["date_posted"].head(5))
