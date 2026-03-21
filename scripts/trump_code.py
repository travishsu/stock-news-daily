import json, urllib.request
url = "https://raw.githubusercontent.com/sstklen/trump-code/main/data/daily_report.json"
report = json.loads(urllib.request.urlopen(url).read())
print(report['summary']['zh'])  # Chinese
#print(report['summary']['ja'])  # Japanese
#print(report['summary']['en'])  # English

