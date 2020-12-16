"""
Code to normalize and otherwise manipulate author lists.
"""

import re
import editdistance
import unidecode

from flask import current_app

from referencesrv.resolver.common import Undecidable

# all author lists coming in need to be case-folded
# replaced van(?: der) with van|van der
SINGLE_NAME_RE = "(?:(?:d|de|de la|De|des|Des|in '[a-z]|van|van der|van den|van de|von|Mc|[A-Z]')[' ]?)?[A-Z][a-z]['A-Za-z]*"
LAST_NAME_PAT = re.compile(r"%s(?:[- ]%s)*" % (SINGLE_NAME_RE, SINGLE_NAME_RE))

ETAL = r"(([\s,]*and)?[\s,]*[Ee][Tt][.\s]*[Aa][Ll][.\s]+)?"
LAST_NAME_SUFFIX = r"([,\s]*[Jj][Rr][.,\s]+)?"

# This pattern should match author names with initials behind the last
# name
TRAILING_INIT_PAT = re.compile(r"(?P<last>%s%s)\s*,?\s+"
                               r"(?P<inits>(?:[A-Z]\.[\s-]*)+)" % (LAST_NAME_PAT.pattern, LAST_NAME_SUFFIX))
# This pattern should match author names with initals in front of the
# last name
LEADING_INIT_PAT = re.compile(r"(?P<inits>(?:[A-Z]\.[\s-]*)+) "
                              r"(?P<last>%s%s)\s*,?" % (LAST_NAME_PAT.pattern, LAST_NAME_SUFFIX))

EXTRAS_PAT = re.compile(r"\b\s*(and|et\.? al\.?|jr)\b", re.I)

REF_GLUE_RE = r"[,;]?(\s*(?:and|&))?\s+"
NAMED_GROUP_PAT = re.compile(r"\?P<\w+>")
LEADING_INIT_AUTHORS_PAT = re.compile("%s(%s%s)*%s"%(
    NAMED_GROUP_PAT.sub("?:", LEADING_INIT_PAT.pattern), REF_GLUE_RE,
    NAMED_GROUP_PAT.sub("?:", LEADING_INIT_PAT.pattern), ETAL))

TRAILING_INIT_AUTHORS_PAT = re.compile("%s(%s%s)*%s"%(
    NAMED_GROUP_PAT.sub("?:", TRAILING_INIT_PAT.pattern), REF_GLUE_RE,
    NAMED_GROUP_PAT.sub("?:", TRAILING_INIT_PAT.pattern), ETAL))

COLLABORATION_PAT = re.compile(r"(?P<collaboration>[(\[]*[A-Za-z\s\-\/]+\s[Cc]ollaboration[s]?\s*[A-Z\.]*[\s.,)\]]+)")
COLLEAGUES_PAT = re.compile(r"(?P<andcolleagues>and\s\d+\s(co-authors|colleagues))")

REFERENCE_LAST_NAME_EXTRACTOR = re.compile(r"(\w\w+\s*\w\w+\s*\w{0,1}\w+)")
SINGLE_WORD_EXTRACTOR = re.compile(r"\w+")

FIRST_CAPTIAL = re.compile(r"^([^A-Z0-9\"""]*[A-Z])")

# when first name is spelled out
FIRST_NAME_PAT = r"[A-Z][a-z][A-Za-z]*(\-[A-Z][a-z][A-Za-z]*)?"
FULLNAME_PAT = re.compile(r"(?P<first>%s\s*(?:[A-Z]\.[\s-]*)?)?"
                          r"(?P<last>%s%s),?" %(FIRST_NAME_PAT, LAST_NAME_PAT.pattern, LAST_NAME_SUFFIX))
FULLNAME_AUTHORS_PAT = re.compile("%s(%s%s)*(%s)?"%(
    NAMED_GROUP_PAT.sub("?:", FULLNAME_PAT.pattern), REF_GLUE_RE,
    NAMED_GROUP_PAT.sub("?:", FULLNAME_PAT.pattern), ETAL))

REMOVE_AND = re.compile(r"(,?\s+and\s+)", re.IGNORECASE)
COMMA_BEFORE_AND = re.compile(r"(,)?(\s+and)", re.IGNORECASE)

CROP_IF_NEEDED = re.compile(r"((^(?!and|&).*(and|&)(?!,).*),)|((^(?!and|&).*(and|&)(?!,).*)$)|((^(?!,).*),)")

