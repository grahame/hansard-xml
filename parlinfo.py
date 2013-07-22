#!./venv/bin/python3.3

import requests, urllib, os, time, re
import lxml, lxml.etree, json, sys
from lxml import etree
from io import BytesIO
from hashlib import sha1

retries = 5
def wrapped_get(s, *args, **kwargs):
    exc = None
    for i in range(retries):
        try:
            return s.get(*args, **kwargs)
        except requests.exceptions.ConnectionError as e:
            sys.stdout.write('!')
            sys.stdout.flush()
            exc = e
        time.sleep(1)
    raise exc

def load_state(f):
    try:
        with open(f, 'r') as fd:
            return json.load(fd)
    except IOError:
        return {}
    except ValueError:
        return {}

def save_state(f, v):
    tmp = f + '.tmp'
    with open(tmp, 'w') as fd:
        json.dump(v, fd)
    os.rename(tmp, f)

#
# Run a query. We'll get one or more links to each result page. We then 
# retrieve the result page to get a link to a Hansard XML document.
#
class ParlInfoQuery:
    base = 'http://parlinfo.aph.gov.au/parlInfo/feeds/rss.w3p'
    def get_uri(self, page):
        q = urllib.parse.quote
        self.args['page'] = str(page)
        return ParlInfoQuery.base + ';' + \
                ';'.join(("{}={}".format(q(k), q(v)) for (k, v) in self.args.items()))

    def __init__(self, name, **kwargs):
        self.args = kwargs
        self.state_file = 'state/query_{}.json'.format(urllib.parse.quote(name))
        self.result_pages = load_state(self.state_file)
        self.dirty = False

    def save(self):
        if self.dirty:
            save_state(self.state_file, self.result_pages)
            self.dirty = False

    def set_result_page(self, result_page, title):
        self.result_pages[result_page] = title
        self.dirty = True

    def update(self, complete=False, startat=0):
        def parse_rss(data):
            parser = etree.HTMLParser()
            # some of the files have strange entities in them that aren't defined in XML
            try:
                et = etree.parse(BytesIO(data), parser)
            except lxml.etree.XMLSyntaxError:
                print("something went wrong parsing query result. giving up", file=sys.stderr)
                return
            for elem in et.xpath('//item'):
                title = elem.xpath('title')[0].text
                if title:
                    title = title.strip()
                result_page = elem.xpath('guid')[0].text
                if result_page:
                    result_page = result_page.strip()
                yield title, result_page

        try:
            s = requests.Session()
            page = startat
            while True:
                uri = self.get_uri(page)
                sys.stdout.write("[page{}] getting: {} ".format(page, uri))
                sys.stdout.flush()
                r = wrapped_get(s, uri, stream=False)
                added = 0
                nresults = 0
                for title, result_page in parse_rss(r.content):
                    nresults += 1
                    if not result_page in self.result_pages:
                        added += 1
                        self.set_result_page(result_page, title)
                sys.stdout.write("... {} new\n".format(added))
                if not complete and added == 0:
                    sys.stdout.write("no new results found on this page - ending search.\n")
                    sys.stdout.flush()
                    return
                if nresults == 0:
                    sys.stdout.write("zero results found on this page - ending search.\n")
                    sys.stdout.flush()
                    return
                page += 1
        finally:
            self.save()

    def get_check_uris(self):
        get_uri = re.compile(r'^.*query=Id:\"([^\"]+)\"')
        docname_uri = {}
        for uri in sorted(self.result_pages):
            unescp_uri = urllib.parse.unquote(uri)
            m = get_uri.match(unescp_uri)
            if not m:
                raise Exception("eep: ", uri)
            obj_id = m.groups()[0]
            docname = obj_id.rsplit('/', 1)[0]
            if docname not in docname_uri:
                docname_uri[docname] = uri
        return docname_uri.values()

def check_uri_for_xml(s, uri):
    def get_xml_uri(data):
        p = etree.parse(BytesIO(data), parser=etree.HTMLParser())
        for href in (t.get('href') for t in p.xpath('//a')):
            if href is not None and href.find('fileType=text%2Fxml') != -1:
                if href.startswith('/'):
                    return 'http://parlinfo.aph.gov.au' + href
                return href
    r = wrapped_get(s, uri, stream=False)
    return get_xml_uri(r.content)

class XmlUriFind:
    def __init__(self, check_uris):
        self.check_uris = check_uris
        self.state_file = 'state/parlinfo_xml.json'
        self.xml_for_uri = load_state(self.state_file)

    def save(self):
        save_state(self.state_file, self.xml_for_uri)

    def update(self, retry=False):
        try:
            to_check = [ t for t in self.check_uris if (t not in self.xml_for_uri) or (retry and self.xml_for_uri.get(t) == None) ]
            s = requests.Session()
            total = len(to_check)
            for i, uri in enumerate(sorted(to_check)):
                sys.stdout.write("[{}/{}] getting: {} ".format(i+1, total, uri))
                sys.stdout.flush()
                x = check_uri_for_xml(s, uri)
                self.xml_for_uri[uri] = x
                if x is not None:
                    sys.stdout.write("... found.\n")
                else:
                    sys.stdout.write("... no XML.\n")
        finally:
            self.save()

    def get_xml_uris(self):
        return list(filter(None, self.xml_for_uri.values()))

class XmlFetcher:
    def __init__(self, xml_uris):
        self.xml_uris = xml_uris
    
    def update(self):
        def get_fname(uri):
            p = urllib.parse.urlparse(uri)
            uri_namepart = urllib.parse.unquote(p.path).split('/')[-1]
            uniq = sha1(uri.encode('utf8')).hexdigest()[:8]
            return 'xml/{}_{}'.format(uniq, uri_namepart)

        with_fname = [ (t, get_fname(t)) for t in self.xml_uris ]
        to_get = [ t for t in with_fname if not os.access(t[1], os.R_OK) ]

        s = requests.Session()
        nget = len(to_get)
        for i, (uri, fname) in enumerate(sorted(to_get)):
            sys.stdout.write("[{}/{}] getting: {} ".format(i+1, nget, uri))
            sys.stdout.flush()
            r = wrapped_get(s, uri, stream=False)
            tmpf = fname + '.tmp'
            with open(tmpf, 'wb') as fd:
                fd.write(r.content)
            os.rename(tmpf, fname)
            sys.stdout.write("... OK\n")
            sys.stdout.flush()

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('queries', nargs='+')
    parser.add_argument('--all', '-a', action='store_true')
    parser.add_argument('--startat', '-s', default=0, type=int)
    parser.add_argument('--retryxml', '-r', action='store_true')
    args = parser.parse_args()
    queries = {
        'hansardr' : "(Dataset:hansardr)",
        'hansards' : "(Dataset:hansards)"
    }
    check_uris = set()
    for qname in args.queries:
        q = ParlInfoQuery(qname, orderBy="date-eFirst", query=queries[qname], resCount="Default")
        q.update(complete=args.all, startat=args.startat)
        check_uris = check_uris.union(set(q.get_check_uris()))
    scanner = XmlUriFind(list(check_uris))
    scanner.update(retry=args.retryxml)
    fetcher = XmlFetcher(scanner.get_xml_uris())
    fetcher.update()

