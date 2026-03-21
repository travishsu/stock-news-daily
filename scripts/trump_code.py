import json
import os
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

url = os.environ.get(
    "TRUMP_CODE_REPORT_URL",
    "https://raw.githubusercontent.com/sstklen/trump-code/main/data/daily_report.json",
)
report = json.loads(urllib.request.urlopen(url).read())
print(report['summary']['zh'])  # Chinese
# print(report['summary']['ja'])  # Japanese
# print(report['summary']['en'])  # English
