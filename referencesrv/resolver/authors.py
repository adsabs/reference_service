"""
Code to normalize and otherwise manipulate author lists.
"""

import re
import editdistance
import unidecode

from flask import current_app

from referencesrv.resolver.common import Undecidable

ETAL_PAT = re.compile(r"(?i)[\s,]*et\.?\s*al\.?")
# all author lists coming in need to be case-folded
# replaced van(?: der) with van|van der
SINGLE_NAME_RE = "(?:(?:d|de|De|des|Des|in '[a-z]|van|van der|van den|von|Mc|[A-Z]')[' ]?)?[A-Z][a-z][A-Za-z]*"
LAST_NAME_PAT = re.compile(r"%s(?:[- ]%s)*" % (SINGLE_NAME_RE, SINGLE_NAME_RE))

LAST_NAME_SUFFIX = r"([,\s]*[Jj]r[.]*)?"

# This pattern should match author names with initials behind the last
# name
TRAILING_INIT_PAT = re.compile(r"(?P<last>%s)\s*,?\s+"
                               r"(?P<inits>(?:[A-Z]\.[\s-]*)+%s)" % (LAST_NAME_PAT.pattern, LAST_NAME_SUFFIX))
# This pattern should match author names with initals in front of the
# last name
LEADING_INIT_PAT = re.compile(r"(?P<inits>(?:[A-Z]\.[\s-]*)+%s) "
                              r"(?P<last>%s),?" % (LAST_NAME_SUFFIX, LAST_NAME_PAT.pattern))

EXTRAS_PAT = re.compile('\\b\s*(and|et al|ed|jr)\\b', re.I)

REF_GLUE_RE = r"[,;]?(\s*(?:and|&))?\s+"
NAMED_GROUP_PAT = re.compile(r"\?P<\w+>")
LEADING_INIT_AUTHORS_PAT = re.compile("%s(%s%s)*(%s)?"%(
    NAMED_GROUP_PAT.sub("?:", LEADING_INIT_PAT.pattern), REF_GLUE_RE,
    NAMED_GROUP_PAT.sub("?:", LEADING_INIT_PAT.pattern), ETAL_PAT.pattern))

TRAILING_INIT_AUTHORS_PAT = re.compile("%s(%s%s)*(%s)?"%(
    NAMED_GROUP_PAT.sub("?:", TRAILING_INIT_PAT.pattern), REF_GLUE_RE,
    NAMED_GROUP_PAT.sub("?:", TRAILING_INIT_PAT.pattern), ETAL_PAT.pattern))

COLLABORATION_PAT = re.compile(r"(?P<collaboration>[A-Za-z\s\-]*Collaboration,)")
COLLEAGUES_PAT = re.compile(r"(?P<andcolleagues>and\s\d+\s(co-authors|colleagues))")

REFERENCE_LAST_NAME_EXTRACTOR = re.compile(r"(\w\w+\s*\w\w+\s*\w{0,1}\w+)")
SINGLE_WORD_EXTRACTOR = re.compile(r"\w+")

def get_author_pattern(ref_string):
    """
    returns a pattern matching authors in ref_string.

    The problem here is that initials may be leading or trailing.
    The function looks for patterns pointing on one or the other direction;
    if unsure, an Undecidable exception is raised.

    :param ref_string:
    :return:
    """
    # if there is a collaboration included in the list of authors
    # remove that to be able to decide if the author list is trailing or ending
    collaborators_len = get_collabration_length(ref_string)

    n_trailing = len(TRAILING_INIT_PAT.findall(ref_string[collaborators_len:]))
    n_leading = len(LEADING_INIT_PAT.findall(ref_string[collaborators_len:]))
    if n_leading == n_trailing:
        raise Undecidable('Both leading and trailing found without a majority')
    if n_trailing > n_leading:
        return TRAILING_INIT_PAT
    else:
        return LEADING_INIT_PAT

def get_authors_recursive(ref_string, start_idx, author_pat):
    """
    if there is a comma missing between the authors, RE gets confused,
    once substring is identified as author, continue on with the rest of ref_string
    to make sure all the authors are identified

    :param ref_string:
    :param start_idx:
    :param author_pat:
    :return:
    """
    author_len = 0
    while True:
        author_match = author_pat.match(ref_string[start_idx+author_len:])
        if author_match:
            author_len += len(author_match.group())
        else:
            break
        author_len += len(ref_string) - len(ref_string.lstrip())
    return author_len

