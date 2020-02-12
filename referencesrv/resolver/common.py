from flask import current_app

class DeferredSourceMatcher(object):
    """
    # Defer loading of the actual source matcher to runtime to save on
    # startup time when we don't need it.
    """
    def __getattr__(self, att_name):
        """

        :param att_name:
        :return:
        """
        if att_name=='__bases__':
            return (object,)
        elif att_name=='__name__':
            return 'Unready source matcher'

        return getattr(current_app.extensions['source_matcher'], att_name)

SOURCE_MATCHER = DeferredSourceMatcher()


class Evidences(object):
    """
    a measure of confidence of a match.

    All scoring functions working on one aspect are supposed to give a float
    between -1 and 1, where -1 is "I'm pretty sure it's wrong" and 1 is
    "I'm almost certain it's right".  They put this score into the the
    add_evidence function.

    The individual evidences are kept by this class, but there's a get_score
    method that munges them together to yield a number between -1 and 1 that
    we hope to be a useful measure for the relative credibility of solutions.

    The individual evidences typically come from tailored matching functions
    (e.g., authors.compute_author_evidence).  Those are free to abstain
    from voting; if no evidences are collected, get_score will return
    None (which should allow for easy filtering of those).

    These evidences stand in as scores in that, when compared, they
    are ordered according to what get_score returns.
    """
    def __init__(self):
        """

        """
        self.evidences = []
        self.labels = []
        # _score is cached; None means "not computed yet or invalid"
        self.score = None

    def __lt__(self, other):
        """

        :param other:
        :return:
        """
        if hasattr(other, 'get_score'):
            return self.get_score()<other.get_score()
        else:
            return self.get_score()<other

    def __le__(self, other):
        """

        :param other:
        :return:
        """
        if hasattr(other, 'get_score'):
            return self.get_score()<=other.get_score()
        else:
            return self.get_score()<=other

    def __gt__(self, other):
        """

        :param other:
        :return:
        """
        if hasattr(other, 'get_score'):
            return self.get_score()>other.get_score()
        else:
            return self.get_score()>other

    def __ge__(self, other):
        """

        :param other:
        :return:
        """
        if hasattr(other, 'get_score'):
            return self.get_score()>=other.get_score()
        else:
            return self.get_score()>=other

    def __eq__(self, other):
        """

        :param other:
        :return:
        """
        if hasattr(other, 'get_score'):
            return self.get_score()==other.get_score()
        else:
            return self.get_score()==other

    def __len__(self):
        """

        :return:
        """
        return len(self.evidences)

    def __str__(self):
        """

        :return:
        """
        return 'Evidences(%s)'%', '.join('%s=%s'%item for item in zip (self.labels, self.evidences))

    def sum(self):
        """

        :return:
        """
        return sum(self.evidences)

    def avg(self):
        """

        :return:
        """
        if len(self.evidences) != 0:
            return round(self.sum()/len(self.evidences), 1)
        return 0

    def add_evidence(self, evidence, label):
        """
        adds evidence (a float between -1 and 1) to our evidence collection
        under label.

        :param evidence:
        :param label:
        :return:
        """
        assert current_app.config['EVIDENCE_SCORE_RANGE'][0] <= evidence <= current_app.config['EVIDENCE_SCORE_RANGE'][1]
        self.score = None
        self.evidences.append(evidence)
        self.labels.append(label)

    def get_score(self):
        """
        returns some float between -1 and 1 representative of the collective
        evidence collected.

        :return:
        """
        if not self.evidences:
            current_app.logger.error('No evidence, rejecting')
            return None
        if self.score is None:
            self.score = sum(self.evidences)
        return self.score

    def has_veto(self):
        """
        returns false if all evidence is strictly positive.

        :return:
        """
        for e in self.evidences:
            if e<=0:
                return True
        return False

    def single_veto_from(self, field_label):
        """
        returns true if there is exactly one veto and it originates from
        what has field_label.

        :param field_label:
        :return:
        """
        neg_inds = [ind for ind, ev in enumerate(self.evidences) if ev<=0]
        if len(neg_inds)==1:
            return (self.labels[neg_inds[0]]==field_label)
        return False

    def count_votes(self):
        """
        return true if the combination of terms all have high scores

        :return:
        """
        d = dict(zip(self.labels, self.evidences))
        combinations = [
            ['authors', 'pubstring', 'volume', 'year'],
            ['authors', 'year', 'page']
        ]
        for fields in combinations:
            vote = 0
            for term in fields:
                if term in d and d[term] == current_app.config['EVIDENCE_SCORE_RANGE'][1]:
                    vote += 1
            if vote == len(fields):
                return True
        return False


    def __getitem__(self, label):
        """
        returns the score for the field label if exist

        :param label:
        :return:
        """
        if label in self.labels:
            d = dict(zip(self.labels, self.evidences))
            return d[label]
        return None


