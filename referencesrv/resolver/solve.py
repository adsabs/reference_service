"""
Evaluating hypotheses and working out which is acceptable.
"""

import regex as re
import urllib
import traceback

from flask import current_app

from referencesrv.resolver.common import Undecidable, NoSolution, Solution, OverflowOrNone, Solr, Incomplete, sorted2
from referencesrv.resolver.solrquery import Querier
from referencesrv.resolver.hypotheses import Hypotheses
from referencesrv.resolver.authors import normalize_author_list

# metacharacters and reserved words of the ADS solr parser
SOLR_ESCAPABLE = re.compile(r"""(?i)([-]|\bto\b|\band\b|\bor\b|\bnot\b|\bnear\b)""")
# remove punctuations in title since it is causing error in solr query, keep only -
REMOVE_PUNCTUATION = re.compile(r"[()\[\]:\\/*?\"+~^,=#'{}]")

AUTHOR_LAST_NAME = re.compile(r"([A-Z][A-Za-z\-]+)")
AUTHOR_LAST_NAME_CASE_INSENSITIVE = re.compile(r"([A-Za-z]+)")

# mappings from standard hint keys to actual solr keywords
# this is so that renaming solr indices would not affect hypothesis generation.
HINT_TO_SOLR_KEYS = {
}

def make_solr_condition_author(value):
    """

    :param value:
    :return:
    """
    # only if not already normalized
    if ";" not in value:
        value = re.sub(r"\.( ?[A-Z]\.)*", "",
                       # ... and silly "double initials"
                       re.sub(r"-[A-Z]\.", "", normalize_author_list(value, initials='.' in value)))
    # something went wrong with normalization,
    # so grab all last names and insert semicolon between them
    if ";" not in value:
        lastname = '; '.join(AUTHOR_LAST_NAME.findall(value))
        # most probably lastname is not capitalized
        # so grab the words
        if len(lastname) == 0:
            lastname = '; '.join(AUTHOR_LAST_NAME_CASE_INSENSITIVE.findall(value))
        value = lastname
    # authors fields have special serialization rules
    return " AND ".join('"%s"' % s.strip() for s in value.split(";"))

def make_solr_condition_first_author(value):
    """

    :param value:
    :return:
    """
    # something went wrong, multiple authors here
    if ',' in value:
        try:
            value = AUTHOR_LAST_NAME.findall(value)[0]
        except:
            value = value.split(',')[0]
    return value

def make_solr_condition(key, value):
    """
    returns a solr query fragment.
    :param key:
    :param value:
    :return:
    """
    if not value or not value.strip():
        return None
    key = HINT_TO_SOLR_KEYS.get(key, key)

    # need to verify if this is still needed
    # if key.endswith("_escaped"):
    #     return '%s:"%s"'%(HINT_TO_SOLR_KEYS.get(key[:-8], key[:-8]), value)

    # approximate search on first_author
    # 2/23 hold off on this for now and use first_author_norm
    # 5/21 remove the initials dots if any
    # 7/15/2019 first_author_norm cannot be approximated, go back to first_author
    # 5/7/2020 for now map both first_author_norm and first_author approximation to first_author approximation
    if key =='first_author_norm~' or key == 'first_author~':
        return 'first_author:"%s"~'%(make_solr_condition_first_author(value))
    if key == 'first_author_norm':
        return 'first_author_norm:"%s"'%(make_solr_condition_first_author(value))

    # both author and author_norm
    if 'author' in key:
        return '%s:(%s)' % (key, make_solr_condition_author(value))

    if 'pub' in key:
        return '%s:%s' % (key, value)

    if key == 'identifier':
        return 'identifier:"%s"'%(urllib.quote(value))

    if key == 'bibcode':
        return 'identifier:"%s"' %value

    if key == 'arxiv':
        return 'identifier:("arxiv:%s")'%value

    if key == 'ascl':
        return 'identifier:("ascl:%s")'%value

    if key == 'doi':
        return 'doi:"%s"'%value

    if key=='page':
        if len(value) == 1:
            return "page:(%s)"%value
        # return "page:(%s)"%(" or ".join('"%s"'%(value[:i]+'?'+value[i+1:]) for i in range(len(value))))
        # 8/22 wildcard ? preceding any character has gone away
        # as per Roman setup query with all lower and single digits
        first_char = [chr(i) for i in range(ord('a'),ord('z')+1)] + [chr(i) for i in range(ord('0'),ord('9')+1)]
        return "page:(%s or %s)"%(" or ".join(['"' + i +  value[1:] + '"' for i in first_char]),
                                  " or ".join('"%s"'%(value[:i]+'?'+value[i+1:]) for i in range(1,len(value))))

    if key=='title':
        return '%s:(%s)' % (key, " AND ".join(SOLR_ESCAPABLE.sub(r"\\\1", REMOVE_PUNCTUATION.sub('', value)).split()))

    # approximate search
    if key=='title~':
        return 'title:"%s"~' % (SOLR_ESCAPABLE.sub(r"\\\1", REMOVE_PUNCTUATION.sub('', value)))

    # becasue of ApJ oring with ApJL need to put in parentheses
    if key=='bibstem':
        return '%s:(%s)'%(key, value)

    # approximate search
    # for year discrepancy => give it a 10 year window
    if key=='year~':
        return 'year:%s'%("[%s TO %s]"%(int(value)-5, int(value)+5))

    if key=='doctype':
        return '%s:(%s)'%(key, value)

    return '%s:"%s"'%(key, SOLR_ESCAPABLE.sub(r"\\\1", value))


