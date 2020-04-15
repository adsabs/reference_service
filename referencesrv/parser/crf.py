"""
The module contains classes to train/test/classify
conditional random field machine learning method

"""

import os
import traceback
import numpy as np
import re
import nltk
import time, datetime
from pystruct.models import ChainCRF
from pystruct.learners import FrankWolfeSSVM
from itertools import groupby
from collections import OrderedDict

from flask import current_app

try:
    import cPickle as pickle
except ImportError:
    import pickle

from referencesrv.parser.getDataXML import get_xml_tagged_data_training, get_xml_tagged_data
from referencesrv.parser.getDataText import get_arxiv_tagged_data

from referencesrv.resolver.authors import get_authors, get_editors
from referencesrv.resolver.journalfield import is_page_number


class CRFClassifier(object):
    IDENTIFYING_WORDS = OrderedDict(
        [('ARXIV_IDENTIFIER', ['arxiv']), ('EDITOR_IDENTIFIER', ['editor', 'eds']), ('ET_AL', ['et', 'al']),
         ('DOI_IDENTIFIER', ['doi']), ('ISSUE_IDENTIFIER', ['issue']), ('ISSN__IDENTIFIER', ['issn']),
         ('PAGE_IDENTIFIER', ['page', 'pages', 'pp', 'p']), ('VERSION_IDENTIFIER', ['version']),
         ('VOLUME_IDENTIFIER', ['volume', 'vol']), ('ISBN_IDENTIFIER', ['isbn']), ('ASCL_IDENTIFIER', ['ascl'])])

    PUNCTUATIONS = OrderedDict(
        [('PUNCTUATION_BRACKETS', ['[', ']']), ('PUNCTUATION_COLON', [':']), ('PUNCTUATION_COMMA', [',']),
         ('PUNCTUATION_DOT', ['.']), ('PUNCTUATION_PARENTHESIS', ['(', ')']), ('PUNCTUATION_QUOTES', ['"', '\'']),
         ('PUNCTUATION_NUM', ['#']), ('PUNCTUATION_HYPEN', ['-']), ('PUNCTUATION_FORWARD_SLASH', ['/']),
         ('PUNCTUATION_SEMICOLON', [';'])])

    SEGMENT_DICT_KEYS = ['year', 'title', 'journal', 'publisher', 'volume', 'issue', 'page', 'doi', 'arxiv', 'issn', 'unknown', 'version', 'ascl', 'unknown_url']

    # these are used to tag training references and so crf decodes identify words to these labels
    # author labels
    AUTHOR_TAGS = ['AUTHOR_LAST_NAME', 'PUNCTUATION_COMMA', 'AUTHOR_FIRST_NAME', 'PUNCTUATION_DOT', 'AUTHOR_MIDDLE_NAME', 'AND', 'ET_AL', 'PUNCTUATION_HYPEN', 'AUTHOR_COLLABORATION']
    # numeric labels
    NUMERIC_TAGS = ['ARXIV', 'DOI', 'ISSUE', 'PAGE', 'VERSION', 'VOLUME', 'ISSN', 'YEAR', 'ASCL']

    STOPWORD_TAGS = ['AND', 'IN', 'OF', 'THE']
    
    WORD_BREAKER_REMOVE = [re.compile(r'[A-Za-z]*(-\s+)[A-Za-z]*')]

    START_WITH_AUTHOR = re.compile(r'([A-Za-z].*$)')
    CAPITAL_FIRST_CHAR = re.compile(r'([A-Z].*$)')

    QUOTES_AROUND_ETAL_REMOVE = re.compile(r'(.*)(")(et al\.?)(")(.*)', re.IGNORECASE)
    TO_ADD_DOT_AFTER_FIRST_INITIAL = re.compile(r'\b([A-Z])(\s,?[A-Z][A-Za-z]+,)')
    TO_ADD_DOT_AFTER_INITIALS = re.compile(r'\b([A-Z])\s*([A-Z])(\s,?[A-Z][A-Za-z]+,)')

    TITLE_JOURNAL_EXTRACTOR = [re.compile(r'^[.,\s]*(?P<title>[A-Z]+[A-za-z\'\s:-]+)[.,()\s\d\w]+"(?P<journal>[A-Z]+[A-Za-z\s.]+)".*'),
                               re.compile(r'^[.,\s]*"(?P<title>[A-Z]+[\w\.\'\s:-]+)[.,\s]+"\s*"(?P<journal>[A-Z]*[A-Za-z\s.]*)"?'),
                               re.compile(r'^[.,\s]*"(?P<title>[A-Z]+[\w\.\'\s:-]+)[.,\s]*"(?:[.,\s]+.*[Ii][Nn][:\s]|\s*)(?P<journal>[A-Za-z\.\s]+)+.*'),
                               re.compile(r'^[.,\s]*"(?P<title>[A-Z]+[\w\.\'\s:-]+)[.,\s]+"\s*(?P<journal>\s*)'),
                               re.compile(r'^[.,\s]*(?P<title>[A-Z]+[A-Za-z\d\'\s:-]+)[.,\s]+(?P<journal>[A-Z]+[A-Za-z\.\s]+)[\s\d,;]+.*'),]
    TITLE_JOURNAL_PUNCTUATION_REMOVER = re.compile(r'[:\(\)\-\[\]]')
    WORDS_IN_TITLE_NOT_CAPITAL = "a|an|the|for|and|nor|but|or|yet|so|at|around|by|after|along|for|from|of|on|to|with|without"
    JOURNAL_ONLY_EXTRACTOR = [re.compile(r'^[\s\d,]*[a-z\s]*(?P<journal>([A-Z][A-Za-z\s]+)[,\s]+(\d+[th]*\s[A-Z]+\s[Mm]eeting))[\d,.\s\w-]*$'),
                              re.compile(r'^[\s\d,]*[a-z\s,]*(?P<journal>([A-Z]+[A-Za-z&\-\s]*)|[%s])[\d,.\s\w-]*$'%WORDS_IN_TITLE_NOT_CAPITAL),
                              re.compile(r'^[\s\d,.eds]*(?P<journal>([A-Z][A-Za-z\s]+)[.,\s]+)[()\d,.\s\w-]*$'),
                              re.compile(r'^[\s\d,.]*(?P<journal>([a-z&\-\s]+)[.,\s]+)[()\d,.\s\w-]*$'),]
    TITLE_JOURNAL_REMOVE_IN = re.compile(r'^[\s*[Ii][Nn][:\s]*]*|[\s*[Ii][Nn][:\s]*]*$')
    URL_EXTRACTOR = re.compile(r'(https?://[A-z0-9\-\.\/]+)')
    EDITOR_EXTRACTOR = re.compile(r'(:?[Ii][Nn][":\s]+)(.*)(:?[Ee][Dd][Ss]?[.,\s"])')
    EDITOR_RESIDUE = re.compile(r'(I[Nn]+[:\s]{1,2}?\s+([\(]?[Ee]+d[s\.\)\s]+)?)')
    ARXIV_ID_EXTRACTOR = re.compile(r'(\w+\-\w+/\d+|\w+/\d{7}|\d{4}\.\d{4,5})(v?\d*)')
    ASCL_ID_EXTRACTOR = re.compile(r'((ascl\s*:\s*)([\d.]+))')
    DOI_ID_EXTRACTOR = re.compile(r'(?P<doi>(doi|DOI)?[\s\.\:]{0,2}\b10\.\s*\d{4}[\d\:\.\-\_\/\(\)A-Za-z\s]+)')

    URL_TO_DOI = re.compile(r'(.*)((https://|http://)(dx.doi.org/|doi.org/))(.*)')
    URL_TO_ARXIV = re.compile(r'(.*)((https://|http://)(arxiv.org/abs/))(.*)')

    # two specific formats for matching volume, page, issue
    # note that in the first expression issue matches a space, there is no issue in this format,
    # it is included to have all three groups present
    FORMATTED_MULTI_NUMERIC_EXTRACTOR = [re.compile(r'(?P<volume>\d+)\s+(?P<issue>\d+)\s*:(?P<page>[A-Z]?\d+\-?[A-Z]?\d*)'),
                                         re.compile(r'(?P<volume>\d+):(?P<page>[A-Z]?\d+\-?[A-Z]?\d*)(?P<issue>\s*)')]
    ETAL_PAT_EXTRACTOR = re.compile(r"([\w\W]+(?i)[\s,]*et\.?\s*al\.?)")
    ETAL_PAT_ENDSWITH = re.compile(r"(.*et\.?\s*al\.?\s*)$")
    # to capture something like `Trujillo and Sheppard, 2014. Nature 507, p. 471-474.`
    # also capture `van der Klis 2000, ARA&A 38, 717`
    LAST_NAME_PREFIX = "d|de|De|des|Des|van|van der|von|Mc|der"
    SINGLE_LAST_NAME = "(?:(?:%s|[A-Z]')[' ]?)?[A-Z][a-z][A-Za-z]*"%LAST_NAME_PREFIX
    MULTI_LAST_NAME = "%s(?:[- ]%s)*" % (SINGLE_LAST_NAME, SINGLE_LAST_NAME)
    YEAR_PATTERN = "[12][089]\d\d"
    AUTHOR_PATTERN = r"(^({MULTI_LAST_NAME}\s*(?:and|&)?\s*(?:{MULTI_LAST_NAME})?[\s,]*))(:?[\.,\s]*\(?{YEAR_PATTERN}\)?)|(^{MULTI_LAST_NAME}\s*(?:and|&)?\s*(?:{MULTI_LAST_NAME})?)[\.,\s]*{YEAR_PATTERN}".format(MULTI_LAST_NAME=MULTI_LAST_NAME, YEAR_PATTERN=YEAR_PATTERN)
    LAST_NAME_EXTRACTOR = re.compile(AUTHOR_PATTERN)

    # to capture something like `CS Casari, M Tommasini, RR Tykwinski, A Milani, Carbon-atom wires: 1-D systems with tunable properties, Nanoscale 2016; 8: 4414-35. DOI:10.1039/C5NR06175J.`
    INITIALS_NO_DOT_EXTRACTOR = re.compile(r"([A-Z]+\s*[A-Z]+[a-z]+[,\s]*)+")

    PAGE_EXTRACTOR = re.compile(r'(?=.*[0-9])(?P<page>[BHPL0-9]+[-.][BHPL0-9]+)')
    VOLUME_EXTRACTOR = re.compile(r'(vol|volume)[.\s]+(?P<volume>\w+)')
    YEAR_EXTRACTOR = re.compile(r'[(\s]*(%s[a-z]?)[)\s.,]+'%YEAR_PATTERN)
    START_WITH_YEAR = re.compile(r'(^%s)'%YEAR_PATTERN)

    REFERENCE_TOKENIZER = re.compile(r'([\s,.():;\[\]"#\/\-])')
    TAGGED_MULTI_WORD_TOKENIZER = re.compile(r'([\s.,])')

    # is all capital
    IS_CAPITAL = re.compile(r'^([A-Z]+)$')
    # is alphabet only, consider hyphenated words also
    IS_ALPHABET = re.compile(r'^(?=.*[a-zA-Z])([a-zA-Z\-]+)$')
    # is numeric only, consider the page range with - being also numeric
    # also include arxiv id with a dot to be numeric
    # note that this differs from function is_numeric in the
    # sense that this recognizes numeric even if it was not identified/tagged
    IS_NUMERIC = re.compile(r'^(?=.*[0-9])([0-9\-\.]+)$')
    # is alphanumeric, must have at least one digit and one alphabet character
    IS_ALPHANUMERIC = re.compile(r'^(?=.*[0-9])(?=.*[a-zA-Z])([a-zA-Z0-9]+)$')

    # should star with a digit, or end with a digit, or be all digits
    IS_MOSTLY_DIGIT = re.compile(r'(\b[A-Za-z0-9]+[0-9]\b|\b[0-9]+[0-9A-Za-z]\b|\b[0-9]\b)')

    SPACE_BEFORE_DOT_REMOVER = re.compile(r'\s+(\.)')
    SPACE_AROUND_AMPERSAND_REMOVER = re.compile(r'\b(\w)\s&\s(\w+)')

    JOURNAL_ABBREVIATED_EXTRACTOR = re.compile(r'^([A-Z][A-Za-z\.]*\s*)+$')

    MATCH_A_WORD = re.compile(r'\w+')
    MATCH_A_WORD_HYPHENATED = re.compile(r'(\w+(?:-\w+)*)')
    MATCH_A_NONE_WORD = re.compile(r'\W+')
    MATCH_PARENTHESIS = re.compile(r'[()]')

    PUNCTUATION_REMOVER_FOR_NUMERIC_ID = re.compile(r'[(),"]')
    
    REGEX_PATTERN_WHOLE_WORD_ONLY = r'\b%s\b'

    def __init__(self):
        """

        """
        self.academic_publishers_locations_re = re.compile(r'\b(%s)\b' % '|'.join(current_app.config['REFERENCE_SERVICE_ACADEMIC_PUBLISHERS_LOCATIONS']))
        self.academic_publishers_re = re.compile(r'\b(%s)\b' % '|'.join(current_app.config['REFERENCE_SERVICE_ACADEMIC_PUBLISHERS']))
        self.academic_publishers_and_locations_re = re.compile(r'\b(%s)\b' % '|'.join(
            current_app.config['REFERENCE_SERVICE_ACADEMIC_PUBLISHERS'] +
            current_app.config['REFERENCE_SERVICE_ACADEMIC_PUBLISHERS_LOCATIONS']))
        self.stopwords = current_app.config['REFERENCE_SERVICE_STOP_WORDS']

        self.year_now = datetime.datetime.now().year
        self.year_earliest =  1400

    def create_crf(self):
        """

        :return:
        """
        # to load nltk tagger, a time consuming, one time needed operation
        self.nltk_tagger = nltk.tag._get_tagger()
        self.crf = FrankWolfeSSVM(model=ChainCRF(), C=1.0, max_iter=50)
        self.X, self.y, self.label_code, self.folds, generate_fold = self.load_training_data()

        score = 0
        # only need to iterate through if fold was generated
        num_tries = 10 if generate_fold else 1
        while (score <= 0.90) and (num_tries > 0):
            try:
                X_train, y_train = self.get_train_data()
                self.train(X_train, y_train)

                X_test, y_test = self.get_test_data()
                score = self.evaluate(X_test, y_test)
            except Exception as e:
                current_app.logger.error('Exception: %s'%(str(e)))
                current_app.logger.error(traceback.format_exc())
                pass
            num_tries -= 1
        return (score > 0)

    def get_num_states(self):
        """

        :return:
        """
        num_states = len(np.unique(np.hstack([y for y in self.y[self.folds != 0]])))
        current_app.logger.debug("number of states = %s" % num_states)
        return num_states

    def get_folds_array(self, filename):
        """
        read the distribution of train and test indices from file
        :param filename:
        :return:
        """
        with open(filename, 'r') as f:
            reader = f.readlines()
            for line in reader:
                if line.startswith("STATIC_FOLD"):
                    try:
                        return eval(line.split(" = ")[1])
                    except:
                        return None

    def get_train_data(self):
        """

        :return:
        """
        return self.X[self.folds != 0], self.y[self.folds != 0]

    def get_test_data(self):
        """

        :return:
        """
        return self.X[self.folds == 0], self.y[self.folds == 0]

    def train(self, X_train, y_train):
        """
        :param X_train: is a numpy array of samples where each sample
                        has the shape (n_labels, n_features)
        :param y_train: is numpy array of labels
        :return:
        """
        self.crf.fit(X_train, y_train)

    def evaluate(self, X_test, y_test):
        """

        :param X_test:
        :param y_test:
        :return:
        """
        return self.crf.score(X_test, y_test)

    def decoder(self, numeric_label):
        """

        :param numeric_label:
        :return:
        """
        labels = []
        for nl in numeric_label:
            key = next(key for key, value in self.label_code.items() if value == nl)
            labels.append(key)
        return labels

    def encoder(self, labels):
        """

        :param labels:
        :return: dict of labels as key and numeric value is its value
        """
        # assign a numeric value to each label
        label_code = {}
        numeric = -1
        for label in labels:
            for l in label:
                if (numeric >= 0 and l in label_code):
                    continue
                else:
                    numeric = numeric + 1
                    label_code[l] = numeric
        return label_code

    def save(self, filename):
        """
        save object to a pickle file
        :return:
        """
        try:
            with open(filename, "wb") as f:
                pickler = pickle.Pickler(f, -1)
                pickler.dump(self.crf)
                pickler.dump(self.label_code)
                pickler.dump(self.nltk_tagger)
            current_app.logger.info("saved crf in %s."%filename)
            return True
        except Exception as e:
            current_app.logger.error('Exception: %s' % (str(e)))
            current_app.logger.error(traceback.format_exc())
            return False

    def load(self, filename):
        """

        :return:
        """
        try:
            with open(self.filename, "rb") as f:
                unpickler = pickle.Unpickler(f)
                self.crf = unpickler.load()
                self.label_code = unpickler.load()
                self.nltk_tagger = unpickler.load()
            current_app.logger.info("loaded crf from %s."%filename)
            return self.crf
        except Exception as e:
            current_app.logger.error('Exception: %s' % (str(e)))
            current_app.logger.error(traceback.format_exc())

    def substitute(self, pattern, replace, text):
        """
        replace whole word only in the text

        :param patten:
        :param repalce:
        :param text:
        :return:
        """
        if isinstance(pattern, list):
            pattern_escape = '\\b|\\b'.join([re.escape(p) for p in pattern])
            return re.sub(self.REGEX_PATTERN_WHOLE_WORD_ONLY % pattern_escape, replace, text)
        return re.sub(self.REGEX_PATTERN_WHOLE_WORD_ONLY % re.escape(pattern), replace, text)

    def search(self, pattern, text):
        """
        search whole word only in the text
        :param pattern:
        :param text:
        :return:
        """
        return re.search(self.REGEX_PATTERN_WHOLE_WORD_ONLY % pattern, text.lower())

    def tokenize_identified_multi_words(self, text):
        """
        tokenzie section of reference that has been identified, these include author, title, journal, and publisher
        basically this is used to be able to tell if word is the beginning of identified section, in the middle, or the
        last word
        
        :param text:
        :return:
        """
        return filter(None, [w.strip() for w in self.TAGGED_MULTI_WORD_TOKENIZER.split(text)])

    def get_labeled_multi_words(self, words, labels, current_label):
        """
        get all the words that have the same label (ie, journal, title, publisher can be multiple words, compared
        to numeric words, year, volume, that are single words)

        :param words:
        :param labels:
        :param current_label
        :return:
        """
        indices = [i for i in range(len(words)) if labels[i] == current_label]
        if len(indices) == 0:
            return []
        if len(indices) == 1:
            return [words[indices[0]]]
        return [words[i] for i in indices]

    def identifier_arxiv_or_ascl(self, words, labels):
        """

        :param words:
        :param labels:
        :return:
        """
        if 'ARXIV' in labels:
            # just to be sure, verify what has been tagged as arxiv is actually arxiv id
            arXiv = self.ARXIV_ID_EXTRACTOR.search(words[labels.index('ARXIV')])
            if arXiv:
                return arXiv.group(1)
        # crf sometimes mistaken ascl for arxiv, makes no difference
        # since we are going to compare with identifier field
        if 'ASCL' in labels or 'ARXIV' in labels:
            ascl = self.ASCL_ID_EXTRACTOR.search(words[labels.index('ASCL' if 'ASCL' in labels else 'ARXIV')])
            # does not make any difference if this is ASCL id or arXiv id, so assign it to arxiv field
            if ascl:
                return ascl.group(3)
        return ''

    def reference(self, refstr, words, labels):
        """
        put identified words into a dict to be passed out
        
        :param words:
        :param labels:
        :return:
        """
        ref_dict = {}
        name = []
        for i, (w, l) in enumerate(zip(words, labels)):
            if l in self.AUTHOR_TAGS:
                if (l.startswith('AUTHOR_') or l in ['AND', '&', 'ET_AL']) and len(name) > 0:
                    if 'PUNCTUATION_COMMA' in labels and labels[i - 1] != 'PUNCTUATION_HYPEN':
                        name.append(' ')
                    elif labels[i - 1] == 'AUTHOR_LAST_NAME':
                        name.append(', ')
                    elif labels[i - 1] in ['AUTHOR_FIRST_NAME', 'AUTHOR_MIDDLE_NAME'] and len(words[i - 1]) == 1:
                        name.append('. ')
                name.append(w)
            elif len(name) > 0:
                if name[-1] == ',':
                    name.pop()
                break
            else:
                break
        ref_dict['authors'] = ''.join(name)
        if 'YEAR' in labels:
            ref_dict['year'] = words[labels.index('YEAR')]
        if 'VOLUME' in labels:
            # TODO: figure out why multiple words are marked as volume by CRF
            # for now if there are multiple volumes return the first numeric value
            volume = [words[i] for i, value in enumerate(labels) if value == 'VOLUME']
            if len(volume) == 1:
                ref_dict['volume'] = volume[0]
            else:
                for v in volume:
                    if v.isdigit():
                        ref_dict['volume'] = v
                        break
        if 'PAGE' in labels:
            ref_dict['page'] = words[labels.index('PAGE')]
        if 'ISSUE' in labels:
            ref_dict['issue'] = words[labels.index('ISSUE')]
        if 'ARXIV' in labels or 'ASCL' in labels:
            identifier = self.identifier_arxiv_or_ascl(words, labels)
            if len(identifier) > 0:
                ref_dict['arxiv'] = identifier
        if 'DOI' in labels:
            # just to be sure, verify what has been tagged as doi is actually doi
            doi = self.extract_doi(words[labels.index('DOI')])
            if len(doi) > 0:
                ref_dict['doi'] = doi[doi.find('10'):]
        if 'ISSN' in labels:
            ref_dict['ISSN'] = words[labels.index('ISSN')]
        if 'JOURNAL' in labels:
            journal = []
            for i in [i for i, l in enumerate(labels) if l == 'JOURNAL']:
                journal.append(words[i])
            if len(journal) > 0:
                ref_dict['journal'] = self.TITLE_JOURNAL_REMOVE_IN.sub('', ' '.join(journal)).strip()
        if 'TITLE' in labels:
            title = []
            for i in [i for i, l in enumerate(labels) if l == 'TITLE' or l == 'BOOK_TITLE']:
                title.append(words[i])
            if len(title) > 0:
                ref_dict['title'] = self.TITLE_JOURNAL_REMOVE_IN.sub('', ' '.join(title)).strip()
        ref_dict['refstr'] = refstr
        return ref_dict

    def is_numeric_tag(self, ref_data, index, ref_label, current_label, segment_dict):
        """

        :param ref_data:
        :param index:
        :param ref_label:
        :param current_label:
        :param segment_dict:
        :return:
        """
        if len(ref_label) > 0:
            return 1 if ref_label[index] == current_label else 0
        return 1 if ref_data[index] == segment_dict[current_label.lower()] else 0

    def is_year_tag(self, ref_data, index, ref_label, segment_dict):
        """

        :param ref_data:
        :param index:
        :param ref_label:
        :param segment_dict:
        :return:
        """
        return self.is_numeric_tag(ref_data, index, ref_label, 'YEAR', segment_dict)

    def is_volume_tag(self, ref_data, index, ref_label, segment_dict):
        """

        :param ref_data:
        :param index:
        :param ref_label:
        :param segment_dict:
        :return:
        """
        return self.is_numeric_tag(ref_data, index, ref_label, 'VOLUME', segment_dict)

    def is_page_tag(self, ref_data, index, ref_label, segment_dict):
        """

        :param ref_data:
        :param index:
        :param ref_label:
        :param segment_dict:
        :return:
        """
        return self.is_numeric_tag(ref_data, index, ref_label, 'PAGE', segment_dict)

    def is_issue_tag(self, ref_data, index, ref_label, segment_dict):
        """

        :param ref_data:
        :param index:
        :param ref_label:
        :param segment_dict:
        :return:
        """
        return self.is_numeric_tag(ref_data, index, ref_label, 'ISSUE', segment_dict)

    def is_arxiv_tag(self, ref_data, index, ref_label, segment_dict):
        """

        :param ref_data:
        :param index:
        :param ref_label:
        :param segment_dict:
        :return:
        """
        return self.is_numeric_tag(ref_data, index, ref_label, 'ARXIV', segment_dict)

    def is_doi_tag(self, ref_data, index, ref_label, segment_dict):
        """

        :param ref_data:
        :param index:
        :param ref_label:
        :param segment_dict:
        :return:
        """
        return self.is_numeric_tag(ref_data, index, ref_label, 'DOI', segment_dict)

    def is_issn_tag(self, ref_data, index, ref_label, segment_dict):
        """

        :param ref_data:
        :param index:
        :param ref_label:
        :param segment_dict:
        :return:
        """
        return self.is_numeric_tag(ref_data, index, ref_label, 'ISSN', segment_dict)

    def is_ascl_tag(self, ref_data, index, ref_label, segment_dict):
        """

        :param ref_data:
        :param index:
        :param ref_label:
        :param segment_dict:
        :return:
        """
        return self.is_numeric_tag(ref_data, index, ref_label, 'ASCL', segment_dict)


    def compare_string(self, sub_str, str):
        """

        :param substring:
        :param string:
        :return:
        """
        return any(sub_str == token for token in self.MATCH_A_WORD.findall(str))

    def is_numeric(self, ref_data, index, ref_label, segment_dict):
        """

        :param ref_data:
        :param index:
        :param ref_label:
        :param segment_dict:
        :return:
        """
        if len(ref_label) > 0:
            return 1 if ref_label[index] in self.NUMERIC_TAGS else 0
        return int(any(ref_data[index] == segment_dict[tag.lower()] for tag in self.NUMERIC_TAGS))

    def is_unknown(self, ref_data, index, ref_label, segment_dict):
        """
        any words that we were not able to guess what it could be (we guess to be able to compute
        some of the values for the features passed to crf) identify as unknown and let crf decided
        :param ref_data:
        :param index:
        :param ref_label:
        :param segment_dict:
        :return:
        """
        if len(ref_label) > 0:
            return 0
        return 1 if ref_data[index] in segment_dict.get('unknown', '') else 0

    def is_title(self, ref_data, index, ref_label, segment_dict):
        """

        :param ref_data:
        :param index:
        :param ref_label:
        :param segment_dict:
        :return:
        """
        if len(ref_label) > 0:
            return 1 if (ref_label[index] == 'TITLE' or ref_label[index] == 'BOOK_TITLE') else 0
        return 1 if self.compare_string(ref_data[index], segment_dict.get('title', ''))  else 0

    def is_journal(self, ref_data, index, ref_label, segment_dict):
        """

        :param ref_data:
        :param index:
        :param ref_label:
        :param segment_dict:
        :return:
        """
        if len(ref_label) > 0:
            return 1 if ref_label[index] == 'JOURNAL' else 0
        # let crf decide if for example J. is first/middle initials or stands for journal
        return 1 if self.compare_string(ref_data[index], segment_dict.get('journal', '')) and \
                not self.compare_string(ref_data[index], segment_dict.get('authors', '')) else 0

    def is_publisher(self, ref_data, index, ref_label, segment_dict):
        """

        :param ref_data:
        :param index:
        :param ref_label:
        :return:
        """
        if len(ref_label) > 0:
            if ref_label[index] == 'PUBLISHER':
                return 1
            return 0
        return 1 if self.compare_string(ref_data[index], segment_dict.get('publisher', '')) else 0

    def is_location(self, ref_data, index, ref_label):
        """

        :param ref_data:
        :param index:
        :param ref_label:
        :return:
        """
        if len(ref_label) > 0:
            if ref_label[index] == 'PUBLISHER_LOCATION':
                return 1
            return 0
        return int(self.academic_publishers_locations_re.search(ref_data[index]) is not None)

    def is_publisher_or_location(self, words):
        """

        :param words:
        :return:
        """
        publisher_or_location = list(sum(list(map(lambda m: tuple(filter(bool, m)),
                                                  self.academic_publishers_and_locations_re.findall(words))), ()))
        return ' '.join(publisher_or_location)

    def is_stopword(self, ref_data, index, ref_label):
        """

        :param ref_data:
        :param index:
        :param ref_label:
        :return:
        """
        if len(ref_label) > 0:
            if ref_label[index] in self.STOPWORD_TAGS:
                return 1
            return 0
        return int(ref_data[index] in self.stopwords)
    
    def is_author(self, ref_data, index, ref_label, segment_dict):
        """
        
        :param ref_data: 
        :param index: 
        :param ref_label: 
        :return: 
        """
        if len(ref_label) > 0:
            return 1 if ref_label[index] in self.AUTHOR_TAGS else 0
        # let crf decide if for example J. is first/middle initials or stands for journal
        return 1 if self.compare_string(ref_data[index], segment_dict.get('authors', '')) and \
                not self.compare_string(ref_data[index], segment_dict.get('journal', '')) else 0

    def is_identifying_word(self, ref_data_word):
        """

        :param a_word:
        :return:
        """
        for i, word in enumerate(self.IDENTIFYING_WORDS.values()):
            for w in word:
                if self.search(w, ref_data_word):
                    return i+1
        return 0

    def which_identifying_word(self, ref_data, index, ref_label):
        """

        :param ref_data:
        :param index:
        :param ref_label:
        :return: 1 if arXiv, 2 if editor, 3 if et al, 4 if doi, 5 if issue, 6 if issn, 7 if page,
                 8 if version, 9 if volume, 10 if isbn, 11 if ascl
        """
        if len(ref_label) > 0:
            return self.IDENTIFYING_WORDS.keys().index(ref_label[index])+1 \
                            if ref_label[index] in self.IDENTIFYING_WORDS.keys() else 0
        return self.is_identifying_word(ref_data[index])

    def is_punctuation(self, punctuation):
        """

        :param punctuation:
        :return: 0 if not a punctuation
                 1 if brackets, 2 if colon, 3 if comma, 4 if dot, 5 if parenthesis,
                 6 if quotes (both single and double), 7 if num sign, 8 if hypen, 9 if forward slash,
                 10 if semicolon
        """
        found = [i for i, p in enumerate(self.PUNCTUATIONS.values()) if punctuation in p]
        return found[0]+1 if len(found) > 0 else 0

    def which_punctuation(self, ref_data, index, ref_label):
        """

        :param ref_data:
        :param index:
        :param ref_label:
        :return:
        """
        if len(ref_label) > 0:
            return self.PUNCTUATIONS.keys().index(ref_label[index])+1 \
                            if ref_label[index] in self.PUNCTUATIONS.keys() else 0
        return self.is_punctuation(ref_data[index])

    def where_in_author(self, ref_data, index, ref_label, segment_dict):
        """

        :param ref_data:
        :param index:
        :param ref_label:
        :param segment_dict:
        :return: 1 if the first word in author string,
                 2 if the last word in author string,
                 3 if the middle words in author string,
                 0 not in author string
        """
        if len(ref_label) > 0:
            if next((l for l in ref_label if 'AUTHOR_' in l), None) is not None:
                idx_first = next(i for i,v in enumerate(ref_label) if v in ['AUTHOR_LAST_NAME', 'AUTHOR_FIRST_NAME', 'AUTHOR_COLLABORATION'])
                if index == idx_first:
                    return 1
                idx_last =  len(ref_label) - next(i for i,v in enumerate(reversed(ref_label)) if v in ['AUTHOR_LAST_NAME', 'AUTHOR_FIRST_NAME', 'ET_AL', 'AUTHOR_COLLABORATION']) - 1
                if index == idx_last:
                    return 2
                if index > idx_first and index < idx_last:
                    return 3
            return 0

        if len(segment_dict.get('authors', '')) > 0:
            token = self.tokenize_identified_multi_words(segment_dict.get('authors', ''))
            # let crf decide if for example J. is first/middle initials or stands for journal
            if ref_data[index] in token and ref_data[index] in self.tokenize_identified_multi_words(segment_dict.get('journal', '')):
                return 0
            if ref_data[index] == token[0]:
                return 1
            if ref_data[index] == token[-1]:
                return 2
            if index > 0 and index < len(token):
                return 3
        return 0

    def where_in_title(self, ref_data, index, ref_label, segment_dict):
        """

        :param ref_data:
        :param index:
        :param ref_label:
        :param segment_dict:
        :return: 1 if the first word in title string,
                 2 if the last word in title string,
                 3 if the middle words in title string,
                 0 not in author string
        """
        if len(ref_label) > 0:
            if 'TITLE' in ref_label or 'BOOK_TITLE' in ref_label:
                idx_first = next(i for i, v in enumerate(ref_label) if v in ['TITLE','BOOK_TITLE'])
                if index == idx_first:
                    return 1
                idx_last = len(ref_label) - next(i for i, v in enumerate(reversed(ref_label)) if v in ['TITLE','BOOK_TITLE'])
                if index == idx_last:
                    return 2
                if index > idx_first and index < idx_last:
                    return 3
            return 0

        if len(segment_dict.get('title', '')) > 0:
            token = self.tokenize_identified_multi_words(segment_dict.get('title', ''))
            # compare two words for the beginning and the end if possible
            if len(token) >= 2 and index > 1 and index < len(ref_data)-1:
                if ref_data[index] == token[0] and ref_data[index+1] == token[1]:
                    return 1
                if ref_data[index] == token[-1] and ref_data[index-1] == token[-2]:
                    return 2
            if ref_data[index] == token[0]:
                return 1
            if ref_data[index] == token[-1]:
                return 2
            if ref_data[index] in token or ref_data[index] in segment_dict.get('unknown', '').split() \
                    and not self.is_stopword(ref_data, index, ref_label):
                return 3
        return 0

    def where_in_journal(self, ref_data, index, ref_label, segment_dict):
        """

        :param ref_data:
        :param index:
        :param ref_label:
        :param segment_dict:
        :return: 1 if the first word in journal string,
                 2 if the last word in journal string,
                 3 if the middle words in journal string,
                 0 not in author string
        """
        if len(ref_label) > 0:
            if 'JOURNAL' in ref_label:
                idx_first = next(i for i, v in enumerate(ref_label) if v == 'JOURNAL')
                if index == idx_first:
                    return 1
                idx_last = len(ref_label) - next(i for i, v in enumerate(reversed(ref_label)) if v == 'JOURNAL')
                if index == idx_last:
                    return 2
                if index > idx_first and index < idx_last:
                    return 3
            return 0

        if len(segment_dict.get('journal', '')) > 0:
            token = self.tokenize_identified_multi_words(segment_dict.get('journal', ''))
            # let crf decide if for example J. is first/middle initials or stands for journal
            if ref_data[index] in token and ref_data[index] in self.tokenize_identified_multi_words(segment_dict.get('authors', '')):
                return 0
            if ref_data[index] == token[0]:
                return 1
            if ref_data[index] == token[-1]:
                return 2
            if ref_data[index] in token:
                return 3
        return 0

    def get_data_features_author(self, ref_data, index, ref_label, segment_dict):
        """

        :param ref_data:
        :param index:
        :param ref_label:
        :param segment_dict:
        :return:
        """
        where = self.where_in_author(ref_data, index, ref_label, segment_dict)
        return [
            self.is_author(ref_data, index, ref_label, segment_dict),  # is it more likely author
            1 if where == 1 else 0,  # if it is author determine if first word (usually lastname, but can be firstname or first initial, or collaborator)
            1 if where == 2 else 0,  # any of the middle words
            1 if where == 3 else 0,  # or the last (could be et al)
        ]

    def get_data_features_title(self, ref_data, index, ref_label, segment_dict):
        """

        :param ref_data:
        :param index:
        :param ref_label:
        :param segment_dict:
        :return:
        """
        where = self.where_in_title(ref_data, index, ref_label, segment_dict)
        return [
            self.is_title(ref_data, index, ref_label, segment_dict),  # is it more likely part of title?
            1 if where == 1 else 0,  # first word in title
            1 if where == 2 else 0,  # last word in title
            1 if where == 3 else 0,  # middle words in title
        ]

    def get_data_features_journal(self, ref_data, index, ref_label, segment_dict):
        """

        :param ref_data:
        :param index:
        :param ref_label:
        :param segment_dict:
        :return:
        """
        where = self.where_in_journal(ref_data, index, ref_label, segment_dict)
        return [
            self.is_journal(ref_data, index, ref_label, segment_dict),  # is it more likely part of journal?
            1 if where == 1 else 0,  # first word in journal
            1 if where == 2 else 0,  # last word in journal
            1 if where == 3 else 0,  # middle words in journal
        ]

    def get_data_features_identifying_word(self, ref_data, index, ref_label):
        """

        :param ref_data:
        :param index:
        :param ref_label:
        :return:
        """
        which = self.which_identifying_word(ref_data, index, ref_label)
        return [
            int(self.is_identifying_word(ref_data[index]) > 0),
            1 if which == 1 else 0,   # 1 if arXiv,
            1 if which == 2 else 0,   # 2 if editor,
            1 if which == 3 else 0,   # 3 if et al,
            1 if which == 4 else 0,   # 4 if doi,
            1 if which == 5 else 0,   # 5 if issue,
            1 if which == 6 else 0,   # 6 if issn
            1 if which == 7 else 0,   # 7 if page,
            1 if which == 8 else 0,   # 8 if version,
            1 if which == 9 else 0,   # 9 if volume,
            1 if which == 10 else 0,  # 10 if isbn,
            1 if which == 11 else 0,  # 11 if ascl,
        ]

    def get_data_features_punctuation(self, ref_data, index, ref_label):
        """

        :param ref_data:
        :param index:
        :param ref_label:
        :return:
        """
        which = self.which_punctuation(ref_data, index, ref_label)
        return [
            int(self.is_punctuation(ref_data[index]) > 0),
            1 if which == 1 else 0,   # 1 if brackets,
            1 if which == 2 else 0,   # 2 if colon,
            1 if which == 3 else 0,   # 3 if comma,
            1 if which == 4 else 0,   # 4 if dot,
            1 if which == 5 else 0,   # 5 if parenthesis,
            1 if which == 6 else 0,   # 6 if quotes (both single and double),
            1 if which == 7 else 0,   # 7 if num signs,
            1 if which == 8 else 0,   # 8 if hypen,
            1 if which == 9 else 0,   # 9 if forward slash,
            1 if which == 10 else 0,  # 10 if semicolon,
        ]

    def get_data_features(self, ref_data, index, ref_label=[], segment_dict={}):
        """

        :param ref_data: has the form [e1,e2,e3,..]
        :param index: the position of the word in the set
        :param ref_label: labels for ref_data available during training only
        :param noun_phrase
        :return:
        """
        last_index = len(ref_data) - 1
        return [
            len(ref_data[index]),                                                                           # length of element
            len(ref_data[index-1]) if index > 0 else 0,                                                     # length of previous element if any
            len(ref_data[index+1]) if index < last_index else 0,                                            # length of next element if any
            int(self.IS_CAPITAL.match(ref_data[index]) is not None),                                        # is element all capital
            int(self.IS_CAPITAL.match(ref_data[index-1]) is not None) if index > 0 else 0,                  # is previous element, if any, all capital
            int(self.IS_CAPITAL.match(ref_data[index+1]) is not None) if index < last_index else 0,         # is next element, if any, all capital
            int(ref_data[index][0].isupper()),                                                              # is first character capital
            int(ref_data[index-1][0].isupper()) if index > 0 else 0,                                        # is previous element, if any, first character capital
            int(ref_data[index+1][0].isupper()) if index < last_index else 0,                               # is next element's, if any, first character capital
            int(self.IS_ALPHABET.match(ref_data[index]) is not None),                                       # is alphabet only, consider hyphenated words also
            int(self.IS_ALPHABET.match(ref_data[index-1]) is not None) if index > 0 else 0,                 # what about previous word, if any
            int(self.IS_ALPHABET.match(ref_data[index+1]) is not None) if index < last_index else 0,        # and next word, if any
            int(self.IS_NUMERIC.match(ref_data[index]) is not None),                                        # is numeric only, consider the page range with - being also numeric
            int(self.IS_NUMERIC.match(ref_data[index-1]) is not None) if index > 0 else 0,                  # what about previous word, if any
            int(self.IS_NUMERIC.match(ref_data[index+1]) is not None) if index < last_index else 0,         # and next word, if any
            self.is_numeric(ref_data, index, ref_label, segment_dict),                                      # is numeric only
            self.is_numeric(ref_data, index-1, ref_label, segment_dict) if index > 0 else 0,                # what about previous word, if any
            self.is_numeric(ref_data, index+1, ref_label, segment_dict) if index < last_index else 0,       # and next word, if any
            int(self.IS_ALPHANUMERIC.match(ref_data[index]) is not None),                                   # is alphanumeric, must at least one digit and one alphabet character
            int(self.IS_ALPHANUMERIC.match(ref_data[index-1]) is not None) if index > 0 else 0,             # what about previous word, if any
            int(self.IS_ALPHANUMERIC.match(ref_data[index+1]) is not None) if index < last_index else 0,    # and next word, if any
            self.is_stopword(ref_data, index, ref_label),                                                   # is it stopword
            self.is_stopword(ref_data, index-1, ref_label) if index > 0 else 0,                             # what about previous word, if any
            self.is_stopword(ref_data, index+1, ref_label) if index < last_index else 0,                    # and next word, if any
            self.is_year_tag(ref_data, index, ref_label, segment_dict),                                     # is it a year?
            self.is_page_tag(ref_data, index, ref_label, segment_dict),                                     # is it a page?
            self.is_volume_tag(ref_data, index, ref_label, segment_dict),                                   # is it more likely volume?
            self.is_issue_tag(ref_data, index, ref_label, segment_dict),                                    # is it more likely issue?
            self.is_arxiv_tag(ref_data, index, ref_label, segment_dict),                                    # is it more likely arXiv id?
            self.is_doi_tag(ref_data, index, ref_label, segment_dict),                                      # is it more likely doi?
            self.is_issn_tag(ref_data, index, ref_label, segment_dict),                                     # is it more likely issn?
            self.is_ascl_tag(ref_data, index, ref_label, segment_dict),                                     # is it more likely ascl?
            self.is_location(ref_data, index, ref_label),                                                   # is it city or country name
            self.is_publisher(ref_data, index, ref_label, segment_dict),                                    # is it the publisher name
            self.is_unknown(ref_data, index, ref_label, segment_dict),                                      # is it one of the words unable to guess
        ] \
            + self.get_data_features_author(ref_data, index, ref_label, segment_dict) \
            + self.get_data_features_title(ref_data, index, ref_label, segment_dict) \
            + self.get_data_features_journal(ref_data, index, ref_label, segment_dict) \
            + self.get_data_features_identifying_word(ref_data, index, ref_label) \
            + self.get_data_features_punctuation(ref_data, index, ref_label)

    def format_training_data(self, the_data):
        """

        :param the_data:
        :return:
        """
        # get label, word in the original presentation
        labels = [[elem[0] for elem in ref] for ref in the_data]
        words = [[elem[1] for elem in ref] for ref in the_data]

        # count how many unique labels there are, return a dict to convert from words to numeric words
        label_code = self.encoder(labels)

        numeric_labels = []
        features = []
        for label, word in zip(labels, words):
            # replace of numeric words for the original presentation of label
            numeric_label = []
            for l in label:
                numeric_label.append(label_code[l])
            numeric_labels.append(np.array(numeric_label))

            # get the numeric features for the original presentation of word and insert at index of label
            feature = []
            for idx in range(len(word)):
                feature.append(self.get_data_features(word, idx, label))
            features.append(np.array(feature))
        return features, numeric_labels, label_code