def get_authors(ref_string):
    """
    returns something what should be the authors in ref_string, assuming
    the reference starts with them and they don't have spelled out first names.

    This works by returning the longest match of either leading or trailing
    authors starting at the beginning of ref_string.

    :param ref_string:
    :return:
    """
    if isinstance(ref_string, unicode):
        ref_string = unidecode.unidecode(ref_string)

    # if there are any collaborator(s) listed in the reference
    # remove them to be able to decide if the author list is trailing or ending
    collaborators_len = get_collabration_length(ref_string)

    # if there is a xxx colleagues or xxx co-authors
    # that would signal the end of author
    and_colleagues = get_and_colleagues(ref_string)
    if len(and_colleagues) > 0:
        authors_len = ref_string.find(and_colleagues) + len(and_colleagues)
    else:
        lead_len = get_authors_recursive(ref_string, collaborators_len, LEADING_INIT_AUTHORS_PAT)
        trail_len = get_authors_recursive(ref_string, collaborators_len, TRAILING_INIT_AUTHORS_PAT)

        authors_len = max(lead_len, trail_len) + len(and_colleagues)
        if authors_len < 3:
            raise Undecidable("No discernible authors in '%s'"%ref_string)

    return ref_string[:collaborators_len+authors_len]


def get_editors(ref_string):
    """
    returns list of editors, which can appear anywhere in the reference

    :param ref_string:
    :return:
    """
    if isinstance(ref_string, unicode):
        ref_string = unidecode.unidecode(ref_string)

    lead_match = LEADING_INIT_AUTHORS_PAT.search(ref_string)
    trail_match = TRAILING_INIT_AUTHORS_PAT.search(ref_string)
    lead_len = trail_len = 0

    if lead_match:
        lead_len = len(lead_match.group())
    if trail_match:
        trail_len = len(trail_match.group())

    return lead_match.group() if lead_len > trail_len else trail_match.group() if lead_len < trail_len else None

def get_collabration_length(ref_string):
    """
    collabrators are listed at the beginning of the author list,
    return the length, if there are any collaborators listed

    :param ref_string:
    :return:
    """
    match = COLLABORATION_PAT.match(ref_string)
    if match:
        return len(match.group('collaboration'))

    return 0


def get_and_colleagues(ref_string):
    """

    :param ref_string:
    :return:
    """
    match = COLLEAGUES_PAT.search(ref_string)
    if match:
        return match.group('andcolleagues')

    return ''


def normalize_single_author(author_string):
    """
    returns a normalized form for a single author string.

    As this is for processing author strings coming from ADS,
    we do not touch initials or similar.  This is just so ADS
    authors are at the same normalization level as what happens
    in normalize_author_list.

    :param author_string:
    :return:
    """
    return unidecode.unidecode(author_string).replace("-", " ").lower()


def normalize_author_list(authorString, initials=True):
    """
    tries to bring authorString in the form AuthorLast1; AuthorLast2

    If the function cannot make sense of authorString, it returns it unchanged.

    :param authorString:
    :param initials:
    :return:
    """
    try:
        pat = get_author_pattern(authorString)
    except Undecidable:
        return authorString

    if initials:
        return "; ".join("%s, %s" % (mat.group("last"), mat.group("inits"))
                         for mat in pat.finditer(authorString)).strip()
    else:
        return "; ".join("%s" % (mat.group("last"))
                         for mat in pat.finditer(authorString)).strip()


def get_first_author(authorString, initials=False):
    """
    returns the last name of the first author in authorString.

    If that's not possible for some reason, common.Undecidable is raised.

    :param authorString:
    :param initials:
    :return:
    """
    pat = get_author_pattern(authorString)
    mat = pat.search(authorString)
    if initials:
        return "%s, %s" % (mat.group("last"), mat.group("inits"))
    else:
        return mat.group("last")


def get_first_author_last_name(authorString):
    """
    returns the last name of the first author of one of our normalised author strings.

    :param authors:
    :return:
    """
    if authorString:
        parts = authorString.split(';')
        if parts:
            return parts[0].split(",")[0]
    return None

