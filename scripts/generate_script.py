import argparse
import json
import os
import re
import requests


def clean_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", required=True)
    args = parser.parse_args()

    fallback_title = "Aaj Ki Viral Baat! #Shorts"
    fallback_script = (
        "Aajkal AI literally har jagah nazar aa rahi hai. Study se lekar business aur daily work tak "
        "har cheez ke liye naye tools aa rahe hain. Bas thoda curious raho aur jo naya tool dikhe usko "
        "try karo. Ho sakta hai wahi kal tumhara favourite tool ban jaye."
    )

    key = os.getenv("GEMINI_API_KEY", "").strip()
    title, script = fallback_title, fallback_script

    if key:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')}:generateContent?key={key}"
        )
        body = {"contents": [{"parts": [{"text":
            'Generate one 90-120 word Roman Urdu/Hinglish AI YouTube Short. '
            'Return ONLY JSON: {"title":"title","script":"script"}'
        }]}]}
        try:
            r = requests.post(url, json=body, timeout=60)
            if r.status_code == 200:
                data = r.json()
                parsed = json.loads(clean_json(data["candidates"][0]["content"]["parts"][0]["text"]))
                title = str(parsed.get("title") or title)
                script = str(parsed.get("script") or script)
            elif r.status_code == 429:
                print("Gemini quota/rate limit reached; using fallback.")
            else:
                print(f"Gemini HTTP {r.status_code}; using fallback.")
        except Exception as exc:
            print(f"Gemini error: {exc}; using fallback.")

    os.makedirs("output", exist_ok=True)
    with open("output/script.txt", "w", encoding="utf-8") as f:
        f.write(script)
    with open("output/title.txt", "w", encoding="utf-8") as f:
        f.write(title)

    print("Script generated successfully!")


if __name__ == "__main__":
    main()