class CRFClassifierXML(CRFClassifier):
    def __init__(self):
        CRFClassifier.__init__(self)

    def load_training_data(self):
        """
        load training/test data
        :return:
        """
        training_files_path = os.path.dirname(__file__) + '/training_files/'
        xml_ref_filenames = [training_files_path + 'S0019103517302440.xml',
                             training_files_path + 'S0019103517303470.xml',
                             training_files_path + '10.1371_journal.pone.0048146.xref.xml',
                             training_files_path + '10.1073_pnas.1205221109.xref.xml',
                             training_files_path + 'iss5.springer.xml']
        references= []
        for f in xml_ref_filenames:
            references = references + get_xml_tagged_data_training(f)

        X, y, label_code = self.format_training_data(references)

        # for now use static division. see comments in foldModelText.dat
        generate_fold = False
        if generate_fold:
            folds = list(np.random.choice(range(0, 9), len(y)))
        else:
            folds = self.get_folds_array(training_files_path + 'foldModelXML.dat')

        return np.array(X), np.array(y), label_code, np.array(folds), generate_fold

    def merge_authors(self, reference_list):
        """
        merge the tagged authors into a single string

        :param reference_list:
        :return:
        """
        name = []
        for l, w in reference_list:
            if l in self.AUTHOR_TAGS:
                name.append(w)
                if l == 'AUTHOR_LAST_NAME':
                    name.append(' ')
                elif l in ['AUTHOR_FIRST_NAME', 'AUTHOR_MIDDLE_NAME', 'ET_AL']:
                    name.append(' ')
        if len(name) > 0 and name[-1] == ' ':
            name.pop()
        return ''.join(name)

    def extract_doi(self, reference_str):
        """
        just need this to be compatible to the text model
        in the xml side, just need to return the string
        :param reference_str:
        :return:
        """
        return reference_str

    def segment(self, reference_list):
        """

        :param reference_list:
        :return:
        """
        if not isinstance(reference_list, list):
            return []

        # get label, words from the tagged list
        labels = []
        words = []
        for elem in reference_list:
            # in xml format the dot at the end of first/middle initial and journal is attached to the field
            # separate them here
            if elem[0] in ['AUTHOR_FIRST_NAME', 'AUTHOR_MIDDLE_NAME', 'JOURNAL'] and elem[1].endswith('.'):
                labels += [elem[0], 'PUNCTUATION_DOT']
                words += [elem[1][:-1], '.']
            else:
                labels.append(elem[0])
                words.append(elem[1])

        segment_dict = {}
        segment_dict['authors'] = self.merge_authors(reference_list)
        ref_words = self.tokenize_identified_multi_words(segment_dict.get('authors', '')) if len(segment_dict.get('authors', ''))>0 else []
        for key in self.SEGMENT_DICT_KEYS:
            if key.upper() in labels:
                words_for_label = self.get_labeled_multi_words(words, labels, key.upper())
                segment_dict[key] = ' '.join(words_for_label)
                ref_words += words_for_label
            else:
                segment_dict[key] = ''
        segment_dict['refstr'] = words[labels.index('REFSTR')]
        segment_dict['refplaintext'] = words[labels.index('REFPLAINTEXT')] if 'REFPLAINTEXT' in labels else None
        return segment_dict, ref_words

    def classify(self, reference_str):
        """
        Run the classifier on input data
        :param reference_str:
        :return: list of words and the corresponding list of labels
        """
        segment_dict, ref_words = self.segment(reference_str)
        features = []
        if len(ref_words) > 0:
            for i in range(len(ref_words)):
                features.append(self.get_data_features(ref_words, i, [], segment_dict))
            ref_labels = self.decoder(self.crf.predict([np.array(features)])[0])
            return segment_dict['refstr'], segment_dict['refplaintext'], ref_words, ref_labels
        return segment_dict['refstr'], segment_dict['refplaintext'], None, None

    def parse(self, raw_references):
        """

        :param raw_references:
        :return:
        """
        parsed_references = []
        tagged_references = get_xml_tagged_data(raw_references)
        for tagged_reference in tagged_references:
            refstr, refplaintext, words, labels = self.classify(tagged_reference)
            if words and labels:
                parsed_reference = self.reference(refstr, words, labels)
            else:
                parsed_reference = {'refstr':refstr}
            if refplaintext:
                parsed_reference['refplaintext'] =  refplaintext
            parsed_references.append(parsed_reference)
        return parsed_references