class Solution(object):
    """
    a container for a solution and some ancillary metadata.

    Ancillary metadata includes:

    * citing_bibcode
    * score
    * source_hypothesis (the hypothesis that eventually got it right)
    """
    def __init__(self, cited_bibcode, score, source_hypothesis='not given', citing_bibcode=None):
        """

        :param cited_bibcode:
        :param score:
        :param source_hypothesis:
        :param citing_bibcode:
        """
        self.cited_bibcode = cited_bibcode
        self.score = score
        self.citing_bibcode = str(citing_bibcode)
        self.source_hypothesis = source_hypothesis
    
    def __str__(self):
        """

        :return:
        """
        if isinstance(self.score, Evidences):
            return '%.1f %s'%(self.score.avg(),self.cited_bibcode)
        return NotResolved(raw_ref='', citing_bibcode=self.cited_bibcode)

    def __repr__(self):
        return repr(self.cited_bibcode)


class Hypothesis(object):
    """A container for expectations to a reference.

    Constraints have a dict of fields to show to the search
    engine (the hints, get them from the attribute), and a
    get_score(response_record, hypothesis)->Evidences method.
    See common.Evidences for details.

    The get_score function receives a result record, i.e.,
    a dictionary containing at most the fields given in the
    apiQueryFields configuration.    How it compares this against
    what's in the record is basically up to the class.

    Additionally, it gets the hypotheses that generated the response.
    This is a simple way to pass information from the hints generator
    to the matching function -- usually, you should just construct
    the Hypothesis with additional keyword arguments ("details");
    you should query for them in get_score using the get_detail(str)
    -> anything method (that returns None for keys not passed).

    For debugging, you should give hypotheses short, but somewhat
    expressive names.  See below for examples.
    """

    def __init__(self, name, hints, get_score_function, **details):
        """

        :param name:
        :param hints:
        :param get_score_function:
        :param details:
        """
        self.name = name
        self.hints, self.get_score_function = hints, get_score_function
        self.details = details

    def get_score(self, response_record, hints):
        """

        :param response_record:
        :param hints:
        :return:
        """
        return self.get_score_function(response_record, hints)

    def get_detail(self, detail_name):
        """

        :param detail_name:
        :return:
        """
        if detail_name in self.details:
            return self.details.get(detail_name)
        return None

class NotResolved(object):
    """
    a sentinel class holding unresolved references.
    """
    def __init__(self, raw_ref, citing_bibcode):
        """

        :param raw_ref:
        :param citing_bibcode:
        """
        self.raw_ref = raw_ref
        self.citing_bibcode = str(citing_bibcode)

    def __str__(self):
        """

        :return:
        """
        return 'NOT RESOLVED: %s...'%(self.raw_ref[:40])

class Error(Exception):
    """
    the base class for all exceptions.
    """
    pass


class NoSolution(Error):
    """
    is raised when a solution could not be found.

    NoSolution is constructed with an explanation string and the
    Reference instance that failed.
    """
    def __init__(self, reason, ref=None):
        Error.__init__(self, reason)
        self.ref = ref
        self.reason = reason

    def __str__(self):
        if self.ref is None:
            return self.reason
        else:
            return '%s: %s'%(self.reason, self.ref)


class Undecidable(NoSolution):
    """
    is raised when the resolver needs to make a decision but cannot.

    In addition to the reference string, this also contains
    solutions_considered, pairs of evidence and solutions that were
    considered tied.
    """
    def __init__(self, reason, ref=None, considered_solutions=[]):
        NoSolution.__init__(self, reason, ref)
        self.considered_solutions = considered_solutions


class Overflow(Error):
    """is raised when too many matches come back from solr.

    It should be taken as "please try another, more specific hypothesis".
    """

class Solr(Error):
    """
    is raised when solr returns an error.
    """

def round_two_significant_digits(num):
    """

    :param num:
    :return:
    """
    return float('%s' % float('%.1g' % num))