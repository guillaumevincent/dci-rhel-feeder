import json

import requests
import fedmsg
import fedmsg.meta

config = fedmsg.config.load_config()
fedmsg.meta.make_processors(**config)
url = "https://apps.fedoraproject.org/datagrepper/raw/"
two_months = 24 * 3600 * 9
response = requests.get(
    url,
    params=dict(
        topic='org.fedoraproject.prod.releng.atomic.twoweek.complete',
        delta=two_months
    )
)
data = response.json()
print(json.dumps(data, indent=4, sort_keys=True))
for message in data['raw_messages']:
    print(fedmsg.meta.msg2title(message))
    print(fedmsg.meta.msg2link(message))

