"""
Operations on stuff that was in the journal field and at related
locations.

This module also contains functions tailored to compare things like
volumes and pages.  For those, it's a demerit if either reference or
ADS gives a field (i.e., not None or empty string) while the other does.
"""

import re
import editdistance
import unidecode
import math

from flask import current_app

from referencesrv.resolver.common import SOURCE_MATCHER, round_two_significant_digits


# A string containing all "modifiers" to page numbers from
# letters, "pink pages", and the like.
LETTER_CHARS = "ALPSe"
POSTPAGE_CHARS = "BHPL"
# ADS page numbers can be "normal" pages (including "letter"-like
# indicators, P, L, A), possibly with ranges, or they can be
# more or less random identifiers.  I'm saying they are pages if they
# match the following pattern:
ADS_NUMERIC_PAGE_PATTERN = re.compile("(?P<lchar>[%s])?(?P<pageno>\d+\.?\d*)(?P<postchar>[%s])?(?:-[%s]?\d+[%s]?)?"
                                      %(LETTER_CHARS, POSTPAGE_CHARS, LETTER_CHARS, POSTPAGE_CHARS))

YEAR_PATTERN = re.compile(r'^([12][089]\d\d)')

def get_best_bibstem_for(sourceSpec):
    """
    returns a "unique" bibstem that could match for sourceName.

    If we cannot come up with anything, this raises a KeyError
    
    :param sourceSpec: 
    :return: 
    """
    current_app.logger.debug("sourceSpec=%s"%(sourceSpec))
    try:
        return SOURCE_MATCHER.bestmatches(sourceSpec.upper(), 1)[0][1].strip('.')
    except IndexError:
        raise KeyError(sourceSpec)


def get_exact_bibstem_for(sourceSpec):
    """
    returns a "unique" bibstem that could match for sourceName.

    If we cannot come up with anything, this raises a KeyError

    :param sourceSpec:
    :return:
    """
    current_app.logger.debug("sourceSpec=%s" % (sourceSpec))
    try:
        return SOURCE_MATCHER.exactmatch(sourceSpec.upper())
    except IndexError:
        raise KeyError(sourceSpec)


def get_bibstem(stem):
    """
    checks to see if bibstem stem exist.

    :param sourceSpec:
    :return:
    """
    current_app.logger.debug("stem=%s" % (stem))
    bibstem = SOURCE_MATCHER.has_key(stem.upper())
    if bibstem:
        return bibstem[0].strip('.')
    return None


def add_volume_evidence(evidences, ref_volume, ads_volume, ads_issue):
    """
    adds evidence from comparing volume specifications from
    the reference and from ADS.
    
    :param evidences: 
    :param ref_volume: 
    :param ads_volume: 
    :param ads_issue:
    :return:
    """
    if not ref_volume and not (ads_volume or ads_issue):
        return

    nonzeros = [a for a in [ref_volume, ads_volume] if a]
    if len(nonzeros)==1:
        # one of the two has no volume, while the other does 
        # -- that's a bad sign
        evidences.add_evidence(current_app.config['EVIDENCE_SCORE_RANGE'][0], 'volume')
        return

    try:
        if int(ref_volume) == int(ads_volume):
            score = current_app.config['EVIDENCE_SCORE_RANGE'][1]
        # sometimes ads_volume holds conference year, and references include the issue
        # see if ads_volume is a year, if so then check the reference against issue
        elif ads_issue and YEAR_PATTERN.findall(ads_volume) and int(ref_volume)==int(ads_issue):
            score = current_app.config['EVIDENCE_SCORE_RANGE'][1]
        else:
            delta_volume = compute_closeness_two_numbers(ref_volume, ads_volume)
            delta_issue = compute_closeness_two_numbers(ref_volume, ads_issue) if ads_issue and YEAR_PATTERN.findall(ads_volume) else 0
            score = current_app.config['EVIDENCE_SCORE_RANGE'][1] * max(delta_volume, delta_issue)
    except ValueError:
        # Some weird format, so use edit distance
        score = string_similarity(ref_volume, ads_volume)

    evidences.add_evidence(score, 'volume')
    return


def is_page_number(page_spec):
    """

    :param page_spec:
    :return:
    """
    mat = ADS_NUMERIC_PAGE_PATTERN.match(page_spec)
    if mat:
        return mat.group('lchar') is not None
    return False

def clean_ads_page(page_spec):
    """
    returns the numeric content of an ADS page specification.

    This means only the first page of a page range is retained, and
    all "qualifiers" are removed.

    If page_spec is something that doesn't look like something talking
    about normal pages (e.g., AAS numbers or electronic identifiers)
    it is returned unchanged.

    :param page_spec:
    :return:
    """
    mat = ADS_NUMERIC_PAGE_PATTERN.match(page_spec)
    if mat:
        return mat.group('pageno')
    return page_spec


