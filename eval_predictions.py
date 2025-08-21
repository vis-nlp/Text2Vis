#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import os
import json
import base64
import argparse
import openai
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

def encode_image(image_path):
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode("utf-8")

def safe_int_conversion(response_text):
    try:
        return int(response_text.strip())
    except:
        return 0

def evaluate_row(row, image_folder):
    answer_prompt = f"""
You are an expert evaluator. Based on the following rules, determine if the predicted answer matches the ground truth:

Ground Truth Answer: "{row['Answer']}"
Generated Answer: "{row['Generated Answer']}"

Evaluation Criteria:
1. Match if numbers are close (e.g., "48.77" vs "48.73") or equivalent percentages (e.g., "100%" vs "100").
2. Match if ground truth appears within the generated response (e.g., "100" in "The result is 100").
3. Match if core meaning remains the same, even with different phrasing for long answers.
4. Allow minor spelling differences or abbreviations (e.g., "Albenia" vs "Albania", "USA" vs "United States").
5. Do NOT match if meaning changes significantly (e.g., "Fragile" vs "Extreme fragility").

Return only 1 if matched, else return 0. No explanation.
"""
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": answer_prompt}]
    )
    answer_match = safe_int_conversion(response.choices[0].message.content)

    image_path = os.path.join(image_folder, f"{row['ID']}.png")
    if os.path.exists(image_path):
        encoded_img = encode_image(image_path)

        vis_prompt = f"""
You are a visualization expert. Given the following, score the chart using the criteria below:

Query: "{row['Question']}"
Data Table: {row['Table Data']}

Scoring:

1. Readability and Quality Score (0–5)
    - Labels and Titles: Clear and positioned correctly?
    - Layout Spacing: Organized, uncluttered?
    - Color Accessibility: Are colors distinct and friendly?
    - Axis Scaling: Labeled and proportional?
    - Chart Type Suitability: Matches data type?
    - Font and Legends: Readable and aligned?
    - Annotations: Clear and non-overlapping?

2. Chart Correctness Score (0–5)
    - Query Alignment: Chart answers the query?
    - Data Integrity: Values accurately shown?
    - Insight Representation: Insights clearly conveyed?
    - Missing Data Handling: Any misleading gaps?
    - Complexity Handling: Logical for multi-step queries?

Scoring Guide:
5.0 – Excellent: Clear, accurate, no issues.
4.5 – Very Good: Minor issues, still clear.
4.0 – Good: Small flaws, mostly fine.
3.5 – Decent: Some clarity or accuracy issues.
3.0 – Average: Noticeable issues affect clarity.
2.5 – Below Avg: Issues may mislead.
2.0 – Poor: Major clarity issues.
1.5 – Very Poor: Nearly unreadable or wrong.
1.0 – Unusable: Very unclear or misleading.
0.0 – Failed: Completely irrelevant or broken.

Return in strict JSON format only:
{{"Readability and Quality Score": "...", "Chart Correctness Score": "..."}}"""

        vis_response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "user", "content": vis_prompt},
                {
                    "role": "user",
                    "content": [{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded_img}"}}]
                }
            ]
        )

        try:
            response_text = vis_response.choices[0].message.content.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:-3].strip()
            parsed = json.loads(response_text)

            readability_score = float(parsed.get("Readability and Quality Score", 0))
            correctness_score = float(parsed.get("Chart Correctness Score", 0))

        except Exception as e:
            print(f"JSON parse error for ID {row['ID']}: {e}")
            readability_score = 0
            correctness_score = 0
    else:
        readability_score = 0
        correctness_score = 0

    return pd.Series([answer_match, readability_score, correctness_score])

def generate_charts(df, output_folder):
    error_ids = []
    os.makedirs(output_folder, exist_ok=True)

    for index, row in df.iterrows():
        code = row['Generated Code']
        id_val = row['ID']
        plt.close('all')

        def custom_show():
            try:
                fig_nums = plt.get_fignums()
                if fig_nums:
                    fig = plt.figure(fig_nums[0])
                    filename = os.path.join(output_folder, f"{id_val}.png")
                    fig.savefig(filename)
                    plt.close(fig)
            except Exception as e:
                print(f"Error saving figure for ID {id_val}: {e}")
                raise

        exec_env = {"plt": plt, "np": np}
        exec_env["plt"].show = custom_show

        try:
            exec(code, exec_env)
        except Exception as e:
            print(f"Execution error for ID {id_val}: {e}")
            error_ids.append(id_val)
            continue

        if plt.get_fignums():
            try:
                custom_show()
            except Exception as e:
                print(f"Saving error for ID {id_val}: {e}")
                error_ids.append(id_val)
                plt.close('all')
                continue

    return error_ids

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Path to input Excel file (.xlsx)")
    parser.add_argument("--output", required=True, help="Path to output Excel file (.xlsx)")
    parser.add_argument("--chart_dir", required=True, help="Directory to save chart images")
    args = parser.parse_args()

    openai.api_key = os.getenv("OPENAI_API_KEY")
    if not openai.api_key:
        raise EnvironmentError("OPENAI_API_KEY not set")

    df = pd.read_excel(args.input)
    error_ids = generate_charts(df, args.chart_dir)
    df["execution_result"] = df.index.to_series().apply(lambda idx: 0 if idx in error_ids else 1)

    df[['Answer Match', 'Readability and Quality Score', 'Chart Correctness Score']] = df.apply(
        lambda row: evaluate_row(row, args.chart_dir), axis=1
    )

    df["Final Score"] = np.where(
        (df["Answer Match"] == 1) &
        (df["execution_result"] == 1) &
        (df["Readability and Quality Score"] >= 3.5) &
        (df["Chart Correctness Score"] >= 3.5),
        1,
        0
    )

    df.to_excel(args.output, index=False)
    print(f"Evaluation complete. Saved to {args.output}")

if __name__ == "__main__":
    main()

