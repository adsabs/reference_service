"""
Scoring functions.

These are functions that receive a solr solution and a hypothesis
and return Evidences instances.  These typically pull some "detail"
from the hypothesis, which must have been left there by the hypothesis
generator.  The docstrings should say what kind of details they need.
"""

import re

from flask import current_app

from referencesrv.resolver.authors import add_author_evidence, normalize_author_list
from referencesrv.resolver.common import Evidences
from referencesrv.resolver.journalfield import add_year_evidence, add_page_evidence, \
    add_publication_evidence, add_volume_evidence, has_thesis_indicators, add_title_evidence

def get_author_year_score_for_input_fields(result_record, hypothesis):
    """
    returns evidences based on just author and year.

    For most sources, you should rather use get_basic_score_for_input_fields
    -- see there for more information.
    
    :param result_record: 
    :param hypothesis: 
    :return: 
    """
    input_fields = hypothesis.get_detail('input_fields')

    evidences = Evidences()

    normalized_authors = hypothesis.get_detail('normalized_authors')
    if normalized_authors is None:
        normalized_authors = normalize_author_list(input_fields.get('author', ''))

    add_author_evidence(evidences,
        normalized_authors,
        result_record['author_norm'],
        result_record['first_author_norm'],
        has_etal=hypothesis.get_detail('has_etal'))

    add_year_evidence(evidences,
        input_fields.get('year'),
        result_record.get('year'))

    return evidences


def get_basic_score_for_input_fields(result_record, hypothesis):
    """
    returns a score between result_record and hypothesis.

    This evaluates the basic fields except for pub.

    hypothesis needs an input_fields detail that maps author, pub,
    volume, qualifier, page, and title keys to their values, as
    available.  Empty or missing keys are legal.

    You should pass a normalized_authors detail (in addition to
    input_fields["author"]) to save the work for re-normalizing.

    If the author list had an et al (or similar), set an has_etal
    detail.

    The function will return a page_qualifier (for letters, pink pages,
    etc) detail if given, but will otherwise pull it from page numbers
    as passed in.
    
    :param result_record: 
    :param hypothesis: 
    :return: 
    """
    evidences = get_author_year_score_for_input_fields(result_record, hypothesis)

    input_fields = hypothesis.get_detail('input_fields')

    add_page_evidence(evidences,
        input_fields.get('page'),
        result_record.get('page', []),
        result_record.get('page_range', ''),
        ref_qualifier=hypothesis.get_detail('page_qualifier'))

    add_publication_evidence(evidences,
        input_fields.get('pub'),
        input_fields.get('bibstem',''),
        result_record.get('pub', ''),
        result_record.get('bibcode', ''),
        result_record.get('bibstem', ''))

    add_title_evidence(evidences,
        input_fields.get('title'),
        result_record.get('title', ''))

    return evidences


def get_serial_score_for_input_fields(result_record, hypothesis):
    """
    returns Evidences for result_record matching hypothesis as a serial
    publication.

    See get_basic_score_for_input_fields for what hypothesis needs to have.

    :param result_record:
    :param hypothesis:
    :return:
    """
    evidences = get_basic_score_for_input_fields(result_record, hypothesis)

    input_fields = hypothesis.get_detail("input_fields")

    add_volume_evidence(evidences, input_fields.get("volume"), result_record.get("volume"), result_record.get("issue"))

    return evidences


def get_book_score_for_input_fields(result_record, hypothesis):
    """
    returns Evidences for result_record matching hypothesis as a book.

    This means matching the pub against result_record's title field.

    See get_basic_score_for_input_fields for what hypothesis needs to have.

    :param result_record:
    :param hypothesis:
    :return:
    """
    evidences = get_author_year_score_for_input_fields(result_record, hypothesis)

    if result_record["doctype"]=="book":
        evidences.add_evidence(1, "doctype")
    else:
        evidences.add_evidence(-1, "doctype")

    input_fields = hypothesis.get_detail("input_fields")

    add_publication_evidence(evidences,
        input_fields.get("pub"),
        input_fields.get("bibstem"),
        result_record.get("title", ""),
        result_record.get("bibcode", ""),
        result_record.get("bibstem", ""))

    return evidences


def get_score_for_reference_identifier(result_record, hypothesis):
    """
    returns Evidences for result_record matching if an identifier (doi or arXiv id) was matched
    
    :param result_record: 
    :return: 
    """
    evidences = Evidences()

    input_fields = hypothesis.get_detail("input_fields")

    if compare_doi(input_fields.get("doi", None), result_record.get("doi", [])):
        evidences.add_evidence(current_app.config["EVIDENCE_SCORE_RANGE"][1], "bibcode")
    elif input_fields.get("arxiv", "not in ref") == get_arxiv_id(result_record):
        evidences.add_evidence(current_app.config["EVIDENCE_SCORE_RANGE"][1], "bibcode")
    elif compare_bibcode(input_fields.get("bibcode", None), result_record.get("bibcode", None)):
        evidences.add_evidence(current_app.config["EVIDENCE_SCORE_RANGE"][1], "bibcode")
    else:
        evidences.add_evidence(current_app.config["EVIDENCE_SCORE_RANGE"][0], "bibcode")

    return evidences


