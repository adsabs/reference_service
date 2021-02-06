"""
This module keeps track of author and editor list

"""

import re
from collections import OrderedDict

from referencesrv.parser.common import PUNCTUATION_TOKEN
from referencesrv.resolver.authors import get_authors, get_editors

class OriginatorToken():

    IDENTIFYING_WORDS = OrderedDict([('AUTHOR_COLLABORATION_IDENTIFIER', ['collaboration', 'collaboration', 'team', 'teams']),
                                     ('EDITOR_IDENTIFIER', ['editor', 'edited', 'eds', 'ed'])])

    AUTHOR_TAGS = ['AUTHOR_LAST_NAME', 'AUTHOR_FIRST_NAME', 'AUTHOR_MIDDLE_NAME', 'AUTHOR_COLLABORATION',
                   'AUTHOR_FIRST_NAME_FULL', 'AND_AUTHOR', 'ETAL_AUTHOR', 'THE_AUTHOR', 'EDITORS_AUTHOR',
                   'AUTHOR_COLLABORATION_IDENTIFIER']
    EDITOR_TAGS = ['EDITOR_LAST_NAME', 'EDITOR_FIRST_NAME', 'EDITOR_MIDDLE_NAME', 'EDITOR_IDENTIFIER',
                   'AND_EDITOR', 'ETAL_EDITOR']
    PUNCTUATION_TAGS = ['PUNCTUATION_COMMA', 'PUNCTUATION_DOT', 'PUNCTUATION_BRACKETS', 'PUNCTUATION_QUOTES']

    PLACEHOLDER = {'authors':'|authors|', 'editors':'|editors|', 'pre_editors':'|pre_editors|', 'post_editors':'|post_editors|'}

    ETAL_PAT_EXTRACTOR = re.compile(r"([\w\W]+(?i:[\s,]*et\.?\s*al\.?))")
    ETAL_PAT_ENDSWITH = re.compile(r"(.*et\.?\s*al\.?\s*)$")

    # to capture something like `Trujillo and Sheppard, 2014. Nature 507, p. 471-474.`
    # also capture `van der Klis 2000, ARA&A 38, 717`
    LAST_NAME_PREFIX = "d|de|De|des|Des|van|van der|von|Mc|der"
    SINGLE_LAST_NAME = "(?:(?:%s|[A-Z]')[' ]?)?[A-Z][a-z][A-Za-z]*"%LAST_NAME_PREFIX
    MULTI_LAST_NAME = "%s(?:[- ]%s)*" % (SINGLE_LAST_NAME, SINGLE_LAST_NAME)
    AUTHOR_PATTERN = r"(^({MULTI_LAST_NAME}\s*(?:and|&)?\s*(?:{MULTI_LAST_NAME})?[\s,]*))(:?[\.,\s]*\(?{YEAR_PATTERN}\)?)|" \
                     r"(^{MULTI_LAST_NAME}\s*(?:and|&)?\s*(?:{MULTI_LAST_NAME})?)[\.,\s]*{YEAR_PATTERN}"\
        .format(MULTI_LAST_NAME=MULTI_LAST_NAME, YEAR_PATTERN="[12][089]\d\d")
    LAST_NAME_EXTRACTOR = re.compile(AUTHOR_PATTERN)

    # to capture something like `CS Casari, M Tommasini, RR Tykwinski, A Milani, Carbon-atom wires: 1-D systems with tunable properties, Nanoscale 2016; 8: 4414-35. DOI:10.1039/C5NR06175J.`
    INITIALS_NO_DOT_EXTRACTOR = re.compile(r"([A-Z]+\s*[A-Z]+[a-z]+[,\s]*)+")

    EDITOR_EXTRACTOR = [re.compile(r'(?P<pre_editors>[Ee]dited by[:\s]+)(?P<editors>.*)(?P<post_editors>)'),
                        re.compile(r'(?P<pre_editors>[Ii][Nn][":\s]+)(?P<editors>.*)(?P<post_editors>\(?[(\s][Ee][Dd][Ss]?[.,\s")]*)'),
                        re.compile(r'(?P<pre_editors>\(?[(\s][Ee][Dd][Ss]?[.,\s")]*)(?P<editors>.*)(?P<post_editors>)')]

    def __init__(self, reference_tokenizer):
        """

        :param reference_tokenizer: to tokenize the identified substring, and keep track of identified indices
        """
        self.segment_dict = {}
        self.reference_tokenizer = reference_tokenizer
        self.punctuations = ''.join([inner for outer in PUNCTUATION_TOKEN.values() for inner in outer])


    def clear(self):
        """

        :return:
        """
        self.segment_dict = {}


    def identify(self, reference_str):
        """
        attempt to identify authors and authors substring

        :param reference_str: 
        :return:
        """
        # identify authors
        authors = self.identify_authors(reference_str)
        if len(authors) > 0:
            len_authors = len(list(filter(None, [a.strip() for a in self.reference_tokenizer.split(authors)])))
            author_indices = [0, len_authors-1]
            self.segment_dict.update({'authors':authors.replace("&", "and"), 'author_indices':author_indices})

        # also identify editors if any
        editors, pre_editors, post_editors = self.identify_editors(reference_str)
        if len(editors) > 0:
            # note that `in` or `ed` are not counted as part of editor list
            # however they need to be remove from reference to be able to identify necessary tokens
            # following editor identifications
            before_and_after = reference_str.split(editors)
            if len(before_and_after) == 2:
                num_tokens_before = len(list(filter(None, [a for a in self.reference_tokenizer.split(before_and_after[0])])))
                len_editors = len(list(filter(None, [a for a in self.reference_tokenizer.split(editors)])))
                editor_indices = [num_tokens_before, num_tokens_before+len_editors-1]
            else:
                editor_indices = [-1, -1]
            self.segment_dict.update({'editors': editors, 'editor_indices':editor_indices,
                                      'pre_editors': pre_editors, 'post_editors': post_editors})

        # update reference_str
        if len(authors) > 0:
            reference_str = self.PLACEHOLDER['authors'] + reference_str[len(authors):]
        if len(editors) > 0:
            reference_str = reference_str.replace(editors, self.PLACEHOLDER['editors'])
        if len(pre_editors) > 0:
            reference_str = reference_str.replace(pre_editors, self.PLACEHOLDER['pre_editors'])
        if len(post_editors) > 0:
            reference_str = reference_str.replace(post_editors, self.PLACEHOLDER['post_editors'])
        return reference_str


    def assemble(self, reference_str):
        """
        replaces PLACEHOLDER text in reference_str with values identified
        rebuilding the reference_str back to original text

        :param reference_str:
        :return:
        """
        if len(self.segment_dict.get('authors', '')) > 0:
            reference_str = reference_str.replace(self.PLACEHOLDER['authors'], self.segment_dict.get('authors'))
        if len(self.segment_dict.get('editors', '')) > 0:
            reference_str = reference_str.replace(self.PLACEHOLDER['editors'], self.segment_dict.get('editors'))
        if len(self.segment_dict.get('pre_editors', '')) > 0:
            reference_str = reference_str.replace(self.PLACEHOLDER['pre_editors'], self.segment_dict.get('pre_editors'))
        if len(self.segment_dict.get('post_editors', '')) > 0:
            reference_str = reference_str.replace(self.PLACEHOLDER['post_editors'], self.segment_dict.get('post_editors'))
        return reference_str


    def identify_authors(self, reference_str):
        """

        :param reference_str:
        :return:
        """
        try:
            authors = get_authors(reference_str)
        except:
            # something went wrong and we have no author list,
            # see if there is et al., and if so return everything prior to it
            authors = ''
            match = self.ETAL_PAT_EXTRACTOR.match(reference_str)
            if match:
                authors = match.group().strip()
            # no et al.
            # get words prior to year, these should be list of last names, no PUNCTUATIONS
            else:
                match = self.LAST_NAME_EXTRACTOR.match(reference_str)
                if match:
                    authors = match.group(1).strip()
                else:
                    match = self.INITIALS_NO_DOT_EXTRACTOR.match(reference_str)
                    if match:
                        authors = match.group().strip()
            if authors:
                if authors.endswith(','):
                    authors = authors[:-1]

        return authors


    def identify_editors(self, reference_str):
        """
        as far as I can tell there are two patterns to listing editors
            1- in <list of editors> ed or ed. or eds
            2- in <book title> ed or ed. or eds <list of editors>
        hence for the first case we have identifier words both before and after which needs to be removed
        for the second case we need to remove only the before words (ie, ed or ed. or eds)

        :param reference_str:
        :return:
        """
        editors = pre_editors = post_editors = ''
        for i, ee in enumerate(self.EDITOR_EXTRACTOR):
            match = ee.search(reference_str)
            if match:
                if get_editors(match.group('editors')):
                    editors = get_editors(match.group('editors'))
                    if len(editors) > 0:
                        pre_editors = match.group('pre_editors')
                        post_editors = match.group('post_editors')
                        break

        return editors, pre_editors, post_editors


    def is_author(self, ref_label, index):
        """
        during training/testing ref_label is populated, see if it is one of us
        during normal operation see if ref_word has been identified as one us

        :param ref_label:
        :param index:
        :return:
        """
        if ref_label:
            return 1 if ref_label in self.AUTHOR_TAGS else 0

        author_indices = self.segment_dict.get('author_indices', [-1, -1])
        if index >= author_indices[0] and index <= author_indices[1]:
            return 1
        return 0


    def is_editor(self, ref_label, index):
        """
        during training/testing ref_label is populated, see if it is one of us
        during normal operation see if ref_word has been identified as one us

        :param ref_label:
        :param index:
        :return:
        """
        if ref_label:
            return 1 if ref_label in self.EDITOR_TAGS else 0

        editor_indices = self.segment_dict.get('editor_indices', [-1, -1])
        if index >= editor_indices[0] and index <= editor_indices[1]:
            return 1
        return 0


    def where_in_author(self, ref_label_list, index):
        """
        if the token is author, determine if it is the first, the last, or the middle token

        :param ref_label_list:
        :param index:
        :return: 1 if the first word in author string,
                 2 if the last word in author string,
                 3 if the middle words in author string,
                 0 not in author string
        """
        if ref_label_list:
            if next((l for l in ref_label_list if 'AUTHOR_' in l), None) is not None:
                idx_first = next(i for i,v in enumerate(ref_label_list) if v in ['AUTHOR_LAST_NAME', 'AUTHOR_FIRST_NAME', 'AUTHOR_FIRST_NAME_FULL', 'AUTHOR_COLLABORATION'])
                if index == idx_first:
                    return 1
                idx_last =  len(ref_label_list) - next(i for i,v in enumerate(reversed(ref_label_list)) if v in ['AUTHOR_LAST_NAME', 'AUTHOR_FIRST_NAME', 'AUTHOR_FIRST_NAME_FULL', 'AUTHOR_COLLABORATION', 'ETAL_AUTHOR']) - 1
                if index == idx_last:
                    return 2
                if index > idx_first and index < idx_last:
                    return 3
            return 0

        author_indices = self.segment_dict.get('author_indices', [-1, -1])
        if index == author_indices[0]:
            return 1
        if index == author_indices[1]:
            return 2
        if index > author_indices[0] and index < author_indices[1]:
            return 3
        return 0


    def where_in_editor(self, ref_label_list, index):
        """
        if the token is editor, determine if it is the first, the last, or the middle token

        :param ref_label_list:
        :param index:
        :return: 1 if the first word in editor string,
                 2 if the last word in editor string,
                 3 if the middle words in editor string,
                 4
                 0 not in editor string
        """
        if len(ref_label_list) > 0:
            if next((l for l in ref_label_list if 'EDITOR_' in l), None) is not None:
                idx_first = next(i for i,v in enumerate(ref_label_list) if v in ['EDITOR_LAST_NAME', 'EDITOR_FIRST_NAME'])
                if index == idx_first:
                    return 1
                idx_last =  len(ref_label_list) - next(i for i,v in enumerate(reversed(ref_label_list)) if v in ['EDITOR_LAST_NAME', 'EDITOR_FIRST_NAME', 'ETAL_EDITOR']) - 1
                if index == idx_last:
                    return 2
                if index > idx_first and index < idx_last:
                    return 3
            return 0

        editor_indices = self.segment_dict.get('editor_indices', [-1, -1])
        if index == editor_indices[0]:
            return 1
        if index == editor_indices[1]:
            return 2
        if index > editor_indices[0] and index < editor_indices[1]:
            return 3
        return 0


    def author_features(self, ref_word_list, ref_label_list, index):
        """
        return a feature vector that has 1 in the first cell if token is author
        followed by 1 in the position corresponding to where it is first, last, or middle

        :param ref_word_list:
        :param ref_label_list:
        :param index:
        :return:
        """
        current_word = ref_word_list[index] if index >= 0 and index < len(ref_word_list) else ''
        current_label = ref_label_list[index] if index >= 0 and index < len(ref_label_list) else None
        if current_word in self.punctuations:
            exist = where = identifier = 0
        else:
            exist = self.is_author(current_label, index)
            where = self.where_in_author(ref_label_list, index)
            identifier = self.is_author_collaboration_identifier(current_word, current_label)
        return [
            exist,  # is it more likely author
            1 if where == 1 else 0,  # if it is author determine if first word (usually lastname, but can be firstname or first initial, or collaborator)
            1 if where == 2 else 0,  # any author tags appearing in the middle
            1 if where == 3 else 0,  # or the last (could be et al)
            identifier,  # is it identifier
        ]


    def editor_features(self, ref_word_list, ref_label_list, index):
        """
        return a feature vector that has 1 in the first cell if token is editor
        followed by 1 in the position corresponding to where it is first, last, or middle

        :param ref_word_list:
        :param ref_label_list:
        :param index:
        :return:
        """
        current_word = ref_word_list[index] if index >= 0 and index < len(ref_word_list) else ''
        current_label = ref_label_list[index] if index >= 0 and index < len(ref_label_list) else None
        if current_word in self.punctuations:
            exist = where = identifier = 0
        else:
            exist = self.is_editor(current_label, index)
            where = self.where_in_editor(ref_label_list, index)
            identifier = self.is_editor_identifier(current_word, current_label)
        return [
            exist,  # is it more likely editor
            1 if where == 1 else 0,  # if it is editor determine if first word (usually lastname, but can be firstname or first initial)
            1 if where == 2 else 0,  # any editor tags appearing in the middle
            1 if where == 3 else 0,  # or the last (could be et al)
            identifier,  # is it identifier
        ]


    def is_author_collaboration_identifier(self, ref_word, ref_label):
        """

        :param ref_word:
        :param ref_label:
        :return:
        """
        if ref_label:
            if ref_label == 'AUTHOR_COLLABORATION_IDENTIFIER':
                return 1
            return 0
        return int(any(ref_word.lower() == id for id in self.IDENTIFYING_WORDS['AUTHOR_COLLABORATION_IDENTIFIER']))


    def is_editor_identifier(self, ref_word, ref_label):
        """

        :param ref_word:
        :param ref_label:
        :return:
        """
        if ref_label:
            if ref_label == 'EDITOR_IDENTIFIER':
                return 1
            return 0
        return int(any(ref_word.lower() == id for id in self.IDENTIFYING_WORDS['EDITOR_IDENTIFIER']))


    def collect_tagged_tokens(self, ref_word_list, ref_label_list):
        """
        go through the list of tagged tokens and collect all that are authors'

        :param ref_word_list:
        :param ref_label_list:
        :return:
        """
        name = []
        for i, (w, l) in enumerate(zip(ref_word_list, ref_label_list)):
            if l in self.AUTHOR_TAGS + self.PUNCTUATION_TAGS + ['STOPWORD']:
                # skip brackets and stopword
                # `and` between the last two authors should not be tagged as stopword,
                # but sometimes if there is an `and` in title/journal
                # then all ands gets tagged by crf as stopword,
                # the other stopword that can appear in author list is `the` (ie, before collabrations name)
                # we can skip 'the` but not `and`
                if l in ['PUNCTUATION_BRACKETS', 'STOPWORD', 'PUNCTUATION_QUOTES'] and w != 'and':
                    continue
                # add space between tokens, unless it is dot or comma that does not need a space insert it before it
                # also do not insert space before and after single quote
                if l not in ['PUNCTUATION_COMMA', 'PUNCTUATION_DOT'] and ref_label_list[i-1] != 'PUNCTUATION_QUOTES' and len(name) > 0:
                    name.append(' ')
                name.append(w)
            # remove last comma(s)
            elif len(name) > 0:
                while name[-1] in [',', ' ']:
                    name.pop()
                break
            else:
                break
        return ''.join(name)


    def indices(self):
        """
        returns the range of tokens identified as originators

        :return:
        """
        identified = []
        if self.segment_dict.get('author_indices', None):
            identified.append(self.segment_dict.get('author_indices'))
        if self.segment_dict.get('editor_indices', None):
            identified.append(self.segment_dict.get('editor_indices'))
        return identified


    def have_editor(self):
        """

        :return: True if editor(s) identified
        """
        return self.segment_dict.get('editor_indices', None) != None


    def remove_editors(self, reference_str):
        """
        remove what has been identified as editor from reference_str
        needed for unittest verification

        :return:
        """
        if len(self.segment_dict.get('editors', '')) > 0:
            reference_str = reference_str.replace(self.segment_dict.get('editors'), '')
        if len(self.segment_dict.get('pre_editors', '')) > 0:
            reference_str = reference_str.replace(self.segment_dict.get('pre_editors'), '')
        if len(self.segment_dict.get('post_editors', '')) > 0:
            reference_str = reference_str.replace(self.segment_dict.get('post_editors'), '')
        return reference_str