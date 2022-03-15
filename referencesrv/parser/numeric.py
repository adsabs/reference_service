"""
This module keeps track of numeric tokens doi/arxiv/ascl/year/volume/page/issue

"""

import regex as re
import datetime
from collections import OrderedDict
import urllib

from referencesrv.parser.common import concatenate, replace

class NumericToken():

    # note that there is no identifier for year, but need to have line up labels and values
    IDENTIFYING_TOKEN = OrderedDict(
        [('DOI_IDENTIFIER', ['doi']), ('ARXIV_IDENTIFIER', ['arxiv']), ('ASCL_IDENTIFIER', ['ascl']),
         ('YEAR_IDENTIFIER', ['']), ('VOLUME_IDENTIFIER', ['volume', 'vol']), ('PAGE_IDENTIFIER', ['page', 'pages', 'pp', 'p']),
         ('ISSN__IDENTIFIER', ['issn']), ('ISBN__IDENTIFIER', ['isbn']),
         ('VERSION_IDENTIFIER', ['version']), ('ISSUE_IDENTIFIER', ['issue'])])

    # numeric labels
    NUMERIC_TAGS = ['DOI', 'ARXIV', 'ASCL', 'YEAR', 'VOLUME', 'PAGE', 'ISSN', 'ISBN', 'VERSION', 'ISSUE']

    PLACEHOLDER = {'doi': '|doi_%d|', 'arxiv': '|arxiv_%d|', 'ascl': '|ascl|',
                   'year': '|year|', 'volume': '|volume|', 'page': '|page|', 'issue': '|issue|',
                   'volume_identifier':'|volume_identifier|', 'page_identifier':'|page_identifier|'}

    DOI_ID_EXTRACTOR = re.compile(r'(?P<doi>((?i:doi))?[\s\.\:]{0,2}\b10\.\s*\d{4}[\d\:\.\-\_\/\(\)%A-Za-z\s]+)')
    DOI_INDICATOR = re.compile(r'(?i:doi:)')
    DOI_INDICATOR_CAPTURE = re.compile(r'((?i:doi:)\s*)')
    ARXIV_ID_EXTRACTOR = re.compile(r'(?P<arxiv>((?i:(arxiv)))?[\s\:]*('
                                    r'[A-Za-z]+\-[A-Za-z]+\/\d{4}\.\d{5}|[A-Za-z]+\/\d{4}\.\d{5}'       # new format with unneccesary class name
                                    r'|\d{4}\.\d{4,5}'                                                  # new format
                                    r'|[A-Za-z]+\-[A-Za-z]+\/\d{7}|[A-Za-z]+\/\d{7}'                    # old format
                                    r'|\d{7}\s*\[?([A-Za-z]+-[A-Za-z]+|[A-Za-z]+)\]?)'                  # old format with class name in wrong place
                                    r'(v?\d*))')                                                        # version
    ASCL_ID_EXTRACTOR = re.compile(r'(?P<ascl>(ascl)?[\s\:]*(\d{4}\.\d{3}))')
    ARXIV_ASCL_INDICATOR = re.compile(r'((?i:arXiv)):|(?i:ascl):')

    YEAR_EXTRACTOR = re.compile(r'[(\s]*\b([12][089]\d\d[a-z]?)[)\s.,]+')
    VOLUME_EXTRACTOR = re.compile(r'(vol|volume)[.\s]+(?P<volume>\w+)')
    PAGE_EXTRACTOR_QUALIFIER = re.compile(r'(?=.*[0-9])(?P<page>[BHPL0-9]+[-.][BHPL0-9]+)')
    PAGE_EXTRACTOR_INDICATOR = re.compile(r'(\|page_identifier\|[.\s]+(?P<page>\d+))')

    # two specific formats for matching volume, page, issue
    # note that in the first expression issue matches a space, there is no issue in this format,
    # it is included to have all three groups present
    # also consider page pattern like 121(11):11,077-11,085
    MULTI_TOKEN_EXTRACTOR = [re.compile(r'(?P<volume>[A-Z]?\d+)\s+(?P<issue>\d+)\s*\:(?P<page>[ABHPL]?\d+\-?[ABHPL]?\d*)'),
                             re.compile(r'(?P<volume>[A-Z]?\d+)\:(?P<page>[A-Z]?\d+\-?[ABHPL]?\d*)(?P<issue>\s*)'),
                             re.compile(r'(?P<volume>[A-Z]?\d+)\((?P<issue>\d+)\)\:(?P<page>\d+\,?\d*\-?\d*\,?\d*|[ABHPL]?\d+\-?[ABHPL]?\d*)')]

    # should star with a digit, or end with a digit, or be all digits
    IS_MOSTLY_DIGIT = re.compile(r'(\b[A-Za-z0-9]+[0-9]\b|\b[0-9]+[0-9A-Za-z]\b|\b[0-9]\b)')

    MATCH_INSIDE_PARENTHESIS = r'(\(%s\))'

    MATCH_A_WORD = re.compile(r'\w+')

    WITH_QUALIFIER_PATTERN = r'\b[A-Z]%s\b'

    # from adspy
    # # regex for ISBN
    # ISBNregex = re.compile(r'\b([\d\-]+)\b')

    ISBN_EXTRACTOR = re.compile(r'(?P<isbn>ISBN(?:-)?:?\ (978-?|979-?)?\d{1,5}-?\d{1,7}-?\d{1,6}-?\d{1,3})')
    ISSN_EXTRACTOR = re.compile(r'(?P<issn>ISSN[:\s]+\d{4}-?\d{3}[\d\w]{1})')


    def __init__(self):
        """

        """
        self.segment_dict = {}

        self.year_now = datetime.datetime.now().year
        self.year_earliest =  1400

        self.volume_identifying_words = re.compile(r'\b(%s)\b' % '|'.join(self.IDENTIFYING_TOKEN['VOLUME_IDENTIFIER']), re.IGNORECASE)
        self.page_identifying_words = re.compile(r'\b(%s)\b' % '|'.join(self.IDENTIFYING_TOKEN['PAGE_IDENTIFIER']), re.IGNORECASE)


    def clear(self):
        """

        :return:
        """
        self.segment_dict = {}


    def segment_ids(self, reference_str):
        """
        identify doi/arxiv/ascl ids

        :param reference_str:
        :return: reference_str with the identified ids removed
        """
        # extract doi if there are any
        # note that there could be more than one doi
        doi = self.extract_doi(reference_str)
        if doi:
            # remove duplicates if any
            doi = list(set(doi))
            reference_str = self.remove_value(reference_str, 'doi', doi)
            doi = [urllib.parse.unquote(d.replace(' ', '').split(':')[-1]) for d in doi]
        else:
            doi = []

        # extract arXiv id if there are any
        # note that there could be more than one arxiv num
        arxiv = []
        matches = self.ARXIV_ID_EXTRACTOR.findall(reference_str)
        if matches:
            for match in matches:
                arxiv.append(match[0])
            # remove duplicates if any
            arxiv = list(set(arxiv))
            reference_str = self.remove_value(reference_str, 'arxiv', arxiv)
            arxiv = [a.split(':')[-1].strip() for a in arxiv]

        # extract arxiv id if there is one
        ascl_id = self.ASCL_ID_EXTRACTOR.search(reference_str)
        if ascl_id:
            ascl_id = ascl_id.group('ascl')
            reference_str = reference_str.replace(ascl_id, self.PLACEHOLDER['ascl'])
        else:
            ascl_id = ''

        issn = isbn = ''
        # extract issn if there is one
        issn_match = self.ISSN_EXTRACTOR.search(reference_str)
        if issn_match:
            issn = issn_match.group('issn')
            reference_str = reference_str.replace(issn, '')
        # extract isbn if there is one
        isbn_match = self.ISBN_EXTRACTOR.search(reference_str)
        if isbn_match:
            isbn = isbn_match.group('isbn')
            reference_str = reference_str.replace(isbn, '')

        # TODO: version has been tagged in a training file, we are not
        # using that to identify reference yet, so have the PLACEHOLDER for it now
        self.segment_dict.update({'doi': doi, 'arxiv': arxiv, 'ascl': ascl_id.replace(' ', '').split(':')[-1],
                                  'issn': issn, 'isbn': isbn, 'version': ''})
        return reference_str


    def segment_numerals(self, reference_str):
        """
        identifiy year/volume/issue/page

        :param reference_str:
        :param unknown: numeric values that were not able to be identified
        :return:
        """
        year, reference_str = self.segment_year(reference_str)

        # see if can extract numeric based on a patters
        for ne in self.MULTI_TOKEN_EXTRACTOR:
            extractor = ne.search(reference_str)
            if extractor:
                volume = extractor.group('volume')
                page = extractor.group('page').strip(',')
                issue = extractor.group('issue').strip()
                reference_str = self.mark_identified_numerals(reference_str, volume, page, issue)
                self.segment_dict.update({'page': page, 'year': year, 'volume': volume, 'issue': issue})
                return reference_str

        # if there is page in the form of start-end or eid in the format of number.number
        page = self.PAGE_EXTRACTOR_QUALIFIER.search(reference_str)
        if page:
            page = page.group('page')
            reference_str = replace(page, reference_str, self.PLACEHOLDER['page'])
        else:
            # if there is an indicator
            page = self.PAGE_EXTRACTOR_INDICATOR.search(reference_str)
            if page:
                page = page.group('page')
                reference_str = replace(page, reference_str, self.PLACEHOLDER['page'])
            else:
                page = ''

        # if there is a volume indicator
        volume = self.VOLUME_EXTRACTOR.search(reference_str)
        if volume:
            volume = volume.group('volume')
            reference_str = replace(volume, reference_str, self.PLACEHOLDER['volume'])
        else:
            volume = ''

        issue = ''

        # the rest, also remove duplicates
        the_rest = list(OrderedDict.fromkeys(self.IS_MOSTLY_DIGIT.findall(reference_str)))

        # continue only if need to guess values for one of these fields, otherwise return
        if len(volume) == 0 or len(page) == 0:
            unknown = ' '.join([elem for elem in self.MATCH_A_WORD.findall(reference_str)
                                if elem not in the_rest and not self.is_identifying_word(elem)])
            if len(the_rest) > 0:
                # if volume is not detected yet, and there are more than three tokens,
                # since volume is usually the first entity and it is mostly numeric value,
                # throw every alphanumeric element before it out to start with a numeric value
                # and guess it is as volume
                if len(volume) == 0 and len(the_rest) > 3:
                    try:
                        the_rest_numeric = the_rest[the_rest.index(next(elem for elem in the_rest if elem.isdigit())):]
                        unknown = concatenate(unknown, ' '.join([non_numeric for non_numeric in the_rest
                                                                 if non_numeric not in the_rest_numeric]))
                        the_rest = the_rest_numeric
                    except:
                        unknown = concatenate(unknown, ' '.join(the_rest))
                        the_rest = ''
                # how many numeric value do we have?
                # if more than 3, we have no guesses so return
                if len(the_rest) <= 3:
                    # if we have three elements, neither volume nor page should have been identified at this point
                    # in this case in order of most likely fields we have volume, issue, page
                    if len(the_rest) == 3 and len(volume) == 0 and len(page) == 0:
                        volume = the_rest[0]
                        issue = the_rest[1]
                        page = the_rest[2]
                    # if we have two elements, one of volume or page has to be empty
                    elif len(the_rest) == 2 and (len(volume) == 0 or len(page) == 0):
                        # if volume is empty, then most likely the first element is volume
                        # and then depending on if page is empty or not the next element
                        # is either page or issue respectively
                        if len(volume) == 0:
                            volume = the_rest[0]
                            if len(page) == 0:
                                page = the_rest[1]
                            else:
                                issue = the_rest[1]
                        # if volume is set, then if page is empty,
                        # assign the two elements to page and issue respectively
                        # however if page is set, and there are two elements remaining,
                        # cannot tell which could be issue, leave it as easy, already assigned empty to it above
                        elif len(page) == 0:
                            page = the_rest[1]
                            issue = the_rest[0]
                        else:
                            unknown = concatenate(unknown, ' '.join(the_rest))
                    # if one element is left,
                    # the order of most likely is volume if not set, page if not set, issue
                    elif len(the_rest) == 1:
                        if len(volume) == 0:
                            volume = the_rest[0]
                        elif len(page) == 0:
                            page = the_rest[0]
                        else:
                            issue = the_rest[0]
                    else:
                        unknown = concatenate(unknown, ' '.join(the_rest))
            volume = self.numeric_with_qualifier(reference_str, volume)
            page = self.numeric_with_qualifier(reference_str, page)
            reference_str = self.mark_identified_numerals(reference_str, volume, page, issue)

        self.segment_dict.update({'page': page, 'year': year, 'volume': volume, 'issue': issue})
        return reference_str


    def segment_year(self, reference_str):
        """
        identify the year
        note that year could be alphanumeric (ie, 2020a)

        :param reference_str:
        :return:
        """
        year = list(OrderedDict.fromkeys(self.YEAR_EXTRACTOR.findall(reference_str)))
        if len(year) > 1:
            # see if one has appeared in parenthesis, pick that one
            for y in year:
                if re.search(self.MATCH_INSIDE_PARENTHESIS % y, reference_str):
                    year = [y]
                    break
            # if still have more than one, remove alphanumeric and see if there is only one that can be accepted
            if len(year) > 1:
                year = [y for y in year if y.isnumeric() and int(y) >= self.year_earliest and int(y) <= self.year_now]
        if len(year) == 1:
            year = year[0]
            reference_str = replace(year, reference_str, self.PLACEHOLDER['year'])
        # could not identify the year here
        else:
            year = ''
        return year, reference_str


    def fill_value(self, ref_word_list, token_label):
        """
        for multi-value token, represented as lists (ie, doi, arxiv)

        :param ref_word_list:
        :param token_label:
        :return:
        """
        for i, v in enumerate(self.segment_dict.get(token_label, []), start=1):
            ref_word_list[ref_word_list.index(self.PLACEHOLDER[token_label] % i)] = v
        return ref_word_list


    def remove_value(self, reference_str, token_label, value):
        """
        replace value with a placeholder, for multi-value token, represented as lists (ie, doi, arxiv)

        :param reference_str:
        :param token_label:
        :param value:
        :return:
        """
        for i, v in enumerate(value, start=1):
            reference_str = reference_str.replace(v, self.PLACEHOLDER[token_label] % i)
        return reference_str


    def numeric_with_qualifier(self, reference_str, value):
        """
        for fields with qualifier, check to see if there is a one and return the token
        otherwise return the value

        :param reference_str:
        :param value:
        :return:
        """
        if len(value) > 0:
            match = re.findall(self.WITH_QUALIFIER_PATTERN % value, reference_str)
            if len(match) > 0:
                return match[0]
        return value

    def mark_identified_numerals(self, reference_str, volume, page, issue):
        """
        insert placeholder id in the position of identified numerals

        :param reference_str:
        :param volume:
        :param page:
        :param issue:
        :return:
        """
        if len(volume) > 0:
            reference_str = replace(volume, reference_str, self.PLACEHOLDER['volume'])
        if len(page) > 0:
            reference_str = replace(page, reference_str, self.PLACEHOLDER['page'])
        if len(issue) > 0:
            reference_str = replace(issue, reference_str, self.PLACEHOLDER['issue'])
        return reference_str


    def assemble_stage1(self, reference_str):
        """
        replaces PLACEHOLDER text with values identified previously
        in stage 1, that is year/volume/issue values, doi/arxiv/ascl labels, and volume/page identifiers if any

        :param reference_str:
        :return:
        """
        if len(self.segment_dict.get('year', '')) > 0:
            reference_str = reference_str.replace(self.PLACEHOLDER['year'], self.segment_dict.get('year'))
        if len(self.segment_dict.get('volume', '')) > 0:
            reference_str = reference_str.replace(self.PLACEHOLDER['volume'], self.segment_dict.get('volume'))
        if len(self.segment_dict.get('issue', '')) > 0:
            reference_str = reference_str.replace(self.PLACEHOLDER['issue'], self.segment_dict.get('issue'))

        if len(self.segment_dict.get('volume_identifier', '')) > 0:
            reference_str = reference_str.replace(self.PLACEHOLDER['volume_identifier'], self.segment_dict.get('volume_identifier'))
        if len(self.segment_dict.get('page_identifier', '')) > 0:
            reference_str = reference_str.replace(self.PLACEHOLDER['page_identifier'], self.segment_dict.get('page_identifier'))

        # also add the identifier labels
        if len(self.segment_dict.get('doi', [])) > 0:
            for i in range(1, len(self.segment_dict.get('doi'))+1):
                reference_str = reference_str.replace(self.PLACEHOLDER['doi']%i, ' doi:'+self.PLACEHOLDER['doi']%i)
        if len(self.segment_dict.get('arxiv', [])) > 0:
            for i in range(1, len(self.segment_dict.get('arxiv'))+1):
                reference_str = reference_str.replace(self.PLACEHOLDER['arxiv']%i, ' arXiv:'+self.PLACEHOLDER['arxiv']%i)
        if len(self.segment_dict.get('ascl', '')) > 0:
            reference_str = reference_str.replace(self.PLACEHOLDER['ascl'], ' ascl:' + self.PLACEHOLDER['ascl'])
        return reference_str


    def assemble_stage2(self, ref_word_list):
        """
        replaces PLACEHOLDER text with values identified previously
        in stage 2, that is page/doi/arxiv/ascl values

        :param ref_word_list:
        :return:
        """
        if len(self.segment_dict.get('page', '')) > 0:
            for idx in [i for i, x in enumerate(ref_word_list) if self.PLACEHOLDER['page'] in x]:
                ref_word_list[idx] = ref_word_list[idx].replace(self.PLACEHOLDER['page'], self.segment_dict.get('page'))
        if len(self.segment_dict.get('doi', '')) > 0:
            ref_word_list = self.fill_value(ref_word_list, 'doi')
        if len(self.segment_dict.get('arxiv', '')) > 0:
            ref_word_list = self.fill_value(ref_word_list, 'arxiv')
        if len(self.segment_dict.get('ascl', '')) > 0:
            ref_word_list[ref_word_list.index(self.PLACEHOLDER['ascl'])] = self.segment_dict.get('ascl')
        return ref_word_list


    def extract_doi(self, reference_str):
        """

        :param reference_str:
        :return:
        """
        match = self.DOI_ID_EXTRACTOR.search(reference_str)
        if match:
            is_doi = match.group('doi')
            if is_doi:
                doi = []
                # becasue the doi format varies we are considering everything after doi or DOI or 10,
                # if by any chance arxiv id is followed by doi, without any comma, or bracket to signal
                # the end of doi, it is considered to be part of doi
                # actually have encountered references with multiple dois too
                # so far doi and arxiv always came at the end, we are actually ok if arxiv is first
                # however if arxiv appears after doi, as mentioned above, it gets matched as part of doi,
                # in this case need to check for this, also ascl is the same way
                # have seen a few references with having doi and arxiv in the form of url appearing after doi
                # (ie, N. Blagorodnova, S. Gezari, T. Hung, S.R. Kulkarni, S.B. Cenko, D.R. Pasham, L. Yan, I. Arcavi, S. Ben-Ami, B.D. Bue, T. Cantwell, Y. Cao, A.J. Castro-Tirado, R. Fender, C. Fremling, A. Gal-Yam, A.Y.Q. Ho, A. Horesh, G. Hosseinzadeh, M.M. Kasliwal, A.K.H.H. Kong, R.R. Laher, G. Leloudas, R. Lunnan, F.J. Masci, K. Mooley, J.D. Neill, P. Nugent, M. Powell, A.F. Valeev, P.M. Vreeswijk, R. Walters, P. Wozniak, iPTF16fnl: a faint and fast tidal disruption event in an E+A galaxy. The Astrophysical Journal 844(46) (2017). doi:10.3847/1538-4357/aa7579. http://arxiv.org/abs/1703.00965 http://dx.doi.org/10.3847/1538-4357/aa7579)
                # first see if more than one doi is available
                # and then see for each doi, did we got only a doi or arxiv/ascl following it as well
                is_doi_indicator = self.DOI_INDICATOR_CAPTURE.findall(is_doi)
                is_doi = [self.ARXIV_ASCL_INDICATOR.split(item)[0].strip()
                            for item in list(filter(None, self.DOI_INDICATOR.split(is_doi)))]
                if len(is_doi_indicator) == 0:
                    is_doi_indicator = [''] * len(is_doi)
                for item, indicator in zip(is_doi, is_doi_indicator):
                    if item.endswith('.'):
                        item = item[:-1]
                    doi.append(indicator + item)
                return doi
        return None


    def exist(self, ref_word, ref_label):
        """
        during training/testing ref_label is populated, see if it is one of us
        during normal operation see if ref_word has been identified as one us

        :param ref_word:
        :param ref_label:
        :return:
        """
        if ref_label:
            return 1 if ref_label in self.NUMERIC_TAGS else 0
        return int(any(ref_word == self.segment_dict.get(tag.lower(), None) for tag in self.NUMERIC_TAGS))


    def is_tagged_token_doi(self, ref_word):
        """
        see if a token that has been tagged as doi, is actually doi

        :param ref_word:
        :return:
        """
        doi = self.extract_doi(ref_word)
        if doi:
            doi = doi[0]
            return 'doi:%s'%doi[doi.find('10'):]
        return None


    def is_tagged_token_arxiv(self, ref_word):
        """
        verify what has been tagged as arxiv is actually arxiv id

        :param ref_word_list:
        :param ref_label_list:
        :param tagged_as: this is single value
        :return:
        """
        arxiv = self.ARXIV_ID_EXTRACTOR.search(ref_word)
        if arxiv:
            return 'arXiv:%s'%arxiv.group('arxiv').split(':')[-1]
        return None


    def is_tagged_token_ascl(self, ref_word):
        """
        verify what has been tagged as ascl is actually ascl id

        :param ref_word_list:
        :param ref_label_list:
        :param tagged_as: this is a list, either or both 'ASCL', 'ARXIV'
        :return:
        """
        ascl = self.ASCL_ID_EXTRACTOR.search(ref_word)
        if ascl:
            return 'ascl:%s'%ascl.group('ascl').split(':')[-1]
        return None


    def is_token_this_label(self, ref_word, ref_label, this_label):
        """
        verify if the tagged token is of type this
        
        :param ref_word:
        :param ref_label:
        :param this_label:
        :return:
        """
        if ref_label:
            return 1 if ref_label == this_label else 0
        this_token = self.segment_dict.get(this_label.lower())
        if isinstance(this_token, list):
            return 1 if any(ref_word == one for one in this_token) else 0
        return 1 if ref_word == this_token else 0


    def is_token_year(self, ref_word, ref_label):
        """

        :param ref_word:
        :param ref_label:
        :return:
        """
        return self.is_token_this_label(ref_word, ref_label, 'YEAR')


    def is_token_volume(self, ref_word, ref_label):
        """

        :param ref_word:
        :param ref_label:
        :return:
        """
        return self.is_token_this_label(ref_word, ref_label, 'VOLUME')


    def is_token_page(self, ref_word, ref_label):
        """

        :param ref_word:
        :param ref_label:
        :return:
        """
        return self.is_token_this_label(ref_word, ref_label, 'PAGE')


    def is_token_issue(self, ref_word, ref_label):
        """

        :param ref_word:
        :param ref_label:
        :return:
        """
        return self.is_token_this_label(ref_word, ref_label, 'ISSUE')


    def is_token_arxiv(self, ref_word, ref_label):
        """

        :param ref_word:
        :param ref_label:
        :return:
        """
        return self.is_token_this_label(ref_word, ref_label, 'ARXIV')


    def is_token_doi(self, ref_word, ref_label):
        """

        :param ref_word:
        :param ref_label:
        :return:
        """
        return self.is_token_this_label(ref_word, ref_label, 'DOI')


    def is_token_issn_isbn(self, ref_word, ref_label):
        """

        :param ref_word:
        :param ref_label:
        :return:
        """
        return self.is_token_this_label(ref_word, ref_label, 'ISSN') or \
               self.is_token_this_label(ref_word, ref_label, 'ISBN')


    def is_token_ascl(self, ref_word, ref_label):
        """

        :param ref_word:
        :param ref_label:
        :return:
        """
        return self.is_token_this_label(ref_word, ref_label, 'ASCL')


    def is_token_version(self, ref_word, ref_label):
        """

        :param ref_word:
        :param ref_label:
        :return:
        """
        return self.is_token_this_label(ref_word, ref_label, 'VERSION')


    def numeric_features(self, ref_word, ref_label):
        """
        
        :param ref_word: 
        :param ref_label: 
        :return: 
        """
        return [
            self.exist(ref_word, ref_label),                # is it numeric?
            self.is_token_doi(ref_word, ref_label),         # is it more likely doi?
            self.is_token_arxiv(ref_word, ref_label),       # is it more likely arXiv id?
            self.is_token_ascl(ref_word, ref_label),        # is it more likely ascl?
            self.is_token_year(ref_word, ref_label),        # is it more likely year?
            self.is_token_volume(ref_word, ref_label),      # is it more likely volume?
            self.is_token_page(ref_word, ref_label),        # is it more likely page?
            self.is_token_issn_isbn(ref_word, ref_label),   # is it more likely issn/isbn?
            self.is_token_version(ref_word, ref_label),     # is it more likely issue?
            self.is_token_issue(ref_word, ref_label),       # is it more likely issue?
        ]


    def is_identifying_word(self, ref_word):
        """
        verify if ref_word is one of the numeric identifying tokens appear before the value
        ie, volume, page, etc
        
        :param ref_word:
        :return:
        """
        if ref_word and ref_word.isalpha():
            for i, word in enumerate(self.IDENTIFYING_TOKEN.values()):
                for w in word:
                    if w == ref_word.lower():
                        return i+1
        return 0


    def remove_identifying_words(self, reference_str):
        """
        remove identifying words from reference_str
        useful before attempting to identify title/journal/publisher tokens
        
        :param reference_str:
        :return:
        """
        match = self.volume_identifying_words.search(reference_str)
        if match:
            volume_identifier = match.group()
            self.segment_dict.update({'volume_identifier':volume_identifier})
            reference_str = replace(volume_identifier, reference_str, self.PLACEHOLDER['volume_identifier'])
        match = self.page_identifying_words.search(reference_str)
        if match:
            page_identifier = match.group()
            self.segment_dict.update({'page_identifier':page_identifier})
            reference_str = replace(page_identifier, reference_str, self.PLACEHOLDER['page_identifier'])
        return reference_str


    def which_identifying_word(self, ref_word, ref_label):
        """
        verify if ref_word is one of the identifying words, and determine which one
        
        :param ref_word:
        :param ref_label:
        :return: 1 if doi, 2 if arXiv, 3 if ascl, 4 if volume, 5 if page, 6 if issn/isbn, 7 if version, 8 if issue
        """
        if ref_label:
            return list(self.IDENTIFYING_TOKEN.keys()).index(ref_label)+1 if ref_label in self.IDENTIFYING_TOKEN.keys() else 0
        return self.is_identifying_word(ref_word)


    def identifying_word_features(self, ref_word, ref_label):
        """
        return a feature vector that has 1 in the first cell if ref_word is identifying word
        followed by 1 in the position corresponding to which one
        
        :param ref_word:
        :param ref_label:
        :return:
        """
        which = self.which_identifying_word(ref_word, ref_label)
        return [
            1 if which == 0 else 0,   # 0 is one of the identifying words
            1 if which == 1 else 0,   # 1 if doi,
            1 if which == 2 else 0,   # 2 if arXiv,
            1 if which == 3 else 0,   # 3 if ascl,
            1 if which == 4 else 0,   # 4 if volume,
            1 if which == 5 else 0,   # 5 if page,
            1 if which == 6 else 0,   # 6 if issn/isbn,
            1 if which == 7 else 0,   # 7 if version,
            1 if which == 8 else 0,   # 8 if issue,
        ]


    def cycle_tagged_token(self, ref_word, tagged_list):
        """
        occasionally crf tags an id mistakenly, have added all the combination ids that I think we have
        single and multiple doi, single and multiple arxiv, doi and arxiv in this order and reverse
        just to be sure, we know the pattern of each id, verify it is correct
        
        :param ref_word:
        :param tagged_list: order of tags to try
        :return:
        """
        functions = {'DOI': self.is_tagged_token_doi,
                     'ARXIV': self.is_tagged_token_arxiv,
                     'ASCL': self.is_tagged_token_ascl}
        for tag in tagged_list:
            id = functions[tag](ref_word)
            if id:
                return tag.lower(), id
        return None, None


    def collect_id_tagged_tokens(self, ref_word_list, ref_label_list):
        """
        go through the list of tagged tokens and collect all that are ids that correctly
        matches the pattern of id as we know it
        
        :param ref_word_list: 
        :param ref_label_list: order of 
        :return: 
        """
        order_to_match = {'DOI':['DOI', 'ARXIV', 'ASCL'],
                          'ARXIV':['ARXIV', 'ASCL', 'DOI'],
                          'ASCL': ['ASCL', 'DOI', 'ARXIV']}
        matches = {}
        idx = [i for i, l in enumerate(ref_label_list) if l in ['DOI', 'ARXIV', 'ASCL']]
        for i in idx:
            id_tag, id = self.cycle_tagged_token(ref_word_list[i], order_to_match[ref_label_list[i]])
            # TODO: return multiple tagged doi and arxiv
            # for now return the first one and make sure the id_tag is not included
            # some references included and hence it is parsed, some do not, so remove it if included
            if id_tag:
                matches.update({id_tag: id.replace('%s:'%id_tag,'')})
        return matches


    def collect_tagged_numerals_token(self, ref_word_list, ref_label_list, tag):
        """

        :param ref_word_list:
        :param ref_label_list:
        :param tag:
        :return:
        """
        # TODO: first figure out why multiple unequal tokens are marked as volume/page if possible
        # since there should be only one per reference, the same token appearing multiple times is OK
        # if could not figure it out, return multiple tokens and let resolver matches both against solr
        # for now if there are multiple unequal tokens return the first numeric value
        tokens = [ref_word_list[i] for i, value in enumerate(ref_label_list) if value == tag]
        if len(tokens) == 1:
            return tokens[0]
        # see if the multiple token tagged as tag entity are all the same
        the_token = tokens[0]
        for i in range(1, len(tokens)):
            if tokens[i] != the_token:
                the_token = None
                break
        if the_token:
            return the_token
        for token in tokens:
            if token.isdigit():
                return token
        return None
