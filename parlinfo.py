#!./venv/bin/python

import requests, urllib

#
# Maintain a database of Hansard XML documents from APH's ParlInfo service
#

class ParlInfoQuery:
    base = 'http://parlinfo.aph.gov.au/parlInfo/feeds/rss.w3p'
    def get_uri(self, page):
        return 'http://localhost/'
        q = urllib.parse.quote
        self.args['page'] = str(page)
        return ParlInfoQuery.base + ';' + ';'.join(("{}={}".format(q(k), q(v)) for (k, v) in self.args.items()))

    def __init__(self, **kwargs):
        self.args = kwargs

    def __iter__(self):
        def __iter_fn():
            page = 0
            while True:
                yield self.get_uri(page)
                page += 1
        return __iter_fn()

if __name__ == '__main__':
    s = requests.Session()
    q = ParlInfoQuery(orderBy="date-eFirst", query="(Dataset:hansardr)", resCount="500")
    for uri in q:
        r = s.get(uri, stream=False)
        content = r.content
        print(len(content))