def inspect_doubtful_solutions(scored_solutions, query_string, hypothesis):
    """
    raises an Undecidable exception carrying halfway credible candidates.

    The goal is to add these to solve_reference's internal stash
    of candidates so we can look at them again when we're desperate.

    :param scored_solutions:
    :param query_string:
    :param hypothesis:
    :return:
    """
    non_veto_solutions = [(evidences, solution) for evidences, solution in scored_solutions if not evidences.has_veto()]
    if len(non_veto_solutions) == 1:
        sol = non_veto_solutions
        raise Undecidable("Try again if desperate", considered_solutions=[(sol[0][0].get_score(), sol[0][1]["bibcode"])])

    # Some of the following rules only make sense for fielded
    # hypotheses.  Always be aware that input_fields might be None
    input_fields = hypothesis.get_detail("input_fields")

    if input_fields:
        # Some publications are cited without a page number, but have
        # a page number of 1 in ADS (e.g., IBVS).  So, without an input
        # page, we still accept a response page of 1
        # we should base this on the result bibstem, I guess.
        for evidences, solution in scored_solutions:
            if evidences.single_veto_from("page") and not input_fields.get("page"):
                raise Undecidable("Try again if desperate", considered_solutions=[(evidences.get_score(), solution["bibcode"])])

    raise NoSolution(reason="No unique non-vetoed doubtful solution", ref=query_string)


def inspect_ambiguous_solutions(scored_solutions, query_string, hypothesis):
    """
    tries to select a solution from multiple score-hypotheses pairs.

    The function returns a pair of Evidences and solr solution, or it
    raises NoSolution or Undecidable exceptions.

    :param scored_solutions:
    :param query_string:
    :param hypothesis:
    :return:
    """
    # Let's see if the problem goes away if we discard all vetoed solutions
    non_vetoed = [(evidences, sol) for evidences, sol in scored_solutions if not evidences.has_veto()]

    if len(non_vetoed) == 1:
        current_app.logger.debug("Only one non-vetoed solution, returning it.")
        return non_vetoed[0]

    if not non_vetoed:
        current_app.logger.debug("All ambiguous solutions vetoed, inspecting with doubts.")
        return inspect_doubtful_solutions(scored_solutions, query_string, hypothesis)

    # If the leader has at least one evidence more than the runner-up, accept it
    if len(non_vetoed[-1][0])>len(non_vetoed[-2][0]):
        current_app.logger.debug("Accepting solution on larger number of evidences.")
        return non_vetoed[-1]

    # With books, it frequently happens that two entries exist for the
    # same entitiy.  Now, if their titles match (to some extent), we
    # choose one of the two
    t1 = non_vetoed[-1][1]["title"].lower().strip()
    t2 = non_vetoed[-2][1]["title"].lower().strip()
    if t1 and t2 and t1.startswith(t2) or t2.startswith(t1):
        current_app.logger.debug("Breaking ambiguity with %s suspecting it's a duplicate book"%non_vetoed[-2][1]["bibcode"])
        return non_vetoed[-1]

    to_stash = [(score.get_score(), sol["bibcode"])
                for score, sol in non_vetoed if score>current_app.config['EVIDENCE_SCORE_RANGE'][0]]
    current_app.logger.debug("Unsolved ambiguity, stashing %s"%(to_stash))
    raise Undecidable("Ambiguous %s."%(query_string), considered_solutions=to_stash)


