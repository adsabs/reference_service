"""
Extra hypothesis generators (and verifiers) by individual publication types, given fields.
"""

import regex as re

from flask import current_app

from referencesrv.resolver.common import Evidences, Hypothesis
from referencesrv.resolver.scoring import get_basic_score_for_input_fields, get_serial_score_for_input_fields, \
    get_author_year_pub_score_for_input_fields
from referencesrv.resolver.authors import add_author_evidence, normalize_author_list


def change_dict(base, del_keys=(), **kwargs):
    """
    returns the dictionary base less del_keys and with all kwargs
    added.

    This is a convenience function for the hypotheses that often have
    to futz around with the criteria dicts.  base itself is unchanged.

    :param base:
    :param del_keys:
    :param kwargs:
    :return:
    """
    res = base.copy()
    for key in del_keys:
        if key in res:
            del res[key]
    res.update(kwargs)
    return res


def add_boolean_evidence(evidences, boolean, hint):
    """
    adds a 1-evidence with hint if boolean is true, -1 otherwise.

    :param evidences:
    :param boolean:
    :param hint:
    :return:
    """
    if boolean:
        evidences.add_evidence(current_app.config['EVIDENCE_SCORE_RANGE'][1], hint)
    else:
        evidences.add_evidence(current_app.config['EVIDENCE_SCORE_RANGE'][0], hint)


def get_score_for_baas_match(result_record, hypothesis):
    """
    scores a BAAS->DDA match.

    For these, volume and page are hidden deep inside pub_raw.

    We also expect an expected_bibstem detail in the hypothesis, mainly
    for robustness in case this gets used to score something else.

    :param result_record:
    :param hypothesis:
    :return:
    """
    evidences = Evidences()
    if not re.match(r'....%s'%hypothesis.get_detail('expected_bibstem'), result_record['bibcode']):
        evidences.add_evidence(current_app.config['EVIDENCE_SCORE_RANGE'][0], 'no DDA bibcode')
        return evidences

    input_fields = hypothesis.get_detail('input_fields')

    normalized_authors = hypothesis.get_detail('normalized_authors')
    if normalized_authors is None:
        normalized_authors = normalize_author_list(input_fields.get('author', ''))

    add_author_evidence(evidences,
        normalized_authors,
        result_record['author_norm'],
        result_record['first_author_norm'])

    add_boolean_evidence(evidences,
        'Vol. %s'%input_fields['volume'] in result_record['pub_raw'],
        'vol in pub_raw?')

    add_boolean_evidence(evidences,
        re.search(r'p\.\s*%s\b'%input_fields['page'], result_record['pub_raw']), 'page in pub_raw?')
    
    return evidences


def get_conf_series_indicators():
    """

    :return: REs to recognise within pub the bibstem
    """
    conf_series_indicators = {
        "IAUS": r"[\201'Il]( |\.)?\ ?A( |\.)?\ ?U( |\. )?\ ?Sym",
        "IAUCo": r"[\201'I] ?A ?U ?Co[li1]{2}",
        "AIPC": r"A(m)?\s*[lIi](nst)?\s*P(hys)?\s+(Co[on]f|Proc)",
        "ASPC": r"A(stro?n?)?\s*S(oc)?\s*P(ac)?\s*C(o[on]f)?",
        "SPIE": r"SPIE",
        "BSRSL": r"BSRSL",
        "LPSC": r"Lun(ar)?\.?\s+(Planet(ary)?\.?)?\s+(Sci(ence)?\.?)?\s+Conf|LPSC?\s+[IVXLCDM0-9]+",
        "LPI": r"Lunar\s+(Planet(ary)?\.?)?\s+(Sci(ence)?\.?)?\s+[iIvVxXlLcCdDmM]+",
        "LPICo": r"LPI\s+Contrib",
        "ESASP": r"ESA\sS(pec(ial)?)?\.?\s*P(ubl(ication)?s?)?\.?",
        "LNP": r"Lect(ure)?\.?\s+Not(es)?\.?\s+(in)?\s*Phys(ics)?\.?",
        "SAAS": r"Saas[\s-]?Fee",
        "ASSL": r"Astrophys(ics|\.)?\s+(and\s+)?Space\s+Sci(ence|\.)?\s+Lib(rary|\.)?"
    }
    return [(re.compile(pat), stem) for stem, pat in conf_series_indicators.items()]


