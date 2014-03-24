#!/usr/bin/env python3

import json, sys
from lxml import etree

if __name__ == '__main__':
    def gt(q):
        return q + '=' + ', '.join(t.text or '---' for t in e.xpath('/hansard/session.header/' + q))
    for fname in sys.argv[1:]:
        with open(fname, 'rb') as fd:
            try:
                e = etree.parse(fd)
            except:
                print("Exception parsing {}".format(fname), file=sys.stderr)
                raise
            print(gt('date'), gt('parliament.no'), gt('session.no'), gt('chamber'), gt('page.no'), gt('proof'))