def choose_solution(candidates, query_string, hypothesis):
    """
    returns the preferred solution from among candidates.

    The function will raise a NoSolution or Undecidable exception if
    no choice can be made.

    candidates must be a sequence of pairs of (evidences, solr_result).

    :param candidates:
    :param query_string:
    :param hypothesis:
    :return:
    """
    min_score = current_app.config['MIN_SCORE_FIRST_ROUND']
    filtered = [(score, solution) for score, solution in candidates if score >= min_score*len(score)]

    if len(filtered)==0:
        if candidates:
            current_app.logger.debug("No score above minimal score, inspecting doubtful solutions.")
            return inspect_doubtful_solutions(candidates, query_string, hypothesis)
        raise NoSolution("Not even a doubtful solution")

    elif len(filtered)==1:
        current_app.logger.debug("Accepting single unique solution")
        evidence, solution =  filtered[0]
        return evidence, solution

    elif len(filtered)>1:
        current_app.logger.debug("Trying to disentangle multiple equal-scored solutions")
        # get all equal-scored matches with the highest scores
        best_score = max(item[0].get_score() for item in filtered)
        best_solution = [(ev, solution) for ev, solution in filtered if ev.get_score()==best_score]
        if len(best_solution)==1:
            evidence, solution = best_solution[0]
            return evidence, solution
        else:
            current_app.logger.debug("...impossible")
            raise Undecidable("%s solutions with equal (good) score."%len(best_solution))


def solve_for_fields(hypothesis):
    """
    returns a record matching hypothesis or raises NoSolution.

    This does the actual query of the solr server and has the
    hypothesis evaluate whatever comes back.

    :param hypothesis:
    :return:
    """
    if not hasattr(solve_for_fields, "query"):
        QUERIER = Querier()
        query = QUERIER.query

    current_app.logger.debug("HINTS IN %s: %s"%(hypothesis.name, hypothesis.hints))

    query_string = " AND ".join(cond for cond in (make_solr_condition(*item)
                                                  for item in hypothesis.hints.items()) if cond is not None)

    solutions = query(query_string)

    if solutions:
        if len(solutions) > 0:
            current_app.logger.debug("solutions: %s"%(solutions))

            scored = list(sorted2((hypothesis.get_score(s, hypothesis), s) for s in solutions))

            current_app.logger.debug("evidences from %s"%(hypothesis.name))
            for score, sol in sorted2(scored):
                current_app.logger.debug("score %s %s %s"%(sol['bibcode'], score.get_score(), score))

            score, sol = choose_solution(scored, query_string, hypothesis)

            return Solution(sol["bibcode"], score, hypothesis.name)

    raise OverflowOrNone("Got either too many or no records from solr")


def enough_to_proceed(ref):
    """
    check to see if there are enough information to setup queries
    do not blindly create unsuccessful queries

    :param ref:
    :return:
    """
    input_fields = ref.get_detail()

    # need to have at least 3 fields to match
    available = sum([1 for field in ["author", "pub", "title", "volume", "page", "year"] if len(input_fields.get(field, "")) > 0])
    if available >= 3:
        return True
    # check identifiers next
    if input_fields.get("doi", None) is not None:
        return True
    if input_fields.get("arxiv", None) is not None:
        return True
    if input_fields.get("ascl", None) is not None:
        return True
    return False


def solve_reference(ref):
    """
    returns a solution for what record is presumably meant by ref.

    ref is an instance of Reference (or rather, its subclasses).
    If no matching record is found, NoSolution is raised.
    :param ref:
    :return:
    """
    if not enough_to_proceed(ref):
        current_app.logger.error("Not enough information to resolve the record")
        raise Incomplete("Not enough information to resolve the record.", str(ref))

    possible_solutions = []
    reason = None
    for hypothesis in Hypotheses.iter_hypotheses(ref):
        try:
            return solve_for_fields(hypothesis)
        except Undecidable as ex:
            possible_solutions.extend(ex.considered_solutions)
            reason = ex.reason
        except (NoSolution, OverflowOrNone) as ex:
            current_app.logger.debug("(%s)"%ex.__class__.__name__)
        except (Solr, KeyboardInterrupt):
            raise
        except Exception as ex:
            current_app.logger.error("Unhandled exception of type {0} occurred with arguments:{1!r}, thus killing a single hypothesis.".format(type(ex).__name__, ex.args))
            current_app.logger.error(traceback.format_exc())

    # if we have collected possible solutions for which we didn't want
    # to decide the first time around, now see if any one is better than
    # all others and accept that
    if possible_solutions:
        current_app.logger.debug("Considering stashed ties: %s"%(possible_solutions))

        cands = {}
        for score, sol in possible_solutions:
            cands.setdefault(sol, []).append((score, sol))
        for bibcode in cands:
            cands[bibcode] = max(cands[bibcode])
        scored = sorted(zip(cands.values(), cands.keys()))

        if len(scored)==1:
            return Solution(scored[0][1], scored[0][0], "only remaining of tied solutions")
        elif scored[-1][0]>scored[-2][0]:
            return Solution(scored[0][1], scored[0][0], "best tied solution")
        else:
            current_app.logger.debug("Remaining ties, giving up")
    if reason:
        raise NoSolution("Hypotheses exhausted", "%s -- %s"%(reason, str(ref)))
    raise NoSolution("Hypotheses exhausted", str(ref))
