# encoding: utf-8
u""" Extract OpenGraph entities from an HTML document. """

import re
import urllib2
try:
    from bs4 import BeautifulSoup
except ImportError:
    from BeautifulSoup import BeautifulSoup

try:
    import json

except ImportError:
    json = None


class OpenGraph(dict):

    """ Turn OpenGraph metadata into a python dict-like. """

    required_attrs = ['title', 'type', 'image', 'url', ]
    optional_attrs = [
        'audio', 'determiner', 'description', 'locale',
        'locale:alternate', 'site_name', 'video',
    ]

    def __init__(self, url=None, html=None, scrape=False, **kwargs):
        """ Init OpenGraph instance.

        :param url: full URL of a web page to analyze. Can be ``None`` if
            :param:`html` is given.
        :param url: full content of an already fetched web page to analyze.
            Can be ``None`` if :param:`url` is given.
        :param scrape: if ``True``, we will try to fetch missing attributes
            from the page's body.
        """

        self.scrape = scrape
        self._url = url

        for k in kwargs.keys():
            self[k] = kwargs[k]

        dict.__init__(self)

        if url is not None:
            self.fetch(url)

        if html is not None:
            self.parse(html)

    def __setattr__(self, name, val):
        """ Make our dict compatible with a standard object (AMAP). """

        self[name] = val

    def __getattr__(self, name):
        """ Make our dict compatible with a standard object (AMAP). """

        return self[name]

    def fetch(self, url):
        """ Download URL from the internet and return it already parsed. """

        raw = urllib2.urlopen(url)
        html = raw.read()

        return self.parse(html)

    def parse(self, html):
        """
        """
        if not isinstance(html, BeautifulSoup):
            doc = BeautifulSoup(html)
        else:
            doc = html
        ogs = doc.html.head.findAll(property=re.compile(r'^og:'))
        for og in ogs:
            if og.has_attr(u'content'):
                property_name = og[u'property'][3:]

                if property_name in self:
                    # The spec defines arrays now and them. Mutate our
                    # values to lists() in case we encounter another OG
                    # property with an already known name.

                    if type(self[property_name]) != type(list):
                        self[property_name] = [self[property_name]]

                    self[property_name].append(og[u'content'])

                else:
                    self[property_name] = og[u'content']

        # Couldn't fetch all attrs from og tags, try scraping body
        if not self.is_valid() and self.scrape:
            for attr in self.required_attrs:
                if not self.valid_attr(attr):
                    try:
                        self[attr] = getattr(self, 'scrape_%s' % attr)(doc)
                    except AttributeError:
                        pass

    def valid_attr(self, attr):

        return hasattr(self, attr) and len(self[attr]) > 0

    def is_valid(self):

        return all([self.valid_attr(attr) for attr in self.required_attrs])

    def to_html(self):

        if not self.is_valid():
            return u'<meta property="og:error" content="invalid OG metadata" />'

        meta = u'\n'.join(
            u'<meta property="og:{0}" content="%s" />'.format(key, value)
            for key, value in self.iteritems()
        ) + u'\n'

        return meta

    def to_json(self):
        # TODO: force unicode
        if json is None:
            return "{'error': 'there isn't json module'}"

        if not self.is_valid():
            return json.dumps({'error': u'invalid OG metadata'})

        return json.dumps(self)

    def to_xml(self):

        pass

    def scrape_image(self, doc):
        images = [
            dict(img.attrs)['src']
            for img in doc.html.body.findAll('img')
        ]

        if images:
            return images[0]

        return u''

    def scrape_title(self, doc):

        return doc.html.head.title.text

    def scrape_type(self, doc):

        return u'other'

    def scrape_url(self, doc):

        return self._url

    def scrape_description(self, doc):

        tag = doc.html.head.findAll('meta', attrs={'name': 'description'})
        result = u''.join([t['content'] for t in tag])

        return result
