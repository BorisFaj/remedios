import requests

url = "https://graph.facebook.com/v21.0/515982168263190/messages"

headers = {
    "Authorization": "Bearer EAASnIMnOSi4BOZCPOXqbkj86YpVEZAWZCPS8MRckYXnze9xxkyheb7ngQnZAhx44LvbSo6n3PcIHN3pHoUobUwQY6h6hz6RD4d9I3X5OaAKtmBVZBazxrSECZAmgek78J1Eqcyz0EXsM4CVs5XCYhfJjoxWfNZB9qukZAcFmMuALFUkTa005C85e6ttfnLFMGDLaVgAJa66lWfk8OVIWssD9QBLe",
    "Content-Type": "application/json",
}

payload = {
    "messaging_product": "whatsapp",
    "to": "34671276538",
    "type": "template",
    "template": {
        "name": "hello_world",
        "language": {
            "code": "en_US"
        }
    }
}

response = requests.post(url, headers=headers, json=payload)

print(f"Status Code: {response.status_code}")
print(f"Response: {response.text}")