def iter_journal_specific_hypotheses(bibstem, year, author, journal, volume, page, full_reference):
    """
    iterates over hypotheses for some special publication types.

    These are tried for both (sufficiently described) fielded and unfielded
    references.

    These should be fairly specific (i.e., only be generated for
    narrowly defined publications), as, in particular for text references,
    they could otherwise generate many, many queries.

    Note that bibstem might be None.

    :param bibstem:
    :param year:
    :param author:
    :param journal:
    :param volume:
    :param page:
    :param full_reference:
    :return:
    """
    # for convenience of validation, predefine this:
    input_fields = dict((key, val)
        for key, val in [
            ('author', author),
            ('bibstem', bibstem),
            ('volume', volume),
            ('year', year),
            ('page', page),
            ('pub', journal)] if val)

    if bibstem == 'BAAS':
        yield Hypothesis('extra-BAAS->DDA',
            change_dict(input_fields, ['volume', 'page', 'pub'], bibstem='DDA'),
            get_score_for_baas_match,
            input_fields=input_fields,
            expected_bibstem='DDA')
        yield Hypothesis('extra-BAAS->AAS',
            change_dict(input_fields, ['volume', 'page', 'pub'], bibstem='AAS'),
            get_score_for_baas_match,
            input_fields=input_fields,
            expected_bibstem='AAS')
        yield Hypothesis('extra-BAAS->DPS',
            change_dict(input_fields, ['volume', 'page', 'pub'], bibstem='DPS'),
            get_score_for_baas_match,
            input_fields=input_fields,
            expected_bibstem='DPS')

    if bibstem=='LPSC':
        # These were published in 'volumes' per conference. So,
        # for these volume can mean essentially anything
        yield Hypothesis('LPSC-ignore-volume',
            change_dict(input_fields, ['volume', 'pub']),
            get_basic_score_for_input_fields,
            input_fields=change_dict(input_fields, ['volume']),
            expected_bibstem='LPSC')

    if bibstem=='JOSS':
        # These are software records and hence sometimes author skip including volume and page
        # that is why we are here, incomplete record, and
        # so try to match author, year, and publication only
        # if more than one record with these specification is found, no matched is returned
        yield Hypothesis('JOSS-ignore-volume-page',
            change_dict(input_fields, ['volume', 'page'], bibstem='JOSS'),
            get_author_year_pub_score_for_input_fields,
            input_fields=change_dict(input_fields, ['volume', 'page']))

    if bibstem=='ApJ':
        yield Hypothesis('extra-ApJ->ApJL',
            change_dict(input_fields, ['pub'], bibstem='ApJL'),
            get_serial_score_for_input_fields,
            input_fields=input_fields)

    if full_reference and year:
        if full_reference.count(year) > 1:
            # some pubications do not have a volume number, actually the volume number equals the year
            # when parsed if multiple year encountered, it is ignored, and hence the first numeric value is
            # considered volume, and the next one, if any is considered the page
            # so shift that, assign the year to volume, whatever is assigned to volume assign to page
            yield Hypothesis('volume-year-identical',
                change_dict(input_fields, ['volume', 'page'], volume=year, page=volume),
                get_serial_score_for_input_fields,
                input_fields=input_fields)

    if journal:
        for pattern, conf_bibstem in get_conf_series_indicators():
            if pattern.search(journal):
                # volume often isn't properly parsed out for those; if
                # this gives too may false positives, we'll have to do
                # it ourselves from journal, and then use the serial_score.
                yield Hypothesis('fielded-confser-%s'%conf_bibstem,
                    change_dict(input_fields, ['pub'], bibstem=conf_bibstem),
                    get_basic_score_for_input_fields,
                    input_fields=input_fields)