def get_thesis_score_for_input_fields(result_record, hypothesis):
    """
    returns Evidences for result_record being some sort of thesis matching
    hypothesis.

    This involves matching of author (including, to some extent, an initial),
    and year.

    We could try to match institutions, but for now we don't.

    :param result_record:
    :param hypothesis:
    :return:
    """
    evidences = Evidences()

    # Theses should only have one author
    if len(result_record["author_norm"])>1:
        evidences.add_evidence(-0.1, "thesis with multiple authors?")

    input_fields = hypothesis.get_detail("input_fields")

    # compare authors manually to have initials included.
    ref_last, ref_first_init = re.sub(r"[\s.]", "", hypothesis.get_detail("normalized_authors")).lower().split(",")
    ref_first_init = ref_first_init[0]
    ads_last, ads_first_init = re.sub(r"[\s.]", "", result_record["author_norm"][0].lower()).split(",")

    if ref_last==ads_last and ref_first_init==ads_first_init:
        evidences.add_evidence(current_app.config["EVIDENCE_SCORE_RANGE"][1], "author")
    else:
        evidences.add_evidence(current_app.config["EVIDENCE_SCORE_RANGE"][0], "author")

    add_year_evidence(evidences,
        input_fields.get('year'),
        result_record.get('year'))

    if has_thesis_indicators(result_record["pub_raw"]):
        evidences.add_evidence(current_app.config["EVIDENCE_SCORE_RANGE"][1], "thesisString")
    else:
        evidences.add_evidence(current_app.config["EVIDENCE_SCORE_RANGE"][0], "thesisString")
    # XXX TODO: When we have pub_raw, we could also check for places;
    # ideally, there would be -1 for a place in refstring not in ADS
    # and +1 for a place in ADS that's also in the refstring.  We'd
    # need a list of places then, though.  I'd have that as a seperate
    # evidence.

    return evidences

def get_arxiv_id(result_record):
    """

    :param result_record:
    :return:
    """
    identifiers = result_record.get("identifier", [])
    for identifier in identifiers:
        if "arXiv:" in identifier:
            return identifier.replace("arXiv:", "")
        if "ascl:" in identifier:
            return identifier.replace("ascl:", "")
    return ""

def compare_doi(ref_doi, ads_doi):
    """
    doi is case insensitive

    :param ref_doi: single doi
    :param ads_doi: list of dois
    :return:
    """
    if ref_doi is None or len(ads_doi) == 0:
        return False

    ref_doi = ref_doi.lower()
    for doi in ads_doi:
        if ref_doi == doi.lower():
            return True
    return False

def compare_bibcode(ref_bibcode, ads_bibcode):
    """
    BIBCODE_FIELDS = [
        ('year', 0, 4, 'r', int),
        ('journal', 4, 9, 'l', str),
        ('volume', 9, 13, 'r', str),
        ('qualifier', 13, 14, 'r', str),
        ('page', 14, 18, 'r', str),
        ('initial', 18, 19, 'r', str)
    ]

    compare bibcodes from reference and from solr
    allow wildcard for volume page or author, however, only one can be missing at at a time
    :param ref_bibcode:
    :param ads_bibcode:
    :return:
    """
    if ref_bibcode is None or ads_bibcode is None:
        return False

    ref_bibcode = ref_bibcode.upper()
    ads_bibcode = ads_bibcode.upper()

    score = 0
    # year has to match
    if ref_bibcode[0:4] == ads_bibcode[0:4]:
        score = score + 1
    # journal has to match
    if ref_bibcode[4:9] == ads_bibcode[4:9]:
        score = score + 1
    # volume can be wildcard, if not penalize
    if ref_bibcode[9:13] == ads_bibcode[9:13]:
        score = score + 1
    elif ref_bibcode[9:13] != '????':
        score = score -1
    # page can be wildcard, if not penalize
    if ref_bibcode[13:18] == ads_bibcode[13:18]:
        score = score + 1
    elif ref_bibcode[13:18] != '???':
        score = score -1
    # first author initial can be wildcard, if not penalize
    if ref_bibcode[18] == ads_bibcode[18]:
        score = score + 1
    elif ref_bibcode[18] != '?':
        score = score - 1
    return score >= 4

