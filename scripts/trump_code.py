import json
import os
import requests
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

#url = os.environ.get(
#    "TRUMP_CODE_REPORT_URL",
#    "https://trumpcode.washinmura.jp/api/recent-posts",
#)
#report = json.loads(urllib.request.urlopen(url).read())
#report = json.loads(urllib.request.urlopen('https://trumpcode.washinmura.jp/api/recent-posts').read())
response = json.loads(requests.get('https://trumpcode.washinmura.jp/api/recent-posts').text)
print(response)
#print(report['summary']['zh'])  # Chinese
# print(report['summary']['ja'])  # Japanese
# print(report['summary']['en'])  # English