def count_matching_authors(ref_authors, ads_authors, ads_first_author=None):
    """
    returns statistics on the authors matching between ref_authors
    and ads_authors.

    ads_authors is supposed to a list of ADS-normalized author strings.
    ref_authors must be a string, where we try to assume as little as
    possible about the format.  Full first names will kill this function,
    though.

    What's returned is a tuple of (missing_in_ref,
        missing_in_ads, matching_authors, first_author_missing).

    No initials verification takes place here, case is folded, everything
    is supposed to have been dumbed down to ASCII by ADS conventions.

    :param ref_authors:
    :param ads_authors:
    :param ads_first_author:
    :return:
    """
    if not ads_authors:
        raise NotImplementedError("ADS paper without authors -- what should we do?")

    matching_authors, missing_in_ref, first_author_missing = 0, 0, False

    # clean up ADS authors to only contain surnames and be lowercased
    # golnaz: remove the punctuations,
    # also if there is etal or and or ed (editor) in ref_authors remove them too
    ads_authors_lastname = [a.split(',')[0].strip().lower().replace('-', ' ')
                            for a in ads_authors]

    ref_authors = EXTRAS_PAT.sub('', ref_authors.lower().replace('.', ' ').replace('-', ' '))
    ref_authors_lastname = REFERENCE_LAST_NAME_EXTRACTOR.findall(ref_authors)

    if ads_first_author is None:
        ads_first_author = ads_authors_lastname[0]
    first_author_missing = ads_first_author.lower() not in ref_authors
    if first_author_missing and " " in ads_first_author:
        first_author_missing = ads_first_author.split()[-1] not in ref_authors

    different = []
    for ads_auth in ads_authors_lastname:
        if ads_auth in ref_authors or (
                        " " in ads_auth and ads_auth.split()[-1] in ref_authors):
            matching_authors += 1
        else:
            # see if there is actually no match (check for misspelling here)
            # difference of <30% is indication of misspelling
            misspelled = False
            for ref_auth in ref_authors_lastname:
                N_max = max(len(ads_auth), len(ref_auth))
                distance = (N_max - float(editdistance.eval(ads_auth, ref_auth))) / N_max
                if distance > 0.7:
                    different.append(ref_auth)
                    misspelled = True
                    break
            if not misspelled:
                missing_in_ref += 1

    # Now try to figure out if the reference has additional authors
    # (we assume ADS author lists are complete)
    ads_authors_lastname_pattern = "|".join(ads_authors_lastname)

    # just to be on the safe side, nuke some RE characters that sometimes
    # sneak into ADS author lists (really, the respective records should
    # be fixed)
    ads_authors_lastname_pattern = re.sub("[()]", "", ads_authors_lastname_pattern)

    wordsNotInADS = SINGLE_WORD_EXTRACTOR.findall(re.sub(ads_authors_lastname_pattern, "", '; '.join(ref_authors_lastname)))
    # remove recognized misspelled authors
    wordsNotInADS = [word for word in wordsNotInADS if word not in different]
    missing_in_ads = len(wordsNotInADS)

    return (missing_in_ref, missing_in_ads, matching_authors, first_author_missing)


def add_author_evidence(evidences, ref_authors, ads_authors, ads_first_author, has_etal=False):
    """
    adds an evidence for ref_authors matching ads_authors.

    This is for the fielded case, where there's actually a field
    ref_authors.

    The evidence is basically the number of matching authors over
    the number of ADS authors, except when has_etal is True, in
    which case the denominator is the number of reference authors.

    :param evidences:
    :param ref_authors:
    :param ads_authors:
    :param ads_first_author:
    :param has_etal:
    :return:
    """
    # note that ref_authors is a string, and we need to have at least one name to match it to
    # ads_authors with is a list, that should contain at least one name
    if len(ref_authors) == 0 or len(ads_authors) == 0:
        return
    (missing_in_ref, missing_in_ads, matching_authors, first_author_missing
     ) = count_matching_authors(ref_authors, ads_authors, ads_first_author)

    if has_etal:
        normalizer = float(matching_authors + missing_in_ads)
    else:
        normalizer = float(len(ads_authors))

    # if the first author is missing, apply the factor by which matching authors are discounted
    if first_author_missing:
        matching_authors *= current_app.config['MISSING_FIRST_AUTHOR_FACTOR']

    if normalizer != 0:
        score = (matching_authors - missing_in_ads) / normalizer
    else:
        score = 0

    evidences.add_evidence(max(current_app.config['EVIDENCE_SCORE_RANGE'][0], min(current_app.config['EVIDENCE_SCORE_RANGE'][1], score)), "authors")