ETAL_HOOK = re.compile(r"(.* et\.? al\.?)\b", re.I)
AND_HOOK = re.compile(r"(.+?(?=\b[Aa]nd|\s&)(\b[Aa]nd|\s&)(%s%s\s*,?\s+(?:[A-Z]\.[\s-]*)+)|((?:[A-Z]\.[\s-]*)+ %s%s\s*,?))[,\d]+"%(LAST_NAME_PAT.pattern, LAST_NAME_SUFFIX, LAST_NAME_PAT.pattern, LAST_NAME_SUFFIX))

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
    collaborators_idx, collaborators_len = get_collaborators(ref_string)

    # if collaborator is listed before authors
    if collaborators_idx != 0:
        n_trailing = len(TRAILING_INIT_PAT.findall(ref_string[collaborators_len:]))
        n_leading = len(LEADING_INIT_PAT.findall(ref_string[collaborators_len:]))
    else:
        n_trailing = len(TRAILING_INIT_PAT.findall(ref_string))
        n_leading = len(LEADING_INIT_PAT.findall(ref_string))

    if n_leading == n_trailing:
        raise Undecidable('Both leading and trailing found without a majority')
    if n_trailing > n_leading:
        return TRAILING_INIT_PAT
    else:
        return LEADING_INIT_PAT


def get_authors_recursive(ref_string, start_idx, author_pat):
    """
    if there is a comma missing between the authors, or there is a out of place character,
    (ie, P. Bosetti, N. Brand t, M. Caleno, ...) RE gets confused,
    once substring is identified as author, continue on with the rest of ref_string
    to make sure all the authors are identified

    :param ref_string:
    :param start_idx:
    :param author_pat:
    :return:
    """
    author_len = 0
    while True:
        if author_len > 0:
            first_capital = FIRST_CAPTIAL.match(ref_string[start_idx+author_len:])
            if first_capital:
                author_len += len(first_capital.group()) - 1
        author_match = author_pat.match(ref_string[start_idx+author_len:])
        if author_match:
            author_len += len(author_match.group())
        else:
            break

    return author_len


def get_authors_fullnames(ref_string):
    """
    if first name is not initial

    :param ref_string:
    :return:
    """
    try:
        author_match = FULLNAME_AUTHORS_PAT.match(ref_string)
        if author_match:
            return len(author_match.group())
    except:
        pass
    return 0


def get_authors_last_attempt(ref_string):
    """
    last attempt to identify author(s)

    :param ref_string:
    :return:
    """
    # if there is an and, used that as an anchor
    match = AND_HOOK.match(ref_string)
    if match:
        return match.group(1).strip()
    # grab first author's lastname and include etal
    match = LAST_NAME_PAT.search(ref_string)
    if match:
        return match.group().strip()
    return None


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
    # not if collaborators_idx is not zero, it means this is listed after author list
    # that would signal the end of author
    collaborators_idx, collaborators_len = get_collaborators(ref_string)
    # if there is a xxx colleagues or xxx co-authors
    # that would signal the end of author
    and_colleagues_idx, and_colleagues_len = get_and_colleagues(ref_string)

    if and_colleagues_len > 0:
        authors_len = and_colleagues_idx + and_colleagues_len
    elif collaborators_idx > 0:
        authors_len = collaborators_idx + collaborators_len
    else:
        # if there is et al, grab everything before it and do not bother with
        # deciding what format it is
        match = ETAL_HOOK.match(ref_string)
        if match:
            authors_len = len(match.group().strip())
        else:
            lead_len = get_authors_recursive(ref_string, collaborators_len, LEADING_INIT_AUTHORS_PAT)
            trail_len = get_authors_recursive(ref_string, collaborators_len, TRAILING_INIT_AUTHORS_PAT)
            full_len = get_authors_fullnames(ref_string[collaborators_len:])
            authors_len = max(full_len, max(lead_len, trail_len)) + collaborators_len + and_colleagues_len
        if authors_len < 3:
            # the last attempt
            authors = get_authors_last_attempt(ref_string)
            if not authors:
                raise Undecidable("No discernible authors in '%s'"%ref_string)
            return authors
        # might have gone too far if initials are leading
        if authors_len == lead_len and authors_len >= 3:
            # if needs pruning, for example cases like
            # T.A. Heim, J. Hinze and A. R. P. Rau, J. Phys. A: Math. Theor. 42, 175203 (2009). or
            # S.K. Suslov, J. Phys. B: At. Mol. Opt. Phys. 42, 185003 (2009).
            # that captures `J. Phys` as part of author
            author_match = CROP_IF_NEEDED.search(ref_string[:authors_len])
            if author_match:
                if author_match.group(4):
                    authors_len = len(author_match.group(4))
                elif author_match.group(2):
                    authors_len = len(author_match.group(2))
                elif author_match.group(8):
                    authors_len = len(author_match.group(8))
    authors = ref_string[:authors_len].strip().strip(',')
    return authors


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

    return lead_match.group().strip(',') if lead_len > trail_len else trail_match.group().strip(',') if lead_len < trail_len else None


