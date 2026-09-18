import argparse
import os
import requests
import json

def main():
    parser = argparse.ArgumentParser(description="Generate AI Content Script")
    parser.add_argument("--type", type=str, required=True, help="Content category")
    args = parser.parse_args()

    print(f"Generating script for category: {args.type}")
    os.makedirs("output", exist_ok=True)
    
    gemini_api_key = os.getenv("GEMINI_API_KEY", "")
    fallback_script = "Dosto, aajkal AI ki duniya mein naye trends aa rahe hain, inhein miss mat karo!"
    
    if not gemini_api_key:
        script_text = fallback_title = fallback_script
    else:
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_api_key}"
        instruction = "Generate a short viral Hinglish script for a YouTube Short about AI trends, around 90-120 words. Reply ONLY with JSON: {\"title\": \"title\", \"script\": \"script text\"}"
        body = {"contents": [{"parts": [{"text": instruction}]}]}
        try:
            resp = requests.post(api_url, json=body, timeout=60)
            if resp.status_code == 200:
                data = resp.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                if text.startswith("```"): text = text.strip("`").replace("json", "").strip()
                parsed = json.loads(text)
                fallback_title = parsed.get("title", "Viral AI Short")
                script_text = parsed.get("script", fallback_script)
            else:
                script_text = fallback_script
                fallback_title = "Viral AI Short"
        except Exception as e:
            print(f"Error: {e}")
            script_text = fallback_script
            fallback_title = "Viral AI Short"

    with open("output/script.txt", "w", encoding="utf-8") as f:
        f.write(script_text)
    with open("output/title.txt", "w", encoding="utf-8") as f:
        f.write(fallback_title)
    print("Script generated successfully!")

if __name__ == "__main__":
    main()
