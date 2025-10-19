import requests
import json

access_token = "My access token"
url = 'https://webexapis.com/v1/rooms'

headers = {
    'Authorization': 'Bearer {}'.format(access_token),
    'Content-Type': 'application/json'
}

params = {
    'max': 100
}

res = requests.get(url, headers=headers, params=params)
print(json.dumps(res.json(), indent=4))