def compute_closeness_two_numbers(num1, num2):
    """

    :param num1:
    :param num2:
    :return:
    """
    diff = abs(int(num1) - int(num2))

    # perhaps marginal: it catches single-digit
    # typos in longer numbers, though...
    if diff % 10 == 0:
        # if only one digit is different
        if len(num1) == len(num2) and sum(a!=b for a, b in zip(num1, num2)) == 1:
            return round_two_significant_digits((len(num1) - 1.0) / len(num1))
        return 0.5
    elif int(num2) == 0:
        return 0
    else:
        closeness = 0.03 - diff / float(int(num2))
        return round_two_significant_digits(closeness * 10) if closeness > 0 else 0


def compute_page_delta_plain_number(ref_page, ads_match, ref_qualifier):
    """
    helps compute_page_delta for actual numeric page numbers.

    :param ref_page:
    :param ads_match:
    :param ref_qualifier:
    :return:
    """
    delta = 0
    ads_letter, ads_page = ads_match.group('lchar'), ads_match.group('pageno')
    if ads_match.group('postchar'):
        ads_letter = ads_match.group('postchar')

    if ref_qualifier is None:
        mat = ADS_NUMERIC_PAGE_PATTERN.match(ref_page)
        if mat:
            ref_qualifier, ref_page = mat.group('lchar'), mat.group('pageno')

    # this is mostly for AAS references
    ref_page = ref_page.replace(".", "")

    if int(ads_page)==int(ref_page):
        delta += current_app.config['EVIDENCE_SCORE_RANGE'][1]
        if ads_letter or ref_qualifier:
            if ads_letter!=ref_qualifier:
                delta += current_app.config['NO_LETTER_DEMERIT']
    else:
        return compute_closeness_two_numbers(ref_page, ads_page)

    return delta


def compute_page_delta(ref_page, ads_page, ref_qualifier=None):
    """
    returns a confidence delta between page specifications from
    the reference and from ADS.

    :param ref_page:
    :param ads_page:
    :param ref_qualifier:
    :return:
    """
    nonzeros = [a for a in [ref_page, ads_page] if a]
    if len(nonzeros)==1:
        return 0
    if len(nonzeros)==0:
        return None

    try:
        mat = ADS_NUMERIC_PAGE_PATTERN.match(ads_page)
        if not mat:
            raise ValueError('ADS page in bad format')
        delta = compute_page_delta_plain_number(ref_page, mat, ref_qualifier)
    except ValueError:
        # it's some weird identifier.  String identity should do for the moment.
        if ads_page==ref_page:
            delta = current_app.config['EVIDENCE_SCORE_RANGE'][1]
        else:
            return 0

    return delta


def add_page_evidence(evidences, ref_page, ads_page, ads_page_range="", ref_qualifier=None):
    """
    adds evidence from comparing reference and ADS page specs.

    See compute_page_delta for what's going on, this is just a thin
    wrapper.

    :param evidences:
    :param ref_page:
    :param ads_page:
    :param ads_page_range:
    :param ref_qualifier:
    :return:
    """
    if not ref_page and (not (ads_page or ads_page_range) or ads_page == '0'):
        return
    # if reference is a page range compare to ads_page range
    if isinstance(ref_page, basestring) and '-' in ref_page:
        delta = compute_page_delta(ref_page, ads_page_range, ref_qualifier)
    else:
        delta = compute_page_delta(ref_page, ads_page, ref_qualifier)
    if delta is not None:
        evidences.add_evidence(delta, 'page')


def number_similarity(num1,num2):
    """

    :param num1:
    :param num2:
    :return:
    """
    count = 0
    for x, y in zip(str(num1), str(num2)):
        if x == y:
            count = count + 1
    total = max(len(str(num1)), len(str(num1)))
    return count/float(total)


def add_year_evidence(evidences, ref_year, ads_year):
    """
    adds evidence from comparing publication years.

    :param evidences:
    :param ref_year:
    :param ads_year:
    :return:
    """
# This is here since it's perfectly possible that year is not part of
# the query.
#     if int(ref_year)==int(ads_year):
#         evidences.add_evidence(1, "year")
#     elif abs(int(ref_year)-int(ads_year))<2:
#         # that's pretty common, in particular with conferences
#         evidences.add_evidence(0.2, "year")
#     elif abs(int(ref_year)-int(ads_year))<3:
#         # this is not unusual when refereeing processes took a while
#         evidences.add_evidence(-0.2, "year")
#     elif abs(int(ref_year)-int(ads_year))<4:
#         # this is a bit extreme but we still don't want to veto
#         evidences.add_evidence(-0.7, "year")
#     else:
#         evidences.add_evidence(-1, "year")

    # new way of sccoring!
    evidences.add_evidence(number_similarity(ref_year, ads_year), "year")


