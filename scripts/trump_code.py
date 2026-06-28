import json
import requests

URL = "https://raw.githubusercontent.com/sstklen/trump-code/refs/heads/main/data/daily_report.json"

response = json.loads(requests.get(URL).text)
print(response)
