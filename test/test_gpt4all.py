import requests

url = "http://localhost:4891/v1/chat/completions"
data = {
    "model": "Phi-3 Mini Instruct",
    "messages": [{"role": "user", "content": "Who is Lionel Messi?"}],
    "max_tokens": 50,
    "temperature": 0.28
}

response = requests.post(url, json=data)

print(response.status_code)
print(response.text)