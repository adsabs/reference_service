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

    :param result_record:
    :param hypothesis: 
    :return: 
    """
    input_fields = hypothesis.get_detail('input_fields')

    normalized_authors = hypothesis.get_detail('normalized_authors')
    if normalized_authors is None:
        normalized_authors = normalize_author_list(input_fields.get('author', ''))

    evidences = Evidences()

    add_author_evidence(evidences,
        normalized_authors,
        result_record['author_norm'],
        result_record['first_author_norm'],
        has_etal=hypothesis.get_detail('has_etal'))

    add_year_evidence(evidences,
        input_fields.get('year'),
        result_record.get('year'))

    return evidences


def get_author_year_pub_score_for_input_fields(result_record, hypothesis):
    """
    returns evidences based on just author, year and publication.

    :param result_record:
    :param hypothesis:
    :return:
    """
    evidences = get_author_year_score_for_input_fields(result_record, hypothesis)

    input_fields = hypothesis.get_detail("input_fields")

    add_publication_evidence(evidences,
        input_fields.get("pub", ""),
        input_fields.get("bibstem",""),
        input_fields.get("refstr", ""),
        result_record.get("pub", ""),
        result_record.get("bibcode", ""),
        result_record.get("bibstem", ""))

    return evidences


def get_volume_page_score_for_input_fields(result_record, hypothesis):
    """

    :param result_record:
    :param hypothesis:
    :return:
    """
    input_fields = hypothesis.get_detail('input_fields')

    evidences = Evidences()

    # references can eliminate volume and include only page, or only volume can be included
    # parser can not differentiate between if only page was included or only volume,
    # so if there is only one value, do a reverse engineering, see if the page and or volume in ads 
    # matches this one value, or if it can be matched in the ref_str
    exist = bool('volume' in input_fields) + bool('page' in input_fields)

    ads_volume = result_record.get('volume', '')
    ads_page = result_record.get('page', '')

    ref_str = input_fields.get('refstr', '')

    ref_volume = ref_page = None

    if exist == 0:
        # see if ads_volume is in the ref_str
        ref_volume = ads_volume if re.search(r'(\b%s)' % ads_volume, ref_str) else None
        # see if ads_page is in the ref_str
        ref_page = ads_page if re.search(r'(\b%s)' % ads_page, ref_str) else None
    elif exist == 1:
        if 'volume' in input_fields:
            if input_fields['volume'] == ads_page:
                ref_volume = ads_page
                # see if ads_volume is in the ref_str
                ref_page = ads_volume if re.search(r'(\b%s)' % ads_volume, ref_str) else None
            elif input_fields['volume'] == ads_volume:
                # volume matches, see if ads_page is in the ref_str
                ref_volume = ads_volume
                ref_page = ads_page if re.search(r'(\b%s)' % ads_page, ref_str) else None
            else:
                ref_volume = input_fields['volume']
        elif 'page' in input_fields:
            if input_fields['page'] == ads_volume:
                ref_page = ads_volume
                # see if ads_page is in the ref_str
                ref_volume = ads_page if re.search(r'(\b%s)' % ads_page, ref_str) else None
            elif input_fields['page'] == ads_page:
                # page matches, see if ads_volume is in the ref_str
                ref_page = ads_page
                ref_volume = ads_volume if re.search(r'(\b%s)' % ads_volume, ref_str) else None
            else:
                ref_page = input_fields['page']
    else: # == 2
        ref_page = input_fields['page']
        ref_volume = input_fields['volume']

    if ref_volume:
        add_volume_evidence(evidences,
                            ref_volume,
                            ads_volume,
                            result_record.get('issue'),
                            result_record.get('pub_raw'))
    if ref_page:
        add_page_evidence(evidences,
                          ref_page,
                          ads_page,
                          result_record.get('page_range', ''),
                          result_record.get('eid', None),
                          hypothesis.get_detail('page_qualifier'),
                          input_fields.get('refstr', ''))

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
    evidences = get_author_year_pub_score_for_input_fields(result_record, hypothesis)

    input_fields = hypothesis.get_detail('input_fields')

    if 'page' not in input_fields:
        ads_page = result_record.get('page', '')
        # reverse engineering, see if ads_page is in the ref_str
        # some xmls are unable to parse page out
        ref_page = ads_page if re.search(r'(\b%s)' % ads_page, input_fields('refstr', '')) else None
    else:
        ref_page = input_fields.get('page')
        ads_page = result_record.get('page', '')

    add_page_evidence(evidences,
        ref_page,
        ads_page,
        result_record.get('page_range', ''),
        result_record.get('eid', None),
        hypothesis.get_detail('page_qualifier'))

    add_title_evidence(evidences,
        input_fields.get('title'),
        result_record.get('title', ''))

    return evidences


def get_serial_score_for_input_fields(result_record, hypothesis):
    """
    returns Evidences for result_record matching hypothesis as a serial
    publication.

    :param result_record:
    :param hypothesis:
    :return:
    """
    evidences = get_author_year_pub_score_for_input_fields(result_record, hypothesis) + \
                get_volume_page_score_for_input_fields(result_record, hypothesis)

    input_fields = hypothesis.get_detail("input_fields")

    add_title_evidence(evidences,
        input_fields.get('title'),
        result_record.get('title', ''))

    return evidences


def get_book_score_for_input_fields(result_record, hypothesis):
    """
    returns Evidences for result_record matching hypothesis as a book.

    This means matching the pub against result_record's title field.

    :param result_record:
    :param hypothesis:
    :return:
    """
    evidences = get_author_year_score_for_input_fields(result_record, hypothesis)

    if result_record["doctype"] in ["book", "inbook", "techreport"]:
        evidences.add_evidence(current_app.config["EVIDENCE_SCORE_RANGE"][1], "doctype")
    else:
        evidences.add_evidence(current_app.config["EVIDENCE_SCORE_RANGE"][0], "doctype")

    input_fields = hypothesis.get_detail("input_fields")

    add_publication_evidence(evidences,
        input_fields.get("pub", ""),
        input_fields.get("bibstem", ""),
        input_fields.get("refstr", ""),
        result_record.get("title", ""),
        result_record.get("bibcode", ""),
        result_record.get("bibstem", ""))

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


def get_chapter_score_for_input_fields(result_record, hypothesis):
    """
    returns evidences based on author, year, volume and/or page, and publication or title,
    when solr record is a chapter in a proceeding or in a book it comes here

    :param result_record:
    :param hypothesis:
    :return:
    """
    evidences = get_author_year_score_for_input_fields(result_record, hypothesis) + \
                get_volume_page_score_for_input_fields(result_record, hypothesis)

    input_fields = hypothesis.get_detail("input_fields")

    # if comparing against inproceedigns record in solr, compare both pub and title
    # aginst both pub and title in solr
    # inproceedings reference string, depending on the publications, interchanges the order of title and journal
    # include the one with the highest score in the final score
    ref_pubs = [input_fields.get("pub", ""), input_fields.get("pub", ""),
                input_fields.get("title", ""), input_fields.get("title", "")]
    ads_pubs = [result_record.get("title", ""), result_record.get("pub_raw", ""),
                result_record.get("title", ""), result_record.get("pub_raw", "")]
    track_evidence = Evidences()
    for ref_pub, ads_pub in zip(ref_pubs, ads_pubs):
        tmp_evidence = Evidences()
        add_publication_evidence(tmp_evidence,
                                 ref_pub,
                                 input_fields.get("bibstem", ""),
                                 input_fields.get("refstr", ""),
                                 ads_pub,
                                 result_record.get("bibcode", ""),
                                 result_record.get("bibstem", ""))
        if tmp_evidence.get_score() > track_evidence.get_score():
            track_evidence = tmp_evidence
    evidences = evidences + track_evidence
    return evidences


def get_score_for_input_fields(result_record, hypothesis):
    """
    computes the score based on the solr record doctype

    :param result_record:
    :param hypothesis:
    :return:
    """
    if result_record["doctype"] in ["inproceedings", "inbook"]:
        return get_chapter_score_for_input_fields(result_record, hypothesis)
    if result_record["doctype"] == "book":
        return get_book_score_for_input_fields(result_record, hypothesis)
    if result_record["doctype"] == "catalog":
        return get_author_year_pub_score_for_input_fields(result_record, hypothesis)
    return get_serial_score_for_input_fields(result_record, hypothesis)


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
    elif input_fields.get("arxiv", "not in ref") == get_arxiv_id_or_ascl_id(result_record):
        evidences.add_evidence(current_app.config["EVIDENCE_SCORE_RANGE"][1], "bibcode")
    elif input_fields.get("ascl", "not in ref") == get_arxiv_id_or_ascl_id(result_record):
        evidences.add_evidence(current_app.config["EVIDENCE_SCORE_RANGE"][1], "bibcode")
    elif compare_bibcode(input_fields.get("bibcode", None), result_record.get("bibcode", None),
                         result_record.get("identifier", None)):
        evidences.add_evidence(current_app.config["EVIDENCE_SCORE_RANGE"][1], "bibcode")
    else:
        evidences.add_evidence(current_app.config["EVIDENCE_SCORE_RANGE"][0], "bibcode")

    return evidences


def get_arxiv_id_or_ascl_id(result_record):
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


def compare_bibcode(ref_bibcode, ads_bibcode, ads_identifiers):
    """
    compares bibcode built from reference string with the bibcode from solr,
    reference bibcode can also be an identifier, so compare against identifier too

    :param ref_bibcode:
    :param ads_bibcode:
    :param ads_identifiers:
    :return:
    """
    if ref_bibcode is None or ads_bibcode is None:
        return False

    ref_bibcode = ref_bibcode.upper()
    ads_bibcode = ads_bibcode.upper()

    if ref_bibcode == ads_bibcode:
        return True

    if ref_bibcode in [i.upper() for i in ads_identifiers]:
        return True

    return False
