import json
import requests


def ask(m: str):

    url = "http://localhost:4891/v1/chat/completions"
    data = {
        "model": "Phi-3 Mini Instruct",
        "messages": [{"role": "user", "content": m}],
        "max_tokens": 4096,  # lo mismo que el ChatGPT
        "temperature": 0.28
    }

    response = requests.post(url, json=data)

    if response.status_code == 200:
        return extract_content(response.text)


def extract_content(s: str) -> str:
    _r = json.loads(s)
    return _r["choices"][0]["message"]["content"]
