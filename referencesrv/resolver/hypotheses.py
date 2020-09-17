import re

from referencesrv.resolver.common import Hypothesis
from referencesrv.resolver.authors import normalize_author_list, get_first_author_last_name
from referencesrv.resolver.scoring import get_score_for_reference_identifier, get_score_for_input_fields, \
    get_thesis_score_for_input_fields, get_book_score_for_input_fields
from referencesrv.resolver.specialrules import iter_journal_specific_hypotheses
from referencesrv.resolver.journalfield import get_best_bibstem_for, cook_title_string, has_thesis_indicators

from flask import current_app


class Hypotheses(object):
    # Mapping of standard keys to our internal input_field keys.
    field_mappings = [
        ("author", "authors"),
        ("pub", "journal"),
        ("pub", "book"),
        ("volume", "volume"),
        ("issue", "issue"),
        ("page", "page"),
        ("year", "year"),
        ("title", "title"),
        ("refstr", "refstr"),
        ("doi", "doi"),
        ("arxiv", "arxiv"),
        ("ascl", "ascl"),
        ("issn", "issn")
    ]

    ETAL_PAT = re.compile(r"((?i)[\s,]*et\.?\s*al\.?)")
    JOURNAL_LETTER_ATTACHED_VOLUME = re.compile(r"^([ABCDEFGIT])\d+$")
    PAGE_QUALIFIER_AND_PAGE = re.compile(r"([A-Z])(\d+)")
    DETECT_APJL_QUALIFIER = re.compile(r"(ApJL|Let)")
    YEAR_PATTERN = re.compile(r"^([12][089]\d\d)")
    ARXIV_ID_EXTRACTOR = [re.compile(r'(?P<class_name>\w+\-?\w*)?/?(?P<new_pattern>\d{4}\.\d{5})'),
                          re.compile(r'(?P<class_name>\w+\-?\w*)/(?P<old_pattern>\d{7})'),
                          re.compile(r'(?P<old_pattern>\d{7})\s*\[?(?P<class_name>\w+\-?\w*)\]?'), ]
    TITLE_MAIN = re.compile(r"[:]")

    def __init__(self, ref):
        """
        
        :param ref: 
        """
        self.ref = ref
        self.make_digested_record()

    def tokenize_page(self, page):
        """
        see if there is a qualifier attached to the page

        :param page:
        :return:
        """
        match = self.PAGE_QUALIFIER_AND_PAGE.match(page)
        if match:
            return match.group(1), match.group(2)
        return None, page

    def make_digested_record(self):
        """
        adds a digested_record attribute from field_mappings and self.ref.

        This is exclusively called by the constructor.
        :return:
        """
        self.digested_record = {}
        for dest_key, src_key in self.field_mappings:
            value = self.ref.get(src_key)
            if value:
                self.digested_record[dest_key] = value

        self.normalized_authors = None
        if "author" in self.digested_record:
            self.digested_record["author"] = self.ETAL_PAT.sub('', self.digested_record["author"])
            self.normalized_authors = normalize_author_list(self.digested_record["author"], initials='.' in self.digested_record["author"])
            self.normalized_first_author = re.sub(r"\.( ?[A-Z]\.)*", "", re.sub("-[A-Z]\.", "", self.normalized_authors)).split(";")[0].strip()

        if "year" in self.digested_record and len(self.digested_record["year"]) > 4:
            # the extra character(s) are at the end, just to be smart about it let's go with RE
            self.digested_record["year"] = self.YEAR_PATTERN.findall(self.digested_record["year"])[0]

        if self.digested_record.get("page", None):
            if "-" in self.digested_record.get("page"):
                # we are querying on page stat, for now through out the page end
                self.digested_record["page"] = self.digested_record["page"].split("-")[0]
            qualifier, self.digested_record["page"] = self.tokenize_page(self.digested_record["page"])
            if qualifier is not None:
                self.digested_record["qualifier"] = qualifier

        if "volume" in self.digested_record and "pub" in self.digested_record:
            # if volume has a alpha character at the beginning, remove it and attach it to the journal
            # ie. A. Arvanitaki, S. Dimopoulos, S. Dubovsky, N. Kaloper, and J. March-Russell, "String Axiverse," "Phys. Rev.", vol. D81, p. 123530, 2010.
            # which is in fact Journal `Phys. Rev. D.` Volume `81`
            match = self.JOURNAL_LETTER_ATTACHED_VOLUME.match(self.digested_record["volume"])
            if match:
                self.digested_record["pub"] = '%s %s'%(self.digested_record["pub"], self.digested_record["volume"][0])
                self.digested_record["volume"] = self.digested_record["volume"][1:]

        if "title" in self.digested_record:
            # remove too much information
            self.digested_record["title"] = self.TITLE_MAIN.split(self.digested_record["title"])[0]

        if "pub" in self.digested_record:
            try:
                self.digested_record["bibstem"] = get_best_bibstem_for(self.digested_record["pub"])
            except:
                self.digested_record["bibstem"] = ''

        if "arxiv" in self.digested_record:
            # authors specify arxiv id different ways,
            # sometimes for the new format they include class name, which is wrong
            # sometimes for the old format they include class name, but out of order
            # get the correct arxiv_id
            self.digested_record["arxiv"] = self.digested_record["arxiv"].split(":")[-1]
            for aie in self.ARXIV_ID_EXTRACTOR:
                match = aie.match(self.digested_record["arxiv"])
                if match:
                    group_names = match.groupdict().keys()
                    if 'new_pattern' in group_names:
                        self.digested_record["arxiv"] = match.group('new_pattern')
                    elif 'old_pattern' in group_names:
                        self.digested_record["arxiv"] = "%s/%s"%(match.group('class_name'), match.group('old_pattern'))
                    break

        if "ascl" in self.digested_record:
            # remove the ascl prefix if included
            self.digested_record["ascl"] = self.digested_record["ascl"].split(":")[-1]

    def has_keys(self, *keys):
        """
        returns True if the digested record has at least all the fields in keys.

        :param keys:
        :return:
        """
        for key in keys:
            if not self.digested_record.get(key):
                return False
        return True

    def lacks_keys(self, *keys):
        """

        :param keys:
        :return:
        """
        for key in keys:
            if self.digested_record.get(key):
                return False
        return True

    def enough_to_proceed(self):
        """
        check to see if there are enough information to setup queries
        do not blindly create unsuccessful queries

        :return:
        """
        # check authors first
        authors = self.digested_record.get("author", None)
        if authors is not None and len(authors) > 0:
            return True
        # check identifiers next
        if self.digested_record.get("doi", None) is not None:
            return True
        if self.digested_record.get("arxiv", None) is not None:
            return True
        if self.digested_record.get("ascl", None) is not None:
            return True
        return False


    def any_qualifier(self, bibstem, pub):
        """
        if qualifier was send in as part of publication

        :param bibstem:
        :param pub:
        :return:
        """
        if bibstem == 'ApJ':
            if self.DETECT_APJL_QUALIFIER.search(pub):
                return 'L'
        return None

    def has_thesis_indicator_words(self, refstr):
        """

        :param refstr:
        :return:
        """
        for token in refstr.lower().split():
            if token in current_app.config["THESIS_INDICATOR_WORDS"]:
                return True
        return False

    def construct_bibcode(self):
        """
        BIBCODE_FIELDS = [
            ('year', 0, 4, 'r', int),
            ('journal', 4, 9, 'l', str),
            ('volume', 9, 13, 'r', str),
            ('qualifier', 13, 14, 'r', str),
            ('page', 14, 18, 'r', str),
            ('initial', 18, 19, 'r', str)
        ]
        :return:
        """
        year = self.digested_record["year"]
        bibstem = self.digested_record["bibstem"][:5]
        journal = bibstem + (5 - len(bibstem)) * '.'
        volume = self.digested_record.get("volume", "")
        # if no volume is identified, use wildcard
        if len(volume) == 0:
            volume = "????"
        volume = (4 - len(volume)) * '.' + volume
        page_qualifier = self.digested_record.get("qualifier", self.any_qualifier(bibstem, self.digested_record["pub"]))
        # eid can have a dot, remove it first
        page = self.digested_record.get("page", "").replace('.','')
        # if page is more than 4 characters and there is no qualifier,
        # use the qualifier space for the page as well
        if len(page) > 4 and page_qualifier is None:
            page = [page[:5]]
            page_qualifier = ['']
        # if no page is identified, use wildcard for both page and page_qualifier
        elif len(page) == 0:
            page = ["????"]
            page_qualifier = ["?"]
        elif page_qualifier is None:
            page = [(4 - len(page)) * '.' + page] * 2
            page_qualifier = ['.', '?']
        else:
            page = [(4 - len(page)) * '.' + page]
            page_qualifier = [page_qualifier]
        # allow missing author as well
        author = self.normalized_authors[0] if self.normalized_authors else '?'
        collaboration = "collaboration" in self.normalized_authors.lower()
        bibcode = []
        for p, q in zip(page, page_qualifier):
            bibcode.append('{year}{journal}{volume}{page_qualifier}{page}{author}'.format(
                           year=year,journal=journal,volume=volume,page_qualifier=q,page=p,author=author))
            # if there is Collaborations in author list add wildcard bibcode for author,
            # since name of collabration might have been used in bibcode but listed in the reference as second
            if collaboration:
                bibcode.append('{year}{journal}{volume}{page_qualifier}{page}?'.format(
                           year=year,journal=journal,volume=volume,page_qualifier=q,page=p))
        return bibcode

    def iter_hypotheses(self):
        has_etal = self.ETAL_PAT.search(str(self.ref)) is not None

        # If there's a DOI, use it.
        if self.has_keys("doi"):
            yield Hypothesis("fielded-DOI", {
                    "doi": self.digested_record["doi"]},
                get_score_for_reference_identifier,
                input_fields=self.digested_record)

        # If there's a arxiv id, use it.
        if self.has_keys("arxiv"):
            yield Hypothesis("fielded-arxiv", {
                    "arxiv": self.digested_record["arxiv"]},
                get_score_for_reference_identifier,
                input_fields=self.digested_record)

        # If there's a ascl id, use it.
        if self.has_keys("ascl"):
            yield Hypothesis("fielded-ascl", {
                    "ascl": self.digested_record["ascl"]},
                get_score_for_reference_identifier,
                input_fields=self.digested_record)

        # try the old way, construct bibcode
        # if we have solid bibcode make a comprison with bibcode from solr
        # otherwise compare metadata for scoring
        if self.has_keys("year", "pub"):
            for bibcode in self.construct_bibcode():
                self.digested_record.update({'bibcode': bibcode})
                yield Hypothesis("fielded-bibcode", {"bibcode": bibcode},
                    get_score_for_reference_identifier if '?' not in bibcode
                                                       else get_score_for_input_fields,
                    input_fields=self.digested_record,
                    page_qualifier=self.digested_record.get("qualifier", ""),
                    has_etal=has_etal,
                    normalized_authors=self.normalized_authors)

        # could this be a thesis?
        if self.has_keys("author", "year", "refstr") and \
                (self.lacks_keys("volume", "page") or self.has_thesis_indicator_words(
                    self.digested_record["refstr"])):
            # we're checking if any thesis indicators are in pub
            # and later pass on all thesis indicators to solr since we're
            # not sure if the ref thesis words have anything to do with
            # what the ADS thesis words are, plus we don't want any stopwords
            # or other junk in a disjunction, so just oring the words from
            # pub together is not a good idea either.
            if has_thesis_indicators(self.digested_record["refstr"]):
                yield Hypothesis("fielded-thesis", {
                    "author": self.normalized_authors,
                    "pub": "(%s)" % " OR ".join(current_app.config["THESIS_INDICATOR_WORDS"]),
                    "year": self.digested_record["year"]},
                                 get_thesis_score_for_input_fields,
                                 input_fields=self.digested_record,
                                 normalized_authors=self.normalized_authors)

        # try resolving as book, is title in the pub
        if self.has_keys("author", "pub", "year") and self.lacks_keys("title", "volume"):
            cleaned_title = cook_title_string(self.digested_record["pub"])
            # if what's left the the title is too short, revert the cleanup.
            if len(cleaned_title)<15:
                cleaned_title = self.digested_record["pub"]

            yield Hypothesis("fielded-book-pub", {
                   "author": self.normalized_authors,
                    "title": cleaned_title,
                    "year": self.digested_record["year"]},
                get_book_score_for_input_fields,
                input_fields=self.digested_record,
                page_qualifier=self.digested_record.get("qualifier", ""),
                has_etal=False,
                normalized_authors=self.normalized_authors)

        # is it inproceedings that with incomplete metadata (either both volume and page, or either missing)
        if self.has_keys("author", "year") and (self.lacks_keys("volume", "page") or
                                                    self.lacks_keys("volume") or self.lacks_keys("page")):
            yield Hypothesis("fielded-author/year", {
                   "author": self.normalized_authors,
                    "year": self.digested_record["year"]},
                get_score_for_input_fields,
                input_fields=self.digested_record,
                page_qualifier=self.digested_record.get("qualifier", ""),
                has_etal=False,
                normalized_authors=self.normalized_authors)

        # try resolving as book, however, sometimes publication is inbook and hence should check title
        if self.has_keys("author", "title", "year") and self.lacks_keys("volume"):
            yield Hypothesis("fielded-book-title", {
                   "author": self.normalized_authors,
                    "title": self.digested_record["title"],
                    "year": self.digested_record["year"]},
                get_book_score_for_input_fields,
                input_fields=self.digested_record,
                page_qualifier=self.digested_record.get("qualifier", ""),
                has_etal=False,
                normalized_authors=self.normalized_authors)

        # try author, year, pub, volume, and page
        if self.has_keys("author", "year", "volume", "page"):
            yield Hypothesis("fielded-author/year/volume/page", {
                "author": self.normalized_authors,
                "year": self.digested_record["year"],
                "volume": self.digested_record["volume"],
                "page": self.digested_record.get("qualifier", "")+self.digested_record["page"]},
                             get_score_for_input_fields,
                             input_fields=self.digested_record,
                             page_qualifier=self.digested_record.get("qualifier", ""),
                             has_etal=has_etal,
                             normalized_authors=self.normalized_authors)

        # search by author, bibstem, and year
        if self.has_keys("author", "pub", "year"):
            yield Hypothesis("fielded-author/pub/year", {
                    "author": self.normalized_authors,
                    "bibstem": self.digested_record["bibstem"],
                    "year": self.digested_record["year"]},
                get_score_for_input_fields,
                input_fields=self.digested_record,
                page_qualifier=self.digested_record.get("qualifier", ""),
                has_etal=has_etal,
                normalized_authors=self.normalized_authors)

        # pull out titles
        if self.has_keys("author", "year", "title"):
            yield Hypothesis("fielded-title/author/year", {
                "first_author_norm": self.normalized_first_author,
                "year": self.digested_record["year"],
                "title": self.digested_record["title"],},
            get_score_for_input_fields,
            input_fields=self.digested_record,
            page_qualifier='',
            has_etal=False,
            normalized_authors=self.normalized_authors)

        # try some reference type-specific hypotheses
        if "pub" in self.digested_record:
            for hypo in iter_journal_specific_hypotheses(
                    self.digested_record.get("bibstem"),
                    self.digested_record.get("year"),
                    self.normalized_authors,
                    self.digested_record.get("pub"),
                    self.digested_record.get("volume"),
                    self.digested_record.get("page"),
                    self.digested_record.get("refstr")):
                yield hypo

        # try author search with either volume or page
        if self.has_keys("author"):
            # with volume
            if self.has_keys("volume"):
                yield Hypothesis("fielded-author/volume", {
                    "author": self.normalized_authors,
                    "volume": self.digested_record["volume"]},
                    get_score_for_input_fields,
                    input_fields=self.digested_record)
            # with page
            if self.has_keys("page"):
                yield Hypothesis("fielded-author/page", {
                    "author": self.normalized_authors,
                    "page": self.digested_record["page"]},
                    get_score_for_input_fields,
                    input_fields=self.digested_record)

        # now fuzzy search
        if self.has_keys("author", "year"):
            # approximate first author
            yield Hypothesis("fielded-first-author~/year", {
                "first_author_norm~": self.normalized_first_author,
                "year": self.digested_record["year"]},
                get_score_for_input_fields,
                input_fields=self.digested_record,
                page_qualifier=self.digested_record.get("qualifier", ""),
                has_etal=has_etal,
                normalized_authors=self.normalized_authors)
            # and now approximate year
            yield Hypothesis("fielded-author/year~", {
                "author": self.normalized_authors,
                "year~": self.digested_record["year"]},
                get_score_for_input_fields,
                input_fields=self.digested_record,
                page_qualifier=self.digested_record.get("qualifier", ""),
                has_etal=has_etal,
                normalized_authors=self.normalized_authors)

        # last effort, if no author!
        # try bibstem-year-volume-page
        if self.has_keys("year", "pub", "volume", "page"):
            yield Hypothesis("fielded-no-author", {
                    "bibstem": self.digested_record["bibstem"],
                    "year": self.digested_record["year"],
                    "volume": self.digested_record["volume"],
                    "page": self.digested_record.get("qualifier", "")+self.digested_record["page"]},
                get_score_for_input_fields,
                input_fields=self.digested_record,
                page_qualifier='',
                has_etal=False,
                normalized_authors=self.normalized_authors)

        # last effort, if no year!
        # try author-bibstem-volume-page
        if self.has_keys("author", "pub", "volume", "page"):
            yield Hypothesis("fielded-no-year", {
                "author": self.normalized_authors,
                "bibstem": self.digested_record["bibstem"],
                "volume": self.digested_record["volume"],
                "page": self.digested_record["page"]},
                             get_score_for_input_fields,
                             input_fields=self.digested_record,
                             page_qualifier=self.digested_record.get("qualifier", ""),
                             has_etal=has_etal,
                             normalized_authors=self.normalized_authors)