def get_collaborators(ref_string):
    """
    collabrators are listed at the beginning of the author list,
    return the length, if there are any collaborators listed

    :param ref_string:
    :return:
    """
    match = COLLABORATION_PAT.findall(COMMA_BEFORE_AND.sub(',\2', ref_string))
    if len(match) > 0:
        collaboration = match[-1]
        return ref_string.find(collaboration), len(collaboration)

    return 0, 0


def get_and_colleagues(ref_string):
    """

    :param ref_string:
    :return:
    """
    match = COLLEAGUES_PAT.search(ref_string)
    if match:
        andcolleagues = match.group('andcolleagues')
        return ref_string.find(andcolleagues), len(andcolleagues)

    return 0, 0


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


def normalize_author_list(author_string, initials=True):
    """
    tries to bring author_string in the form AuthorLast1; AuthorLast2

    If the function cannot make sense of author_string, it returns it unchanged.

    :param author_string:
    :param initials:
    :return:
    """
    author_string = REMOVE_AND.sub(',', author_string)
    try:
        pat = get_author_pattern(author_string)
        if initials:
            return "; ".join("%s, %s" % (match.group("last"), match.group("inits"))
                             for match in pat.finditer(author_string)).strip()
        else:
            return "; ".join("%s" % (match.group("last"))
                             for match in pat.finditer(author_string)).strip()
    except Undecidable:
        try:
            # is first name spelled out
            if get_authors_fullnames(author_string) > 0:
                if get_authors_fullnames(author_string) > 0:
                    return "; ".join("%s, %s" % (match.group("last"), match.group("first")[0])
                                     for match in FULLNAME_PAT.finditer(author_string)).strip()
            return author_string
        except:
            try:
                # one last effort, grab the first lastname
                return FULLNAME_PAT.search(author_string).group("last")
            except:
                pass
    return ""


def get_first_author(author_string, initials=False):
    """
    returns the last name of the first author in author_string.

    If that's not possible for some reason, common.Undecidable is raised.

    :param author_string:
    :param initials:
    :return:
    """
    pat = get_author_pattern(author_string)
    match = pat.search(author_string)
    if initials:
        return "%s, %s" % (match.group("last"), match.group("inits"))
    else:
        return match.group("last")


def get_first_author_last_name(author_string):
    """
    returns the last name of the first author of one of our normalised author strings.

    :param authors:
    :return:
    """
    if author_string:
        parts = author_string.split(';')
        if parts:
            return parts[0].split(",")[0]
    return None


def get_author_last_name_only(author_string):
    """

    :param author_string:
    :return:
    """
    try:
        get_author_pattern(author_string)
        return [lastname.lower().replace('-', ' ') for lastname in LAST_NAME_PAT.findall(author_string)]
    except Undecidable:
        # we are here since we have full first names, hence return every other matches
        return [single_name.lower() for name in LAST_NAME_PAT.findall(author_string) for single_name in name.split()][1::2]


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
    ads_authors_lastname = [a.split(',')[0].strip().lower().replace('-', ' ')
                            for a in ads_authors]

    ref_authors_lastname = get_author_last_name_only(ref_authors)
    ref_authors = EXTRAS_PAT.sub('', ref_authors.lower().replace('.', ' '))

    if ads_first_author is None:
        ads_first_author = ads_authors_lastname[0]
    first_author_missing = ads_first_author.lower() not in ref_authors
    if first_author_missing and " " in ads_first_author:
        first_author_missing = ads_first_author.split()[-1] not in ref_authors

    different = []
    for ads_auth in ads_authors_lastname:
        if ads_auth in ref_authors or (" " in ads_auth and ads_auth.split()[-1] in ref_authors):
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

