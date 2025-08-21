#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import os
import json
import argparse
import pandas as pd
import openai

def load_api_key():
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise EnvironmentError("Missing OPENAI_API_KEY in environment")
    return key

def generate_response(prompt, model="gpt-4o"):
    try:
        response = openai.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.choices[0].message.content.strip("```json").strip("```")
        return json.loads(text)
    except json.JSONDecodeError as e:
        print(f"JSONDecodeError: {e}")
        return {}
    except Exception as e:
        print(f"Error: {e}")
        return {}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Path to input Excel file")
    parser.add_argument("--output", default="results.xlsx", help="Path to save output Excel file")
    args = parser.parse_args()

    openai.api_key = load_api_key()
    df = pd.read_excel(args.input)

    answers = []
    codes = []

    for _, row in df.iterrows():
        prompt = row["Prompt"]
        result = generate_response(prompt)
        answers.append(result.get("Answer", ""))
        codes.append(result.get("Visualization Code", ""))

    df["Generated Answer"] = answers
    df["Generated Code"] = [code.encode().decode('unicode_escape') for code in codes]

    df.to_excel(args.output, index=False)

if __name__ == "__main__":
    main()

