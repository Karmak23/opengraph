# encoding: utf-8
u""" Extract OpenGraph entities from an HTML document. """

import re
import urllib2
import logging

try:
    from bs4 import BeautifulSoup

except ImportError:
    from BeautifulSoup import BeautifulSoup

try:
    import json

except ImportError:
    json = None

LOGGER = logging.getLogger(__name__)


class OpenGraph(dict):

    """ Turn OpenGraph metadata into a python dict-like. """

    required_attrs = ['title', 'type', 'image', 'url', ]
    optional_attrs = [
        'audio', 'determiner', 'description', 'locale',
        'locale:alternate', 'site_name', 'video',
    ]
    types_attrs = {
        # TODO: please implement video.*, music.*
        'article': [
            'published_time', 'modified_time', 'expiration_time',
            'author', 'section', 'tag'
        ],
        'book': ['author', 'isbn', 'release_date', 'tag', ],
        'profile': ['first_name', 'last_name', 'username', 'gender', ],
        'website': [],
    }

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

        elif html is not None:
            self.parse(html)

        else:
            raise RuntimeError(
                u'Either url or html must be passed as argument.')

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

    def __store_og_entity(self, og_entity, strip_prefix=True):
        """ Store an OG data if it is correct.

        This [internal] method takes care of arrays to some extends. It
        won't handle correctly complex cases like the 3-images examples
        at http://ogp.me/#array
        """

        if og_entity.has_attr(u'content'):
            if strip_prefix:
                # strip leading 'og:'
                property_name = og_entity[u'property'][3:]

            else:
                # make "article:publish_time" become "article__publish_time"
                # which is less cool, a little pythonic and very Djangoesque.
                property_name = og_entity[u'property'].replace(u':', '__')

            if property_name in self:
                # The spec defines arrays now and them. Mutate our
                # values to lists() in case we encounter another OG
                # property with an already known name.

                if type(self[property_name]) != type(list):
                    self[property_name] = [self[property_name]]

                self[property_name].append(unicode(og_entity[u'content']))

            else:
                self[property_name] = unicode(og_entity[u'content'])

    def __search_for_entities(self, entity_prefix, doc):

        # LOGGER.info(u'search "%s:"', entity_prefix)

        og_entities = doc.html.head.findAll(
            property=re.compile(r'^{0}:'.format(entity_prefix)))

        strip_prefix = entity_prefix == u'og'

        for og_entity in og_entities:
            # LOGGER.info(u'found %s', og_entity)

            self.__store_og_entity(og_entity, strip_prefix=strip_prefix)

        # LOGGER.info(u'stored now: %s', u', '.join(
        #             u'{0}: {1}'.format(k, v) for k, v in self.iteritems()))

    def parse(self, html):
        """ Parse the HTML, looking for all OG tags and store them. """

        if isinstance(html, BeautifulSoup):
            doc = html

        else:
            doc = BeautifulSoup(html)

        self.__search_for_entities('og', doc)

        self.__parse_type_specifics(doc)

        self.scrape_if_needed(doc)

    def __parse_type_specifics(self, doc):
        """ Look for the sub-entities of each known OG type. """

        # LOGGER.info(u'keys: %s', self.keys())

        try:
            # This one will give us more tags to look for.
            og_type = self['type']

        except KeyError:
            # No type declared / found. The document is invalid.
            return

        if og_type not in self.types_attrs:
            # currently unknown type.
            return

        self.__search_for_entities(og_type, doc)

    def scrape_if_needed(self, doc):

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