class CRFClassifierText(CRFClassifier):

    def __init__(self):
        CRFClassifier.__init__(self)
        self.filename = os.path.dirname(__file__) + '/serialized_files/crfModelText.pkl'

    def load_training_data(self):
        """
        load training/test data
        :return:
        """
        training_files_path = os.path.dirname(__file__) + '/training_files/'
        arXiv_text_ref_filenames = [training_files_path + 'arxiv.raw',]
        references= []
        for f in arXiv_text_ref_filenames:
            references = references + get_arxiv_tagged_data(f)

        X, y, label_code = self.format_training_data(references)

        generate_fold = False
        # for now use static division. see comments in foldModelText.dat
        if generate_fold:
            folds = list(np.random.choice(range(0, 9), len(y)))
        else:
            folds = self.get_folds_array(training_files_path + 'foldModelText.dat')

        return np.array(X), np.array(y), label_code, np.array(folds), generate_fold

    def save(self):
        """

        :return:
        """
        return CRFClassifier.save(self, self.filename)

    def load(self):
        """

        :return:
        """
        return CRFClassifier.load(self, self.filename)

    def split_reference(self, reference_str, segment_dict):
        """

        :param reference_str:
        :param segment_dict:
        :return:
        """
        # need to split on `.` but not when it is part of arXiv ID, doi, or page number
        # if there is a arXiv ID, doi, or page remove it, split input, and then put it back
        if len(segment_dict.get('doi', '')) > 0:
            reference_str = self.substitute(segment_dict.get('doi', ''), 'doi_id', reference_str)
        if len(segment_dict.get('arxiv', '')) > 0:
            reference_str = self.substitute(segment_dict.get('arxiv', ''), 'arXiv_id', reference_str)
        if len(segment_dict.get('page', '')) > 0:
            reference_str = self.substitute(segment_dict.get('page', ''), 'page_num', reference_str)
        if len(segment_dict.get('ascl', '')) > 0:
            reference_str = self.substitute(segment_dict.get('ascl', ''), 'ascl_id', reference_str)
        if len(segment_dict.get('unknown_url', '')) > 0:
            reference_str = self.substitute(segment_dict.get('unknown_url', ''), 'unknown_url', reference_str)
        ref_words = []
        for w in self.REFERENCE_TOKENIZER.split(reference_str):
            if w == 'page_num':
                ref_words.append(segment_dict.get('page', ''))
            elif w == 'arXiv_id':
                ref_words.append(segment_dict.get('arxiv', ''))
            elif w == 'doi_id':
                ref_words.append(segment_dict.get('doi', ''))
            elif w == 'ascl_id':
                ref_words.append(segment_dict.get('ascl', ''))
            elif w == 'unknown_url':
                ref_words.append(segment_dict.get('unknown_url', ''))
            elif len(w.strip()) > 0:
                ref_words.append(w.strip())
        return ref_words

    def extract_doi(self, reference_str):
        """

        :param reference_str:
        :return:
        """
        matches = self.DOI_ID_EXTRACTOR.finditer(reference_str)
        for match in matches:
            doi = match.group('doi')
            if doi:
                # becasue the doi format varies we are considering everything after doi or DOI or 10,
                # if by any chance arxiv id is followed by doi, without any comma, or bracket to signal
                # the end of doi, it is considered to be part of doi
                # so far doi and arxiv always came at the end, we are actually ok if arxiv is first
                # however if arxiv appears after doi, as mentioned above, it gets matched as part of doi,
                # in this case need to check for this, also ascl is the same way
                # have seen a few references with having doi and arxiv in the form of url appearing after doi
                # (ie, N. Blagorodnova, S. Gezari, T. Hung, S.R. Kulkarni, S.B. Cenko, D.R. Pasham, L. Yan, I. Arcavi, S. Ben-Ami, B.D. Bue, T. Cantwell, Y. Cao, A.J. Castro-Tirado, R. Fender, C. Fremling, A. Gal-Yam, A.Y.Q. Ho, A. Horesh, G. Hosseinzadeh, M.M. Kasliwal, A.K.H.H. Kong, R.R. Laher, G. Leloudas, R. Lunnan, F.J. Masci, K. Mooley, J.D. Neill, P. Nugent, M. Powell, A.F. Valeev, P.M. Vreeswijk, R. Walters, P. Wozniak, iPTF16fnl: a faint and fast tidal disruption event in an E+A galaxy. The Astrophysical Journal 844(46) (2017). doi:10.3847/1538-4357/aa7579. http://arxiv.org/abs/1703.00965 http://dx.doi.org/10.3847/1538-4357/aa7579)
                if 'https://' in doi:
                    doi = doi.split('https://', 1)[0]
                elif 'http://' in doi:
                    doi = doi.split('http://', 1)[0]
                elif 'arXiv:' in doi:
                    doi = doi.split('arXiv:', 1)[0]
                elif 'ascl:' in doi:
                    doi = doi.split('ascl:', 1)[0]
                if doi.endswith('.'):
                    doi = doi[:-1]
            return doi
        return ''

    def identify_ids(self, reference_str):
        """

        :param reference_str:
        :return:
        """
        # if there is a doi
        doi_id = self.extract_doi(reference_str)
        # if there is arXiv id
        arXiv_id = self.ARXIV_ID_EXTRACTOR.search(reference_str.replace(doi_id, ''))
        if arXiv_id:
            arXiv_id = arXiv_id.group()
        else:
            arXiv_id = ''
        ascl_id = self.ASCL_ID_EXTRACTOR.search(reference_str.replace(arXiv_id, ''))
        if ascl_id:
            ascl_id = ascl_id.group(3)
        else:
            ascl_id = ''
        # TODO: once seen issn in the text reference implement it,
        # for now just included it to be compatible with the xml side
        # TODO: version has been tagged in a training file, we are not
        # using that to identifiy reference yet, so have the placeholder for it now
        return {'arxiv': arXiv_id, 'doi': doi_id, 'ascl': ascl_id, 'issn': '', 'version': ''}

    def identify_numeric_tokens(self, reference_str):
        """

        :param reference_str:
        :return:
        """
        # find the year, could be alphanumeric, so accept them
        # if more than one match found, then remove alphanumeric and see if there is only one to accept
        year = list(OrderedDict.fromkeys(self.YEAR_EXTRACTOR.findall(reference_str)))
        if len(year) > 1:
            year = [y for y in year if y.isnumeric() and int(y) >= self.year_earliest and int(y) <= self.year_now]
        if len(year) == 1:
            year = year[0]
            reference_str = self.substitute(year, '', reference_str)

        # see if can extract numeric based on a patters
        for ne in self.FORMATTED_MULTI_NUMERIC_EXTRACTOR:
            extractor = ne.search(reference_str)
            if extractor:
                volume = extractor.group('volume')
                page = extractor.group('page')
                issue = extractor.group('issue').strip()
                if len(volume) > 0:
                    reference_str = self.substitute(volume, '', reference_str)
                if len(page) > 0:
                    reference_str = self.substitute(page, '', reference_str)
                if len(issue) > 0:
                    reference_str = self.substitute(issue, '', reference_str)
                break
            else:
                volume = page = issue = ''

        # if there is page in the form of start-end or eid in the format of number.number
        if len(page) == 0:
            page = self.PAGE_EXTRACTOR.search(reference_str)
            if page:
                page = page.group('page')
                reference_str = self.substitute(page, '', reference_str)
            else:
                page = ''

        # if there is a volume indicator
        if len(volume) == 0:
            volume = self.VOLUME_EXTRACTOR.search(reference_str)
            if volume:
                volume = volume.group('volume')
                reference_str = self.substitute(volume, '', reference_str)
            else:
                volume = ''

        # the rest, also remove duplicates
        the_rest = list(OrderedDict.fromkeys(self.IS_MOSTLY_DIGIT.findall(reference_str)))
        unknown = ''

        # continue only if need to guess values for one of these fields, otherwise return
        if len(volume) == 0 or len(page) == 0 or len(issue) == 0:
            unknown = ' '.join([elem for elem in self.MATCH_A_WORD.findall(reference_str) if elem not in the_rest and
                                                                                                  not self.is_identifying_word(elem)])
            if len(the_rest) > 0:
                # if volume is not detected yet since it is the first entity and since it has to be an integer,
                # throw every alphanumeric element before it out to start with a numeric value and guess it is
                # volume
                if len(volume) == 0:
                    try:
                        the_rest_numeric = the_rest[the_rest.index(next(elem for elem in the_rest if elem.isdigit())):]
                        unknown = unknown + ' '.join([non_numeric for non_numeric in the_rest if non_numeric not in the_rest_numeric])
                        the_rest = the_rest_numeric
                    except:
                        unknown = unknown + ' '.join(the_rest)
                        the_rest = ''

                # how many numeric value do we have? if more than 3, we have no guesses so return
                if len(the_rest) <= 3:
                    # if we have three elements, both volume and page need to be empty
                    # in this case in order of most likely fields we have volume, issue, page
                    if len(the_rest) == 3 and len(volume) == 0 and len(issue) == 0 and len(page) == 0:
                        volume = the_rest[0]
                        issue = the_rest[1]
                        page = the_rest[2]
                    # if we have two elements, one of volume or page need to be empty
                    elif len(the_rest) == 2 and (len(volume) == 0 or len(page) == 0):
                        # if volume is empty, then most likely the first element is volume
                        # and then depending on if page is empty or not the next element is either page or issue respectively
                        if len(volume) == 0:
                            volume = the_rest[0]
                            if len(page) == 0:
                                page = the_rest[1]
                            else:
                                issue = the_rest[1]
                        # if volume is set, then if page is empty, assign the two elements to page and issue respectively
                        # however if page is set, and there are two elements remaining, cannot tell which could be issue
                        elif len(page) == 0:
                            page = the_rest[1]
                            issue = the_rest[0]
                        else:
                            unknown = ' '.join(the_rest)
                    # if one element is left, the order of most likely is volume if not set, is page if not set, is issue
                    elif len(the_rest) == 1:
                        if len(volume) == 0:
                            volume = the_rest[0]
                        elif len(page) == 0:
                            page = the_rest[0]
                        else:
                            issue = the_rest[0]
                    else:
                        unknown = ' '.join(the_rest)

        return {'page': page, 'year': year, 'volume': volume, 'issue': issue, 'unknown': unknown}

    def if_publisher_get_idx(self, entity_list):
        """
        go through list of elements consist of multiple words
        if all the words in one element are either publisher name or location
        return its index in the entity_list

        :param entity_list:
        :return:
        """
        for i, entity in enumerate(entity_list):
            words = entity.split()
            if len([word for word in words if self.academic_publishers_and_locations_re.search(word) is not None]) == len(words):
                return i
        return -1

    def identify_multi_word_entity(self, reference_str):
        """
        journal, title, and publisher are multi word elements

        :param reference_str:
        :return: [title, journal]
        """
        # if there are any urls remaining in reference_str at this point, remove it
        unknown_url = ''
        extractor = self.URL_EXTRACTOR.search(reference_str)
        if extractor:
            unknown_url = extractor.group()
        # attempt to extract journal abbreviation
        for i, je in enumerate(self.JOURNAL_ONLY_EXTRACTOR):
            extractor = je.match(reference_str)
            if extractor:
                journal = extractor.group('journal').strip()
                if len(journal) > 0:
                    publisher = self.is_publisher_or_location(reference_str.replace(journal, ''))
                    return {'title':'', 'journal':journal, 'publisher':publisher, 'unknown_url':unknown_url}
        # attempt to split on dot and comma, if found, attempt to extract title and journal
        for i, tje in enumerate(self.TITLE_JOURNAL_EXTRACTOR):
            extractor = tje.match(reference_str)
            if extractor:
                title = extractor.group('title').strip()
                journal = extractor.group('journal').strip('"').strip() if extractor.group('journal') is not None else ''
                if len(title) > 0 or (len(journal) > 0 and journal.count(',') == 0):
                    publisher = self.is_publisher_or_location(reference_str.replace(journal, '').replace(title, ''))
                    return {'title':title, 'journal':journal, 'publisher':publisher, 'unknown_url':unknown_url}

        patterns = "NP:{<DT|TO|IN|CC|JJ.?|NN.?|NN..?|VB.?>*}"
        NPChunker = nltk.RegexpParser(patterns)

        # prepare the a_reference
        reference_str = self.CAPITAL_FIRST_CHAR.search(reference_str).group()
        reference_str = self.TITLE_JOURNAL_PUNCTUATION_REMOVER.sub(' ', reference_str).replace(',', '.')
        tree = NPChunker.parse(nltk.tag._pos_tag(nltk.word_tokenize(reference_str), tagger=self.nltk_tagger, lang='eng'))

        # identify noun phrases
        nps = []
        for subtree in tree:
            if type(subtree) == nltk.tree.Tree and subtree.label() == 'NP':
                picks = ' '.join(word
                             if not is_page_number(word) and not bool(self.is_identifying_word(word))
                                 else '' for word, tag in subtree.leaves())
                aleaf = self.SPACE_BEFORE_DOT_REMOVER.sub(r'\1', self.SPACE_AROUND_AMPERSAND_REMOVER.sub(r'\1&\2', picks)).strip(' ')
                if len(aleaf) >= 1 and self.is_punctuation(aleaf) == 0:
                    nps.append(aleaf)

        # attempt to combine abbreviated words that represent journal mostly
        nps_merge = []
        for k, g in groupby(nps, lambda x: bool(self.JOURNAL_ABBREVIATED_EXTRACTOR.match(x))):
            if k:
                nps_merge.append(' '.join(g))
            else:
                nps_merge.extend(g)

        # check for possible publisher
        publisher = ''
        while True:
            idx = self.if_publisher_get_idx(nps_merge)
            if idx >= 0:
                # ided publisher, assign it and remove it
                publisher = publisher + ' ' + nps_merge[idx]
                nps_merge.pop(idx)
            else:
                break
        if len(publisher) > 0:
            title = ' '.join(nps_merge)
            # when there is a publisher, it is more than likely we have a book
            # assign everything to title
            return {'title': title, 'journal': '', 'publisher': publisher.strip(), 'unknown_url':unknown_url}

        # more than likely, if there is one field it is journal
        if len(nps_merge) == 1:
            return {'title': '', 'journal': nps_merge[0], 'publisher': publisher}

        # more than likely, if there are two fields, first is title, and second is journal
        if len(nps_merge) == 2:
            return {'title': nps_merge[0].rstrip('.').rstrip(','), 'journal': nps_merge[1], 'publisher': publisher, 'unknown_url':unknown_url}

        # if still three fields, and publisher is not identified to be one of them
        # more than likely the first one is title, and the last one is journal
        # the middle can be either so leave it alone and let CRF figure it out
        if len(nps_merge) == 3:
            return {'title': nps_merge[0].rstrip('.').rstrip(','), 'journal': nps_merge[2], 'publisher': '', 'unknown_url':unknown_url}

        # unable to guess
        return {'title': '', 'journal': '', 'publisher':'', 'unknown_url':unknown_url}

    def identify_authors(self, reference_str):
        """

        :param reference_str:
        :return:
        """
        try:
            authors = get_authors(reference_str).rstrip()
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

        # if there is no punctuation in the author list and it did not end with `et al.`,
        # whatever comes after authors are included as author.
        # ie, M. Bander Fractional quantum hall effect in nonuniform magnetic fields (1990) Phys. Rev. B41 9028
        # authors= M. Bander Fractional quantum hall effect in nonuniform magnetic fields
        if not self.ETAL_PAT_ENDSWITH.search(authors) and authors.count(',') == 0 and authors.count(';') == 0:
            last_name_prefix = self.LAST_NAME_PREFIX.split('|')
            words = authors.replace('.', '').split()
            last_name = len([x for x in words if x[0].isupper() or x in last_name_prefix])
            if last_name < len(words) - last_name:
                return ''

        return authors

    def identify_editors(self, reference_str, segment_dict):
        """

        :param reference_str:
        :param segment_dict:
        :return:
        """
        editors = ''
        match = self.EDITOR_EXTRACTOR.search(reference_str)
        if match:
            editors = get_editors(match.group(2))
            if editors:
                if editors.endswith(','):
                    editors = editors[:-1]
                reference_str = reference_str.replace(editors, '')
                match = self.EDITOR_RESIDUE.search(reference_str)
                if match:
                    reference_str = reference_str.replace(match.group(), '. ')
        segment_dict.update({'editors':editors})
        return reference_str, segment_dict

    def segment(self, reference_str):
        """

        :param reference_str:
        :return:
        """
        if isinstance(reference_str, list):
            return []

        # segment reference, first by identifying possible author section
        authors = self.identify_authors(reference_str)
        # remove the guessed author section and attempt to identify arxiv/doi ids
        reference_str = reference_str.replace(authors, '')
        segment_dict = {'authors':authors.replace("&", "and")}
        segment_dict.update(self.identify_ids(reference_str))
        reference_str = self.substitute(segment_dict.get('arxiv', ''), '',
                            self.substitute(segment_dict.get('ascl', ''), '',
                                self.substitute(segment_dict.get('doi', ''), '', reference_str)))
        # also identify editors if any
        reference_str, segment_dict = self.identify_editors(reference_str, segment_dict)
        segment_dict.update(self.identify_multi_word_entity(reference_str.strip()))
        # now remove what has been guessed to be part of title/journal/publisher to attempt to identify alphanumeric values
        # also if there was any unknown_url, remove that as well
        identified = '%s %s %s %s'%(segment_dict.get('title', ''), segment_dict.get('journal', ''),
                                    segment_dict.get('publisher', ''), segment_dict.get('unknown_url', ''))
        remove = filter(None, self.MATCH_A_NONE_WORD.split(self.MATCH_PARENTHESIS.sub('', identified)))
        reference_str = self.substitute(remove, '', self.PUNCTUATION_REMOVER_FOR_NUMERIC_ID.sub(' ', reference_str))
        segment_dict.update(self.identify_numeric_tokens(reference_str))
        return segment_dict

    def classify(self, reference_str):
        """
        Run the classifier on input data
        :param reference_str:
        :return: list of words and the corresponding list of labels
        """
        # remove any numbering that appears before the reference to start with authors
        # exception is the year
        if self.START_WITH_YEAR.search(reference_str) is None:
            reference_str = self.START_WITH_AUTHOR.search(reference_str).group()
        # also if for some reason et al. has been put in double quoted! remove them
        reference_str = self.QUOTES_AROUND_ETAL_REMOVE.sub(r"\1\3\5", reference_str)
        # make sure there is a dot after first initial
        reference_str = self.TO_ADD_DOT_AFTER_FIRST_INITIAL.sub(r"\1.\2", reference_str)
        # there are some referneces that first and middle initials are specified toghether without the dot
        reference_str = self.TO_ADD_DOT_AFTER_INITIALS.sub(r"\1.\2.\3", reference_str)
        # if there is a url for DOI turned it to recognizable DOI
        reference_str = self.URL_TO_DOI.sub(r"\1DOI:\5", reference_str)
        # if there is a url for arxiv turned it to recognizable arxiv
        reference_str = self.URL_TO_ARXIV.sub(r"\1arXiv:\5", reference_str)

        for rwb in self.WORD_BREAKER_REMOVE:
            reference_str = rwb.sub('', reference_str)

        doi = self.extract_doi(reference_str)
        if doi:
            # attempt to remove any spaces in doi
            reference_str = reference_str.replace(doi, doi.replace(' ', ''))

        segment_dict = self.segment(reference_str)

        if len(segment_dict.get('arxiv', '')) > 0 or len(segment_dict.get('ascl', '')) > 0 or \
           len(segment_dict.get('doi', '')) > 0 or len(segment_dict.get('page', '')) > 0 or \
           len(segment_dict.get('unknown_url', '')) > 0:
            ref_words = self.split_reference(reference_str, segment_dict)
        else:
            ref_words = filter(None, [w.strip() for w in self.REFERENCE_TOKENIZER.split(reference_str)])

        features = []
        for i in range(len(ref_words)):
            features.append(self.get_data_features(ref_words, i, [], segment_dict))

        ref_labels = self.decoder(self.crf.predict([np.array(features)])[0])
        return ref_words, ref_labels

    def parse(self, reference_str):
        """

        :param reference_str:
        :return:
        """
        words, labels = self.classify(reference_str)
        return self.reference(reference_str, words, labels)

def create_text_model():
    """
    create a crf text model and save it to a pickle file

    :return:
    """
    try:
        start_time = time.time()
        crf = CRFClassifierText()
        if not (crf.create_crf() and crf.save()):
            raise
        current_app.logger.debug("crf text model trained and saved in %s ms" % ((time.time() - start_time) * 1000))
        return crf
    except Exception as e:
        current_app.logger.error('Exception: %s' % (str(e)))
        current_app.logger.error(traceback.format_exc())
        return None

def load_text_model():
    """
    load the text model from pickle file

    :return:
    """
    try:
        start_time = time.time()
        crf = CRFClassifierText()
        if not (crf.load()):
            raise
        current_app.logger.debug("crf text model loaded in %s ms" % ((time.time() - start_time) * 1000))
        return crf
    except Exception as e:
        current_app.logger.error('Exception: %s' % (str(e)))
        current_app.logger.error(traceback.format_exc())
        return None
