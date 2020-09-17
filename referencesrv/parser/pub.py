"""
The module keeps track of journal/title/publisher substrings

"""

import re
import nltk
from itertools import groupby

from flask import current_app

from referencesrv.parser.common import concatenate, spot, strip, append_unique, PUNCTUATION_TOKEN, is_punctuation
from referencesrv.resolver.journalfield import is_page_number

class PubToken():

    PLACEHOLDER = {'title': '|title_%d|', 'journal': '|journal_%d|', 'publisher': '|publisher_%d|'}

    PRE_TITLE_JOURNAL_PATTERN = r'(?:(\.|\,|\:|\s|\(?\d{4}[a-z][.,)]*|\(?\d[.,)]*)*\s*)'
    TITLE_JOURNAL_FREE_FALL_PATTERN = r'[A-Z]+.+'
    TITLE_PATTERN = r'[A-Z]+[A-Za-z\d\'\s\:\-\+\?]+'
    TITLE_MULTI_PART_PATTERN = r'[A-Z]+[A-Za-z\d\'\s\-\+\?\.\:]+'
    TITLE_FREE_FALL_PATTERN = r'[A-Z]+[A-Za-z\d\'\s\:\-\+]+(\(.*\)||(\d+\.\d+\-?)*)?[A-Za-z\d\'\s\:\-\+]+' # can have parenthesis and numeric value
    TITLE_JOURNAL_GLUE_PATTERN = r'[.,\s]'
    JOURNAL_PATTERN = r'[A-Z]+[A-Za-z0-9\.\s\'\-&]+[A-Za-z]+'
    JOURNAL_MIXED_PATTERN = r'(((?i)arxiv:e-prints)|[A-Za-z0-9\.\s\'\-&]+[A-Za-z]+)'   # note that journal can start with a number (ie, 35th meeting), and number can in the juornal, but not at the end, since it is most likely volume
    POST_JOURNAL_PATTERN = r'[\s\d.,;\-]+(\w\d+)?'              # note that there could be page qualifier that proceed by number only
    POST_JOURNAL_PATTERN_ALL = r'[\d\W\w\s]'
    PUBLISHER_PATTERN = r'[A-Z]+[A-Za-z0-9\.\:\s\'\-&()]+[A-Za-z]+'
    YEAR_PATTERN = "[12][089]\d\d[a-z]?"
    TITLE_JOURNAL_PUBLISHER_EXTRACTOR = re.compile(r'^%s[\"\']*(?P<title>%s)[.,\"\']+\s+(:?[Ii][Nn][:\s])?(?P<journal>%s)%s\(?(?P<publisher>%s)\)?[\s\d,;.]*$'%(PRE_TITLE_JOURNAL_PATTERN, TITLE_PATTERN, JOURNAL_PATTERN, POST_JOURNAL_PATTERN, PUBLISHER_PATTERN))
    TITLE_JOURNAL_QUOTE_JOURNAL_ONLY = r'^%s(?P<title>%s)[\"\']\s*(?P<journal>%s)%s*[\"\']'%(PRE_TITLE_JOURNAL_PATTERN, TITLE_JOURNAL_FREE_FALL_PATTERN, TITLE_JOURNAL_FREE_FALL_PATTERN, TITLE_JOURNAL_GLUE_PATTERN)
    TITLE_JOURNAL_BOTH_QUOTED = r'^%s[\"\']\s*(?P<title>%s)%s*[\"\'].*[\"\']\s*(?P<journal>%s)%s*[\"\']'%(PRE_TITLE_JOURNAL_PATTERN, TITLE_PATTERN, TITLE_JOURNAL_GLUE_PATTERN, JOURNAL_PATTERN, TITLE_JOURNAL_GLUE_PATTERN)
    TITLE_JOURNAL_QUOTE_TITLE_IN_BEFORE_JOURNAL = r'^%s[\"\']\s*(?P<title>.*)%s*[\"\']%s*(?:[Ii][Nn][:\s])?(?P<journal>%s)+%s+$' % (PRE_TITLE_JOURNAL_PATTERN, TITLE_JOURNAL_GLUE_PATTERN, TITLE_JOURNAL_GLUE_PATTERN, JOURNAL_MIXED_PATTERN, POST_JOURNAL_PATTERN_ALL)
    TITLE_JOURNAL_MUTI_PART_TITLE = r'^%s(?P<title>%s)\,\s+(?P<journal>%s)%s.*$'%(PRE_TITLE_JOURNAL_PATTERN, TITLE_MULTI_PART_PATTERN, JOURNAL_PATTERN, POST_JOURNAL_PATTERN)
    TITLE_JOURNAL_YEAR_IN_MIDDLE = r'^%s(?P<title>%s)[\s+\(]+%s[\)\s]+(?P<journal>%s)%s.*$'%(PRE_TITLE_JOURNAL_PATTERN, TITLE_PATTERN, YEAR_PATTERN, JOURNAL_PATTERN, POST_JOURNAL_PATTERN)
    TITLE_JOURNAL_FREE_FALL = r'^%s(?P<title>%s)(\.|\,|\/)+\s+(?P<journal>%s)%s.*$'%(PRE_TITLE_JOURNAL_PATTERN, TITLE_FREE_FALL_PATTERN, JOURNAL_PATTERN, POST_JOURNAL_PATTERN)
    TITLE_JOURNAL_EXTRACTOR = [re.compile(TITLE_JOURNAL_QUOTE_JOURNAL_ONLY), re.compile(TITLE_JOURNAL_BOTH_QUOTED),
                               re.compile(TITLE_JOURNAL_QUOTE_TITLE_IN_BEFORE_JOURNAL), re.compile(TITLE_JOURNAL_MUTI_PART_TITLE),
                               re.compile(TITLE_JOURNAL_YEAR_IN_MIDDLE), re.compile(TITLE_JOURNAL_FREE_FALL),]
    TITLE_JOURNAL_PUNCTUATION_REMOVER = re.compile(r'[:\(\)\-\[\]]')
    WORDS_IN_TITLE_NOT_CAPITAL = r'a|an|the|for|and|nor|but|or|yet|so|at|around|by|after|along|for|from|of|on|to|with|without'
    JOURNAL_ONLY_MEETING = r'^%s(?P<unknown>[a-z\s]*)(?P<journal>(%s)%s+(\d+[th]*\s[A-Z]+\s[Mm]eeting)).*$'%(PRE_TITLE_JOURNAL_PATTERN, JOURNAL_PATTERN, TITLE_JOURNAL_GLUE_PATTERN)
    JOURNAL_ONLY_LOWER_CASE = r'^%s(?P<unknown>)(?P<journal>([a-z&\-\s]+)%s+)%s*$'%(PRE_TITLE_JOURNAL_PATTERN, TITLE_JOURNAL_GLUE_PATTERN, POST_JOURNAL_PATTERN_ALL)
    JOURNAL_ONLY_WITH_EDITOR = r'^%s(?P<unknown>[Ee][Dd][Ss]?|[Ii][Nn][:\s]+)?\s*(?P<journal>%s)%s+%s+$'%(PRE_TITLE_JOURNAL_PATTERN, JOURNAL_MIXED_PATTERN, TITLE_JOURNAL_GLUE_PATTERN, POST_JOURNAL_PATTERN_ALL)
    JOURNAL_ONLY_FREE_FALL = r'^%s(?P<unknown>[a-z\s,]*)(?P<journal>(%s)|[%s])%s.*$'%(PRE_TITLE_JOURNAL_PATTERN, JOURNAL_MIXED_PATTERN, WORDS_IN_TITLE_NOT_CAPITAL, POST_JOURNAL_PATTERN)
    JOURNAL_ONLY_QUOTE = r'^%s(?P<unknown>.*)[\"\'](?P<journal>%s)[\"\'].*$'%(PRE_TITLE_JOURNAL_PATTERN, JOURNAL_MIXED_PATTERN)
    JOURNAL_ONLY_ITS_TITLE = r'^%s(?P<journal>%s)%s'%(PRE_TITLE_JOURNAL_PATTERN, TITLE_PATTERN, POST_JOURNAL_PATTERN)
    JOURNAL_ONLY_EXTRACTOR = [re.compile(JOURNAL_ONLY_MEETING), re.compile(JOURNAL_ONLY_WITH_EDITOR),
                              re.compile(JOURNAL_ONLY_LOWER_CASE), re.compile(JOURNAL_ONLY_FREE_FALL),
                              re.compile(JOURNAL_ONLY_QUOTE), re.compile(JOURNAL_ONLY_ITS_TITLE)]
    JOURNAL_ABBREVIATED_EXTRACTOR = re.compile(r'^([A-Z][A-Za-z\.]*\s*)+$')

    CAPITAL_FIRST_CHAR = re.compile(r'([A-Z].*$)')

    SPACE_BEFORE_DOT_REMOVER = re.compile(r'\s+(\.)')
    SPACE_AROUND_AMPERSAND_REMOVER = re.compile(r'\b(\w)\s&\s(\w+)')

    NESTED_QUOTE = [re.compile(r'\"(.+?)\"'), re.compile(r"\'(.+?)\'")]

    TOKENIZER = re.compile(r'([\s.,])')
    TITLE_TOKENIZER = re.compile(r'(\:|[\.?!]\B)')
    PUBLISHER_TOKENIZER = re.compile(r'([^\w\s])')

    TOKENS_IDENTIFIED = re.compile(r'\|[a-z\_]+\|')

    REMOVE_PUNCTUATION = re.compile(r"[()\[\]\\/*?\"+~^,=#']")

    def __init__(self):
        """

        """
        self.segment_dict = {}

        self.academic_publishers_locations = re.compile(r'\b(%s)\b' % '|'.join(current_app.config['REFERENCE_SERVICE_ACADEMIC_PUBLISHERS_LOCATIONS']))
        self.academic_publishers = re.compile(r'\b(%s)\b' % '|'.join(current_app.config['REFERENCE_SERVICE_ACADEMIC_PUBLISHERS']))
        self.academic_publishers_and_locations = re.compile(r'\b(%s)\b' % '|'.join(
            current_app.config['REFERENCE_SERVICE_ACADEMIC_PUBLISHERS'] +
            current_app.config['REFERENCE_SERVICE_ACADEMIC_PUBLISHERS_LOCATIONS']))
        self.stopwords = current_app.config['REFERENCE_SERVICE_STOP_WORDS']
        self.punctuations = ''.join([inner for outer in PUNCTUATION_TOKEN.values() for inner in outer])


    def clear(self):
        """

        :return:
        """
        self.segment_dict = {}


    def identified_title(self):
        """

        :return: identified title as a string
        """
        return ' '.join(self.segment_dict.get('title', []))


    def identified_journal(self):
        """

        :return: identified journal as a string
        """
        return ' '.join(self.segment_dict.get('journal', []))


    def identified_publisher(self):
        """

        :return: identified publisher as a string
        """
        return ' '.join(self.segment_dict.get('publisher', []))


    def identify(self, reference_str, nltk_tagger, range_taken, have_editor):
        """
        journal, title, and publisher are multi word elements

        :param reference_str:
        :param nltk_tagger:
        :param range_taken: range indices of token identified as other types
        :param have_editor
        :return:
        """
        # save it to be used in the is_* methods
        self.segment_dict.update({'range_taken':range_taken, 'have_editor':have_editor})

        reference_str_tmp = self.TOKENS_IDENTIFIED.sub('', reference_str)

        # nested quotes messes up RE that relies on quotes to segment title/journal,
        # if there are any nested quotes go to nltk segmentation directly
        if not self.detect_nested_quotes(reference_str_tmp):
            # attempt to extract title, journal, and publisher
            extractor = self.TITLE_JOURNAL_PUBLISHER_EXTRACTOR.match(reference_str_tmp)
            if extractor:
                title = extractor.group('title').strip()
                journal = extractor.group('journal').strip()
                publisher = extractor.group('publisher').strip()
                reference_str = self.mark_identified(reference_str, title, journal, publisher)
                self.save_identified(title, journal, publisher)
                return reference_str

            # attempt to extract title and journal
            for i, tje in enumerate(self.TITLE_JOURNAL_EXTRACTOR):
                extractor = tje.match(reference_str_tmp)
                if extractor:
                    # false positive if length of title is one word
                    if len(extractor.group('title').split()) > 1:
                        title= extractor.group('title').strip()
                        journal = extractor.group('journal').strip('"').strip() if extractor.group('journal') is not None else ''
                        if len(title) > 0 and len(journal) > 0:
                            # make sure the second substring identified as journal is not publisher
                            if self.publisher_idx([journal]) == 0:
                                publisher = [journal]
                                journal = ''
                            else:
                                publisher = []
                            # any other tokens left that is part of the publisher
                            publisher += self.is_publisher_or_location(reference_str.replace(journal, '').replace(title, ''))
                            reference_str = self.mark_identified(reference_str, title, journal, publisher)
                            self.save_identified(title, journal, publisher)
                            return reference_str

            # attempt to extract journal only
            for i, je in enumerate(self.JOURNAL_ONLY_EXTRACTOR):
                extractor = je.match(reference_str_tmp)
                if extractor:
                    journal = extractor.group('journal').strip()
                    # do not accept partial journal name (ie, only J)
                    if len(journal) > 1:
                        if self.segment_dict.get('have_editor', None):
                            # it is actually title, when there is an editor
                            title = journal
                            journal = journal_save = ''
                        elif ':' in journal:
                            if journal.replace(' ','').lower() == 'arxiv:e-prints':
                                # apprently crf gets confused with having arxiv both as arxiv identifier and
                                # be part of journal, so remove it for journal, on the side of resolver
                                # `eprints` is enough indication that it is `arxiv:e-prints`
                                journal_save = 'eprints'
                            else:
                                # it is actually title, since the only journal with colon is eprint
                                title = journal
                                journal = journal_save = ''
                        else:
                            title = ''
                            journal_save = journal
                        publisher = self.is_publisher_or_location(reference_str_tmp.replace(journal, ''))
                        reference_str = self.mark_identified(reference_str, title, journal, publisher)
                        self.save_identified(title, journal_save, publisher)
                        return reference_str

        return self.identify_nltk(reference_str, nltk_tagger)


    def identify_nltk(self, reference_str, nltk_tagger):
        """

        :param reference_str:
        :param nltk_tagger:
        :return:
        """
        patterns = "NP:{<DT|TO|IN|CC|JJ.?|NN.?|NN..?|VB.?>*}"
        NPChunker = nltk.RegexpParser(patterns)

        # prepare the reference
        match = self.CAPITAL_FIRST_CHAR.search(self.TOKENS_IDENTIFIED.sub('', reference_str))
        if match:
            reference_str_tmp = match.group()
            reference_str_tmp = self.TITLE_JOURNAL_PUNCTUATION_REMOVER.sub(' ', reference_str_tmp).replace(',', '.')
            tree = NPChunker.parse(
                nltk.tag._pos_tag(nltk.word_tokenize(reference_str_tmp), tagger=nltk_tagger, lang='eng'))

            # identify noun phrases
            nps = []
            for subtree in tree:
                if type(subtree) == nltk.tree.Tree and subtree.label() == 'NP':
                    picks = ' '.join(word if not is_page_number(word) and not self.is_stopword(word) else ''
                                     for word, tag in subtree.leaves())
                    aleaf = self.SPACE_BEFORE_DOT_REMOVER.sub(r'\1',
                                        self.SPACE_AROUND_AMPERSAND_REMOVER.sub(r'\1&\2', picks)).strip(' ')
                    if len(aleaf) >= 1 and is_punctuation(aleaf) == 0:
                        nps.append(aleaf)

            # check for possible publisher in the segmented nps
            publisher = []
            while True:
                idx = self.publisher_idx(nps)
                if idx >= 0:
                    # ided publisher, assign it and remove it
                    publisher.append(nps[idx])
                    nps.pop(idx)
                else:
                    break

            # attempt to combine abbreviated words that represent journal mostly
            nps_merge = []
            for k, g in groupby(nps, lambda x: bool(self.JOURNAL_ABBREVIATED_EXTRACTOR.match(x))):
                if k:
                    nps_merge.append(' '.join(g))
                else:
                    nps_merge.extend(g)

            # see if there is lonely token and it is a stopword, remove it
            for token in [nps for nps in nps_merge if len(nps.split()) == 1 and nps.lower() in self.stopwords]:
                nps_merge.remove(token)

            # when there is a publisher, it is more than likely we have a book
            # assign everything to title
            if len(publisher) > 0:
                reference_str = self.mark_identified(reference_str, nps_merge, '', publisher)
                self.save_identified(nps_merge, [], publisher)
                return reference_str

            # TODO: if we have have_editor, we cannot identify title, and there are other tokens unaccounted for
            # most likely that is title, assign it to title and let crf take it from there

            # more than likely, if there is one field it is journal
            if len(nps_merge) == 1:
                reference_str = self.mark_identified(reference_str, '', nps_merge[0], '')
                self.save_identified([], nps_merge[0], [])
                return reference_str

            # we have more than one substring, the first is most likely title
            # do not accept title of length one token, let crf figure it out
            title = filter(None, nps_merge[0].split())
            if len(title) <= 1:
                title = ''
                journal = nps_merge[1:]
            else:
                title = ' '.join(title)
                journal = None

            # more than likely, if there are two fields, first is title, and second is journal
            if len(nps_merge) == 2:
                journal = journal if journal else nps_merge[1]
                reference_str = self.mark_identified(reference_str, title, journal, '')
                self.save_identified(title, journal, [])
                return reference_str

            # if still three fields, and publisher is not identified to be one of them
            # more than likely the first one is title, and the last one is journal
            # the middle can be either so leave it alone and let CRF figure it out
            if len(nps_merge) == 3:
                journal = journal if journal else nps_merge[2]
                reference_str = self.mark_identified(reference_str, title, journal, '')
                self.save_identified(title, journal, [])
                return reference_str

        # unable to guess
        self.save_identified([], [], [])
        return reference_str


    def save_identified(self, title, journal, publisher):
        """

        :param title:
        :param journal:
        :param publisher:
        :return:
        """
        if not isinstance(title, list):
            if len(title) > 0:
                title = [title]
            else:
                title = []
        if not isinstance(journal, list):
            if len(journal) > 0:
                journal = [journal]
            else:
                journal = []
        if not isinstance(publisher, list):
            if len(publisher) > 0:
                publisher = [publisher]
            else:
                publisher = []
        # remove unnecessary punctuations in title, keep `:` and `-`
        title = [self.REMOVE_PUNCTUATION.sub(' ', t).strip() for t in title]
        self.segment_dict.update({'title': title, 'journal': journal, 'publisher': publisher})


    def is_identifying_word(self, ref_word):
        """
        verify if ref_word is one of the editor identifying tokens

        :param ref_word:
        :return:
        """
        if ref_word and ref_word.isalpha():
            for i, word in enumerate(self.IDENTIFYING_TOKEN.values()):
                for w in word:
                    if w == ref_word.lower():
                        return i + 1
        return 0


    def fill_value(self, reference_str, token_label):
        """

        :param reference_str:
        :param token_label:
        :return:
        """
        for i, v in enumerate(self.segment_dict.get(token_label, []), start=1):
            reference_str = reference_str.replace(self.PLACEHOLDER[token_label] % i, v)
        return reference_str


    def remove_value(self, reference_str, token_label, value):
        """
        replace value with a placeholder

        :param reference_str:
        :param token_label:
        :param value:
        :return:
        """
        # make sure value is a list, could be a string,
        if not isinstance(value, list):
            if len(value) == 0:
                return reference_str
            value = [value]
        if len(value) == 0:
            return reference_str
        for i, v in enumerate(value, start=1):
            reference_str = reference_str.replace(v, self.PLACEHOLDER[token_label] % i)
        return reference_str


    def assemble(self, reference_str):
        """
        replaces PLACEHOLDER text in reference_str with values identified
        rebuilding the reference_str back to original text

        :param reference_str:
        :return:
        """
        if len(self.identified_title()) > 0:
            reference_str = self.fill_value(reference_str, 'title')
        if len(self.identified_journal()) > 0:
            reference_str = self.fill_value(reference_str, 'journal')
        if len(self.identified_publisher()) > 0:
            reference_str = self.fill_value(reference_str, 'publisher')
        return reference_str


    def mark_identified(self, reference_str, title, journal, publisher):
        """
        insert placeholder id in the position of identified tokens

        :param reference_str:
        :param title:
        :param journal:
        :param publisher:
        :return:
        """
        reference_str = self.remove_value(reference_str, 'title', title)
        reference_str = self.remove_value(reference_str, 'journal', journal)
        reference_str = self.remove_value(reference_str, 'publisher', publisher)
        return reference_str


    def detect_nested_quotes(self, reference_str):
        """

        :param reference_str:
        :return:
        """
        for pat in self.NESTED_QUOTE:
            match = pat.findall(reference_str)
            if len(match) >= 2:
                for i in range(len(match)-1):
                    inbetween = re.search(r"%s\W+(.*)\W+%s"%(match[i], match[i+1]), reference_str)
                    if inbetween and len(inbetween.group(1).strip().split()) > 1:
                        return True
        return False


    def crop_title(self, title):
        """
        split title on dot and colon, keep the first part, consider the rest as unknown
        subtitles are not kept in solr as part of title and hence does not match

        :param title:
        :return:
        """
        parts = self.TITLE_TOKENIZER.split(title)
        if len(parts) > 1:
            return parts[0]
        return title


    def publisher_idx(self, ref_words):
        """
        go through list of elements consist of multiple words
        if all the words in one element are either publisher name or location
        return its index in the entity_list

        :param ref_words:
        :return:
        """
        for i, tokens in enumerate(ref_words):
            match = self.academic_publishers_and_locations.search(tokens)
            if match:
                if match.group() == tokens:
                    return i
        return -1


    def is_publisher_or_location(self, ref_words):
        """

        :param ref_words:
        :return:
        """
        publisher_or_location = []
        for token in self.PUBLISHER_TOKENIZER.split(ref_words):
            if self.academic_publishers_and_locations.search(token):
                publisher_or_location.append(token)
        return publisher_or_location


    def is_publisher(self, ref_word, ref_label):
        """

        :param ref_word:
        :param ref_label:
        :return:
        """
        if ref_label:
            if ref_label == 'PUBLISHER':
                return 1
            return 0

        if ref_word is None:
            return 0
        return 1 if spot(ref_word, self.identified_publisher()) else 0


    def is_location(self, ref_word, ref_label):
        """

        :param ref_word:
       :param ref_label:
        :return:
        """
        if ref_label:
            if ref_label == 'PUBLISHER_LOCATION':
                return 1
            return 0

        if ref_word is None:
            return 0
        if spot(ref_word, self.identified_journal()):
            return 0
        return int(self.academic_publishers_locations.search(ref_word) is not None)


    def is_stopword(self, ref_word):
        """

        :param ref_word:
        :return:
        """
        return int(any(ref_word.lower() == stopword for stopword in self.stopwords))


    def is_token_stopword(self, ref_word, ref_label):
        """

        :param ref_word:
        :param ref_label:
        :return:
        """
        if ref_label:
            if ref_label == 'STOPWORD':
                return 1
            return 0
        return int(self.is_stopword(ref_word))


    def exist(self, ref_word, index):
        """
        is one of us
        
        :param ref_word: 
        :param index: 
        :return: 
        """
        # if token is among other types already identified
        for range in self.segment_dict.get('range_taken', [[-1, -1]]):
            if index >= range[0] and index <= range[1]:
                return 0
        # if punctuations, don't count it as title
        if ref_word in self.punctuations:
            return 0
        # possibly, yes
        return 1


    def tokenize(self, ref_word):
        """
        tokenize ref_word and return tokens that are whole words (remove empty and spaces)

        :param text:
        :return:
        """
        return filter(None, [w.strip() for w in self.TOKENIZER.split(ref_word)])


    def is_title(self, ref_word, ref_label, index):
        """
        during training/testing ref_label is populated, see if it is one of us
        during normal operation see if ref_word has been identified as one us

        :param ref_word:
        :param ref_label:
        :param index:
        :return:
        """
        if ref_label:
            return 1 if ref_label in ['TITLE', 'BOOK_TITLE'] else 0

        # if not one of us, we are done
        if self.exist(ref_word, index) == 0:
            return 0
        # if stopword, not one of us
        if self.is_stopword(ref_word):
            return 0
        return int(spot(ref_word, self.identified_title()))


    def is_journal(self, ref_word, ref_label, index):
        """
        during training/testing ref_label is populated, see if it is one of us
        during normal operation see if ref_word has been identified as one us

        :param ref_word:
        :param ref_label:
        :param index:
        :return:
        """
        if ref_label:
            return 1 if ref_label == 'JOURNAL' else 0

        # if not one of us, we are done
        if self.exist(ref_word, index) == 0:
            return 0
        # if stopword, not one of us
        if self.is_stopword(ref_word):
            return 0
        return int(spot(ref_word, self.identified_journal()))


    def where_in_title(self, ref_word_list, ref_label_list, index):
        """
        if the token is title, determine if it is the first, the last, or the middle token

        :param ref_word_list:
        :param ref_label_list:
        :param index:
        :return: 1 if the first word in title string,
                 2 if the last word in title string,
                 3 if the middle words in title string,
                 0 not in author string
        """
        if ref_label_list:
            title_tag = ['TITLE', 'BOOK_TITLE']
            if ref_label_list in title_tag:
                idx_first = next(i for i, v in enumerate(ref_label_list) if v in title_tag)
                if index == idx_first:
                    return 1
                idx_last = len(ref_label_list) - next(i for i, v in enumerate(reversed(ref_label_list)) if v in title_tag)
                if index == idx_last:
                    return 2
                if index > idx_first and index < idx_last:
                    return 3
            return 0
        
        if index >= 0 and index < len(ref_word_list):
            ref_word = ref_word_list[index]

            # if not one of us, we are done
            if self.exist(ref_word, index) == 0:
                return 0

            tokens = self.tokenize(self.identified_title())
            if len(tokens) > 0:
                if ref_word == tokens[0]:
                    return 1
                if ref_word == tokens[-1]:
                    return 2
                if any(ref_word == token for token in tokens):
                    return 3
        return 0


    def where_in_journal(self, ref_word_list, ref_label_list, index):
        """

        :param ref_word_list:
        :param ref_label_list:
        :param index:
        :return: 1 if the first word in journal string,
                 2 if the last word in journal string,
                 3 if the middle words in journal string,
                 4 if there is only one word in journal string
                 0 not in author string
        """
        if ref_label_list:
            if 'JOURNAL' in ref_label_list:
                idx_first = next(i for i, v in enumerate(ref_label_list) if v == 'JOURNAL')
                if index == idx_first:
                    # one token journal
                    if len([i for i, v in enumerate(ref_label_list) if v == 'JOURNAL']) == 1:
                        return 4
                    return 1
                idx_last = len(ref_label_list) - next(i for i, v in enumerate(reversed(ref_label_list)) if v == 'JOURNAL')
                if index == idx_last:
                    return 2
                if index > idx_first and index < idx_last:
                    return 3
            return 0

        if index >= 0 and index < len(ref_word_list):
            ref_word = ref_word_list[index]

            # if not one of us, we are done
            if self.exist(ref_word, index) == 0:
                return 0

            tokens = self.tokenize(self.identified_journal())
            if len(tokens) > 0:
                if ref_word == tokens[0]:
                    if len(tokens) == 1:
                        return 4
                    return 1
                if ref_word == tokens[-1]:
                    return 2
                if any(ref_word == token for token in tokens):
                    return 3
        return 0


    def title_features(self, ref_word_list, ref_label_list, index):
        """
        return a feature vector that has 1 in the first cell if token is title
        followed by 1 in the position corresponding to where it is first, last, or middle

        :param ref_word_list:
        :param ref_label_list:
        :param index:
        :return:
        """
        current_word = ref_word_list[index] if index >= 0 and index < len(ref_word_list) else ''
        current_label = ref_label_list[index] if index >= 0 and index < len(ref_label_list) else None
        exist = self.is_title(current_word, current_label, index)
        where = self.where_in_title(ref_word_list, ref_label_list, index) if exist == 1 else 0
        return [
            exist,  # is it more likely part of title?
            1 if where == 1 else 0,  # first word in title
            1 if where == 2 else 0,  # last word in title
            1 if where == 3 else 0,  # middle words in title
        ]


    def journal_features(self, ref_word_list, ref_label_list, index):
        """
        return a feature vector that has 1 in the first cell if token is journal
        followed by 1 in the position corresponding to where it is first, last, or middle

        :param ref_word_list:
        :param ref_label_list:
        :param index:
        :return:
        """
        current_word = ref_word_list[index] if index >= 0 and index < len(ref_word_list) else ''
        current_label = ref_label_list[index] if index >= 0 and index < len(ref_label_list) else None
        exist = self.is_journal(current_word, current_label, index)
        where = self.where_in_journal(ref_word_list, ref_label_list, index) if exist == 1 else 0
        return [
            exist,  # is it more likely part of journal?
            1 if where == 1 or where == 4 else 0,  # first word in journal, or single word journal
            1 if where == 2 or where == 4 else 0,  # last word in journal, or single word journal
            1 if where == 3 or where == 4 else 0,  # middle words in journal, or single word journal
        ]


    def publisher_features(self, ref_word, ref_label):
        """

        :param ref_word:
        :param ref_label:
        :return:
        """
        location = self.is_location(ref_word, ref_label)    # is it city or country name
        publisher = self.is_publisher(ref_word, ref_label)  # is it the publisher name
        return [location | publisher, location, publisher]


    def indices(self, ref_label_list, tag):
        """
        return the indices of tokens tagged `tag`

        :param ref_word_list:
        :param ref_label_list:
        :param tag:
        :return:
        """
        return [i for i, l in enumerate(ref_label_list) if l in tag]


    def collect_tagged_title_tokens(self, ref_word_list, ref_label_list):
        """
        go through the list of tagged tokens and collect all that are titles'

        :param ref_word_list:
        :param ref_label_list:
        :return:
        """
        idx = [i for i in self.indices(ref_label_list, ['TITLE', 'BOOK_TITLE', 'PUNCTUATION_COLON'])]
        # only take include colon if in the middle of title
        while ref_label_list[idx[0]] == 'PUNCTUATION_COLON':
            idx = idx[1:]
        while ref_label_list[idx[-1]] == 'PUNCTUATION_COLON':
            idx = idx[:-1]
        title = []
        for i in idx:
            # skip words of length 1, unless is punctuation
            if len(ref_word_list[i]) > 1 or ref_word_list[i] in self.punctuations:
                title = append_unique(title, ref_word_list[i])
        # most likely miss labeled
        if len(title) == 1:
            return ''
        return ' '.join(title).replace(' :', ':')


    def collect_tagged_journal_tokens(self, ref_word_list, ref_label_list):
        """
        go through the list of tagged tokens and collect all that are journals'

        :param ref_word_list:
        :param ref_label_list:
        :return:
        """
        # only collect unique tokens. some reference have repeated tokens, for example
        # Madec, P. Y., Kolb, J., Oberti, S., Paufique, J., La Penna, P., Hackenberg, W., Kuntschner, H., Argomedo, J., Kiekebusch, M., Donaldson, R., Suarez, M., and Arsenault, R., "Adaptive Optics Facility: control strategy and first on-sky results of the acquisition sequence," in [""Proc. SPIE""], "Society of Photo-Optical Instrumentation Engineers (SPIE) Conference Series" 9909, 99090Z (Jul 2016).
        # J. Toomre, "Some travels in the land of nonlinear convection and magnetism," in EAS Publications Series, EAS Publications Series, Vol. 82 (2019) pp. 273-294
        journal = []
        for i in self.indices(ref_label_list, ['JOURNAL']):
            # skip words of length 1, unless it is capital
            if len(ref_word_list[i]) > 1 or ref_word_list[i].isupper():
                journal = append_unique(journal, ref_word_list[i])
        return ' '.join(journal)