def compute_pubstring_statistics(ref_pub, ads_pub, suggested_bibcode):
    """
    returns a tuple (total_ref_words, missing_ref_words).

    A word from ref_pub is accounted for it's position found in ads_pub
    or anywhere in the bibcode.

    :param ref_pub:
    :param ads_pub:
    :param suggested_bibcode:
    :return:
    """
    ref_pub = cook_reference_pub(ref_pub).lower()
    ads_pub = cook_reference_pub(ads_pub.lower()+' '+suggested_bibcode.lower())

    missing_words = 0
    ref_words = re.findall("\w\w+", ref_pub or "")

    for ref_word in ref_words:
        if ref_word not in ads_pub:
            missing_words += 1

    return len(ref_words), missing_words


def string_similarity(value_a, value_b):
    """
    Relative similarity of two strings, based on edit distance.

    :param value_a:
    :param value_b:
    :return:
    """
    if value_a is None or value_b is None:
        return current_app.config['EVIDENCE_SCORE_RANGE'][0]
    N_max = max(len(value_a), len(value_b))
    if N_max == 0:
        return current_app.config['EVIDENCE_SCORE_RANGE'][0]
    return (N_max - float(editdistance.eval(value_a, value_b)))/N_max


def add_publication_evidence(evidences, ref_pub, ref_bibstem, ads_pub, ads_bibcode, ads_bibstem):
    """
    adds evidence from comparing the publication string within the
    reference with ADS' one and the suspected bibcode.

    This is a particularly murky area.  Basically, we stipulate that ads_pub
    is a superset of ref_pub (i.e., it's ok if ads words don't appear in
    ref_pub), but any word in ref_pub not accounted for in ads_pub (allowing
    for abbreviations) or ads_bibcode is a demerit.

    :param evidences:
    :param ref_pub:
    :param ref_bibstem:
    :param ads_pub:
    :param ads_bibcode:
    :return:
    """
    if ref_bibstem and len(ref_bibstem)>1 and (ref_bibstem in ads_bibcode) or \
                            ref_pub and len(ref_pub)>1 and (ads_bibstem in ref_pub):
        evidences.add_evidence(current_app.config['EVIDENCE_SCORE_RANGE'][1], 'pub')
        return

    nonzeros = [a for a in [ref_pub, ads_pub] if a]
    if len(nonzeros) == 0 or not ref_pub:
        return
    if len(nonzeros) == 1:
        evidences.add_evidence(current_app.config['EVIDENCE_SCORE_RANGE'][0], 'pub')
        return

    total_ref_words, missing_ref_words = compute_pubstring_statistics(ref_pub, ads_pub, ads_bibcode)
    if total_ref_words:
        evidences.add_evidence((total_ref_words-2*missing_ref_words)/float(total_ref_words), 'pubstring')


def has_word(haystack, needle):
    """
    returns whether needle is present in haystack as a word.

    :param haystack:
    :param needle:
    :return:
    """
    return re.search(r"\b%s\b"%re.escape(needle), haystack) is not None


def has_thesis_indicators(pub_string):
    """
    returns true if pub_string could point to some thesis.

    The words checked for here come from the thesisIndicatorWords config item.

    :param pub_string:
    :return:
    """
    stuff_to_match = unidecode.unidecode(pub_string).lower()
    for thesis_word in current_app.config['THESIS_INDICATOR_WORDS']:
        if thesis_word.endswith("*"):
            if thesis_word[:-1] in stuff_to_match:
                return True
        else:
            if has_word(stuff_to_match, thesis_word):
                return True
    return False


def cook_reference_pub(pub_string):
    """
    returns pub_string with common abbreviations expanded
    and stopwords removed.

    :param pub_string:
    :return:
    """
    expansion_mapping = current_app.config["JOURNAL_ABBREVIATION"]
    stop_words = re.compile("\b({})\b".format("|".join(current_app.config["REFERENCE_STOP_WORDS"])))
    elements = stop_words.sub(" ", pub_string).split()
    # we need embedded ampersands as "and" so we accept A&A as  word
    return " ".join(expansion_mapping.get(e, e) for e in elements).replace("&", "and")


def cook_title_string(title):
    """
    removes presumably boring words from title and pre-processes it
    for later matching.

    :param title:
    :return:
    """
    return " ".join(p
                    for p in re.sub(r"[^\w]+", " ",
                                    title).split()
                    if p not in current_app.config["REFERENCE_STOP_WORDS"]
                    and len(p) > 5)


def add_title_evidence(evidences, ref_title, ads_title):
    """
    adds evidence from comparing publication title.

    :param evidences:
    :param ref_title:
    :param ads_title:
    :return:
    """
    if not ref_title:
        return
    evidences.add_evidence(string_similarity(ref_title, ads_title), "title")
