"""
A trigdict implements a fuzzy dictionary matching keys with
Levenshtein weights.  For efficiency reasons, before computing
the distances, we go through a trigram index to find candates.

NOTE: over the original C-based implementation, the actual scores
now are a bit lower due to a slight sanitation in the scoring
formula.  I believe the sequence of items should in general be
the same, though.
"""

import editdistance


def get_trigrams(a_string):
    """
    returns the trigrams present in a_string.

    This will be empty for strings that are too short.  Repeated
    trigrams will be in the list multiple times.

    :param a_string:
    :return: 
    """
    return [a_string[i:i+3] for i in range(0, len(a_string)-2)]


class TrigIndex(object):
    """
    A trigram index.

    This is a helper class for Trigdict.  It is constructed
    with a list of strings (here: expansions).

    It will create an inverted index of trigrams within the strings.

    The lookup method will use that index to determine the 
    n expansions that have the most trigrams in common with its first
    argument.  It will return a list of these expansions.
    """
    def __init__(self, expansions):
        """
        # we make a copy of our argument -- we can't anyone let
        # anyone change it underneath us.
        
        :param expansions: 
        """
        self.expansions = list(expansions)
        self.build_index()


    def build_index(self):
        """
        
        :return: 
        """
        self.index = {}
        for exp_ind, expansion in enumerate(self.expansions):
            for trig in get_trigrams(expansion):
               if trig in self.index:
                   self.index[trig].add(exp_ind)
               else:
                   self.index[trig] = set([exp_ind])


    def lookup(self, search_term, num_best=10):
        """
        returns a list of (expansion, score) for the keys with
        the most trigrams in common with search_term.

        The score is an ad-hoc measure hand-trained for working
        well with the source of source specifications occurring
        in bibliographic references in Astronomy.

        The result is sorted ascending, i.e., the best match is at
        the end of the list.
        
        :param search_term: 
        :param num_best: 
        :return: 
        """
        match_counts = {}

        for trig in get_trigrams(search_term):
            for matching_index in self.index.get(trig, []):
                match_counts[matching_index] = 1+match_counts.get(matching_index, 0)
        # sort the candidates by the number of matches descending
        # so we have the most interesting candiates at the top.
        candidates = sorted(match_counts.items(), key=lambda i: i[1], reverse=True)
        if not candidates:
            return []

        # Don't waste CPU cycles on items that don't have at least
        # half the number of trigrams compared to the top candidates, i.e.,
        min_hits = candidates[0][1]//2 or 1

        # Do some normalisation by the lengths of the search and
        # matched strings (this is badly heuristic and could do
        # with some principled approach)
        scaled = []
        term_length = float(len(search_term))
        for exp_ind, hits in candidates:
            exp = self.expansions[exp_ind]
            delta = max(0, abs((len(exp)-term_length))/term_length)
            scaled.append((exp, hits/term_length-delta))
        
        # finally, the most ad-hoc thing: compute levenshein distances,
        # fudge in our old score, and scale again.  Ahem.
        candidates = []
        for expansion, score in scaled:
            candidates.append((expansion, 1-(1-score)*editdistance.eval(expansion, search_term)/term_length))

        # crop and adjust order for our horrible score; the sort by key
        # is so results are stable.
        candidates.sort(key=lambda p: (p[1], p[0]))

        return candidates[-num_best:]


class Trigdict(object):
    """A fuzzy dictionary.

    It doesn't really implement the dictionary protocol, just

    * __getitem__ -- returns one of the items with the smallest
      edit distance, as a 1-element list [(score, item)]
    
    In addition:

    * bestmatches(string, num_best) returns the num_best matches
      for string
    * exactmatch(string) returns an exact match, as if this
      were a python dictionary.

    Feed a Trigdict using conventional assignments of expansions to
    bibstems.  

    Note that after any change, the index will have to be re-computed, which
    can be relatively time-consuming.  Hence, you should ideally build this
    once and not add more items later.

    The expansions going in here are case-normalised (to uppercase).
    Consequently, the search terms are uppercased before matching,
    too.
    """
    def __init__(self):
        """
        
        """
        self.val_dict = {}
        self.all_values = set()
        self.shortdict = {}
        self.index = None

    def  __setitem__(self, expansion, value):
        """
        
        :param expansion: 
        :param value: 
        :return: 
        """
        expansion = expansion.upper()
        if len(expansion)<3:
            self.shortdict.setdefault(expansion, []).append(value)
        else:
            self.val_dict.setdefault(expansion, []).append(value)
            self.all_values.add(value)
        self.index = None

    def exactmatch(self, expansion):
        """
        
        :param expansion: 
        :return: 
        """
        if self.val_dict.has_key(expansion):
            return [(1, b) for b in self.val_dict[expansion]]
        else:
            return None

    def __getitem__(self, expansion, numitem=1):
        """
        
        :param expansion: 
        :param numitem: 
        :return: 
        """
        expansion = expansion.upper()
        if self.index is None:
            self.index = TrigIndex(self.val_dict.keys())

        if len(expansion)<3:
            return [(1, w) for w in self.shortdict.get(expansion, [])]

        candidates = self.index.lookup(expansion, numitem)

        res = []
        for expansion, score in candidates:
            for stem in self.val_dict[expansion]:
                res.append((score, stem))
        return res

    def bestmatches(self, word, numitem):
        """
        returns value for the numitem best matching expansions.

        Note that since there can be multiple values per expansion,
        this can return significantly more than numitem items.
        
        :param word: 
        :param numitem: 
        :return: 
        """
        return self.__getitem__(word, numitem)

    def values(self):
        """
        
        :return: 
        """
        return self.all_values
