import unidecode
import json
import requests
import time

from flask import current_app, request
from referencesrv.client import client

from referencesrv.resolver.common import Solr
from referencesrv.resolver.solrtestdata import get_test_data

class Querier(object):
    def __init__(self):
        """

        """
        self.endpoint = current_app.config['REFERENCE_SERVICE_SOLRQUERY_URL']
        self.query_fields = current_app.config['REFERENCE_SERVICE_QUERY_FIELDS_SOLR']
        self.max_rows = current_app.config['REFERENCE_SERVICE_MAX_RECORDS_SOLR']
        self.connect_solr = current_app.config['REFERENCE_SERVICE_LIVE']
        # some options return with the Bearer keyword and some do not
        # so grab the one that is available, remove the Bearer if present, to add it at the end
        Authorization = current_app.config.get('SERVICE_TOKEN', None) or \
                        request.headers.get('X-Forwarded-Authorization', request.headers.get('Authorization', ''))
        self.Authorization = Authorization if 'Bearer' in Authorization else 'Bearer %s'%Authorization

    def make_params(self, query):
        """
        returns a dictionary of params suitable for the ADS API.

        :param query:
        :return:
        """
        return {
            'fl': self.query_fields,
            'rows': str(self.max_rows),
            'q': query,
        }


    def query(self, query):
        """
        executes query, and returns the result.

        If query yields exactly max_rows fields, we have an overflow.

        :param query:
        :return:
        """
        current_app.logger.debug('Query is %s' % (query))
        solutions = []

        if self.connect_solr:
            start_time = time.time()
            response = client().get(
                url=self.endpoint,
                headers={'Authorization': self.Authorization},
                params=self.make_params(query),
                timeout=10
            )
            current_app.logger.debug("Query executed in %s ms" % ((time.time() - start_time)*1000))

            # all non-200 responses
            if response.status_code != 200:
                current_app.logger.error('Solr returned {response}.'.format(response=response))
                raise Solr("status_code %s"%response.status_code)
            else:
                from_solr = json.loads(response.text)
        else:
            from_solr = get_test_data()

        num_docs = from_solr['response'].get('numFound', 0)
        current_app.logger.debug('YIELD num_docs=%s' %(num_docs))

        if num_docs >= self.max_rows:
            current_app.logger.error('solr overflow exception: query {query} returned more than {num_rows} rows'.format(query=query, num_rows=self.max_rows))
            return None

        for docs in from_solr["response"]["docs"]:
            solutions.append(self.massage_solution(docs))
        current_app.logger.debug('len(solutions)=%s' %(len(solutions)))

        return solutions

    def normalize_single_author(self, author_string):
        """
        returns a normalized form for a single author string.

        As this is for processing author strings coming from ADS,
        we do not touch initials or similar.  This is just so ADS
        authors are at the same normalization level as what happens
        in normalize_author_list.

        :param author_string:
        :return:
        """
        return unidecode.unidecode(author_string).replace('-', ' ').lower()

    def massage_solution(self, raw_sol):
        """
        postprocesses a result coming in from solr.

        This stuff should ideally be done server-side.  When that's not
        possible or desired, keep it here.

        raw_sol is processed in-place, but that's an implementation detail.
        Just append what this function returns and don't use the reference
        to the argument any more.

        :param raw_sol:
        :return:
        """
        if 'author_norm' in raw_sol:
            raw_sol['author_norm'] = [self.normalize_single_author(author) for author in raw_sol['author_norm']]
            raw_sol['first_author_norm'] = self.normalize_single_author(raw_sol['first_author_norm'])
        else:
            # some records don't have author_norm; put in some emergency
            # stuff and fix as we understand the problem better (we need
            # author_norm for verification)
            raw_sol['author_norm'] = [unidecode.unidecode(s) for s in raw_sol.get('author', [])]
            # unidecode posts warning if passed an empty string
            first_author = raw_sol.get('author', [''])[0].lower()
            if first_author:
                raw_sol['first_author_norm'] = unidecode.unidecode(first_author)

        # two fields of page, and title are lists, turn them into strings
        if 'page' in raw_sol:
            raw_sol['page'] = ''.join(raw_sol['page'])
        if 'title' in raw_sol:
            raw_sol['title'] = ''.join(raw_sol['title'])

        # need the short bibstem only
        if 'bibstem' in raw_sol:
            raw_sol['bibstem'] = raw_sol.get('bibstem')[0]

        # about 199 bibstems start off being published online only, without volume, having tmp for volume, and with eid
        # later they are included in the volume of the publication, with page number that is different then eid, and correct volume
        # see if we have one of those here and included the eid field, since some references use outdated eid
        if 'identifier' in raw_sol:
            bibcode_with_eid = next((b for b in
                                     [i for i in raw_sol['identifier'] if len(i) == len(raw_sol['bibcode'])]
                                     if 'tmp' in b), None)
            if bibcode_with_eid:
                # ('page', 14, 18, 'r', str)
                raw_sol['eid'] = bibcode_with_eid[14:18].strip('.')

        # When you add query keys via resconfig, it's probably wise to add
        # them here, too
        for key in current_app.config['SOLR_KEYS_TO_JOIN']:
            if isinstance(raw_sol.get(key, ''), list):
                raw_sol[key] = ' '.join(raw_sol[key])

        return raw_sol

