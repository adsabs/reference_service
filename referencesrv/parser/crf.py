"""
This module contains classes to train/test/classify
conditional random field machine learning method

"""

import os
import traceback
import numpy as np
import re
import nltk
import time
from pystruct.models import ChainCRF
from pystruct.learners import FrankWolfeSSVM

from flask import current_app

try:
    import cPickle as pickle
except ImportError:
    import pickle

from referencesrv.parser.getDataText import get_arxiv_tagged_data
from referencesrv.parser.numeric import NumericToken
from referencesrv.parser.originator import OriginatorToken
from referencesrv.parser.pub import PubToken
from referencesrv.parser.common import which_punctuation

class CRFClassifierText(object):

    IGNORE_IF = re.compile(r'(in press|submitted|to appear)', flags=re.IGNORECASE)

    QUOTES_AROUND_ETAL_REMOVE = re.compile(r'(.*)(")(et al\.?)(")(.*)', re.IGNORECASE)
    LASTNAME_FIRST = re.compile(r'(^[A-Za-z]{3,})')
    TO_FORMAT_INITIALS_PROPER_LASTNAME_FIRST = re.compile(r'\b(?P<lastname>[A-Za-z]{3,}[,\s]+)(?P<first_initial>[A-Za-z]{1})(?P<middle_initial>[A-Za-z]{1})?(?P<glue>[.,]{1}|\sand)')
    TO_FORMAT_INITIALS_PROPER_LASTNAME_LAST = re.compile(r'\b(?P<first_initial>[A-Za-z]{1})(?P<middle_initial>[A-Za-z]{1})?(?P<lastname>\s[A-Za-z]{3,})(?P<glue>[.,]{1}|\sand)')
    SEPARATE_AUTHOR = re.compile(r'^(.*?)([\d\":]+|et al)(.*)$', flags=re.IGNORECASE)
    TO_REMOVE_HYPEN_NEAR_INITIAL = [re.compile(r'([A-Z]\.)(\-)([A-Z]\.)'), re.compile(r'([A-Z])(\-)(\.)'),
                                    re.compile(r'([A-Z])(\-)([A-Z])\b')]

    URL_EXTRACTOR = re.compile(r'((url\s*)?(http)s?://[A-z0-9\-\.\/\={}?&%]+)', re.IGNORECASE)
    MONTH_NAME_EXTRACTOR = re.compile(r'\b([Jj]an(?:uary)?|[Ff]eb(?:ruary)?|[Mm]ar(?:ch)?|[Aa]pr(?:il)?|[Mm]ay|[Jj]un(?:e)?|[Jj]ul(?:y)?|[Aa]ug(?:ust)?|[Ss]ep(?:tember)?|[Oo]ct(?:ober)?|([Nn]ov|[Dd]ec)(?:ember)?)\b')

    URL_TO_DOI = re.compile(r'((url\s*)?(https\s*:\s*//\s*|http\s*:\s*//\s*)((.*?)doi(.*?)org/))|(DOI:https\s*://\s*)', flags=re.IGNORECASE)
    URL_TO_ARXIV = re.compile(r'((url\s*)?(https://|http://)(arxiv.org/(abs|pdf)/))', flags=re.IGNORECASE)
    URL_TO_ASCL = re.compile(r'((url\s*)?(https://|http://)(ascl.net/))', flags=re.IGNORECASE)
    ADD_COLON_TO_IDENTIFIER = re.compile(r'(\s+(DOI|arXiv|ascl))(:?\s*)', flags=re.IGNORECASE)

    IS_START_WITH_YEAR = re.compile(r'(^[12][089]\d\d)')
    START_WITH_AUTHOR = re.compile(r'([A-Za-z].*$)')

    WORD_BREAKER_REMOVE = [re.compile(r'([A-Za-z]+)([\-]+\s+)([A-Za-z]+)')]

    TOKENS_NOT_IDENTIFIED = re.compile(r'\w+\b(?!\|)')

    REFERENCE_TOKENIZER = re.compile(r'([\s.,():;\[\]\'\"#\/])')
    TAGGED_MULTI_WORD_TOKENIZER = re.compile(r'([\s.,])')

    # is all capital
    IS_ALL_CAPITAL = re.compile(r'^([A-Z]+)$')
    # is only the first character capital
    IS_FIRST_CAPITAL = re.compile(r'^([A-Z][a-z]+)$')
    # is alphabet only, consider hyphenated words also
    IS_ALPHABET = re.compile(r'^(?=.*[a-zA-Z])([a-zA-Z\-]+)$')
    # is numeric only, consider the page range with - being also numeric
    # also include arxiv id with a dot to be numeric
    # note that this differs from function is_numeric in the
    # sense that this recognizes numeric even if it was not identified/tagged
    IS_NUMERIC = re.compile(r'^(?=.*[0-9])([0-9\-\.]+)$')
    # is alphanumeric, must have at least one digit and one alphabet character
    IS_ALPHANUMERIC = re.compile(r'^(?=.*[0-9])(?=.*[a-zA-Z])([a-zA-Z0-9]+)$')

    ADD_SPACE_BETWEEN_TWO_IDENTIFIED_TOKENS = re.compile(r'(\|[a-z\_]+\|)(\|[a-z\_]+\|)')
    REGEX_PATTERN_WHOLE_WORD_ONLY = r'(?:\b|\B)%s(?:\b|\B)'

    nltk_tagger = None
    crf = None
    X = y = label_code = folds = None

    def __init__(self):
        """

        """
        self.originator_token = OriginatorToken(self.REFERENCE_TOKENIZER)
        self.numeric_token = NumericToken()
        self.pub_token = PubToken()
        self.unknown_tokens = []
        self.filename = os.path.dirname(__file__) + '/serialized_files/crfModelText.pkl'

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

        # for now use static division. see comments in foldModelText.dat
        generate_fold = False
        if generate_fold:
            folds = list(np.random.choice(range(0, 9), len(y)))
        else:
            folds = self.get_folds_array(training_files_path + 'foldModelText.dat')

        return np.array(X, dtype=object), np.array(y, dtype=object), label_code, np.array(folds), generate_fold


    def save(self):
        """
        save object to a pickle file
        :return:
        """
        try:
            with open(self.filename, "wb") as f:
                pickler = pickle.Pickler(f, -1)
                pickler.dump(self.crf)
                pickler.dump(self.label_code)
                pickler.dump(self.nltk_tagger)
            current_app.logger.info("saved crf in %s."%self.filename)
            return True
        except Exception as e:
            current_app.logger.error('Exception: %s' % (str(e)))
            current_app.logger.error(traceback.format_exc())
            return False

    def load(self):
        """

        :return:
        """
        try:
            with open(self.filename, "rb") as f:
                unpickler = pickle.Unpickler(f)
                self.crf = unpickler.load()
                self.label_code = unpickler.load()
                self.nltk_tagger = unpickler.load()
            current_app.logger.info("loaded crf from %s."%self.filename)
            return self.crf
        except Exception as e:
            current_app.logger.error('Exception: %s' % (str(e)))
            current_app.logger.error(traceback.format_exc())


    def search(self, pattern, text):
        """
        search whole word only in the text
        :param pattern:
        :param text:
        :return: Ture/False depending if found
        """
        try:
            return re.search(self.REGEX_PATTERN_WHOLE_WORD_ONLY % pattern, text) is not None
        except:
            return False

    def reference(self, refstr, words, labels):
        """
        put identified words into a dict to be passed out

        :param words:
        :param labels:
        :return:
        """
        ref_dict = {}
        ref_dict['authors'] = self.originator_token.collect_tagged_tokens(words, labels)
        if 'DOI' in labels or 'ARXIV' in labels or 'ASCL' in labels:
            ref_dict.update(self.numeric_token.collect_id_tagged_tokens(words, labels))
        if 'YEAR' in labels:
            ref_dict['year'] = words[labels.index('YEAR')]
        if 'VOLUME' in labels:
            volume = self.numeric_token.collect_tagged_numerals_token(words, labels, 'VOLUME')
            if volume:
                ref_dict['volume'] = volume
        if 'PAGE' in labels:
            page = self.numeric_token.collect_tagged_numerals_token(words, labels, 'PAGE')
            if page:
                ref_dict['page'] = page
        if 'ISSUE' in labels:
            ref_dict['issue'] = words[labels.index('ISSUE')]
        if 'ISSN' in labels:
            ref_dict['ISSN'] = words[labels.index('ISSN')]
        if 'JOURNAL' in labels:
            ref_dict['journal'] = self.pub_token.collect_tagged_journal_tokens(words, labels)
        if 'TITLE' in labels:
            title = self.pub_token.collect_tagged_title_tokens(words, labels)
            if title:
                ref_dict['title'] = title
        ref_dict['refstr'] = refstr
        return ref_dict

    def punctuation_features(self, ref_word, ref_label):
        """
        return a feature vector that has 1 in the first cell if ref_word is a punctuation
        followed by 1 in the position corresponding to which one

        :param ref_word:
        :param ref_label:
        :return:
        """
        which = which_punctuation(ref_word, ref_label)
        return [
            1 if which == 0 else 0,   # 0 if punctuation,
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


    def is_token_unknown(self, ref_word, ref_label):
        """

        :param ref_word:
        :param ref_label:
        :return:
        """
        if ref_label:
            return 1 if ref_label == 'NA' else 0

        if ref_word is None:
            return 0
        return int(any(ref_word == token for token in self.unknown_tokens))


    def length_features(self, ref_word):
        """
        distinguish between token of length 1, and longer

        :param ref_word:
        :return:
        """
        return [1 if len(ref_word) == 1 else 0,
                1 if len(ref_word) > 1 else 0]


    def get_data_features(self, ref_word_list, index, ref_label_list=None):
        """

        :param ref_word_list: has the form [e1,e2,e3,..]
        :param index: the position of the word in the set, assume it is valid
        :param ref_label_list: labels for ref_word_list available during training only
        :return:
        """
        ref_word = ref_word_list[index]
        ref_label = ref_label_list[index] if ref_label_list else None
        return \
              self.length_features(ref_word)                                                \
            + self.originator_token.author_features(ref_word_list, ref_label_list, index)   \
            + self.pub_token.title_features(ref_word_list, ref_label_list, index)           \
            + self.pub_token.journal_features(ref_word_list, ref_label_list, index)         \
            + self.numeric_token.numeric_features(ref_word, ref_label)                      \
            + self.numeric_token.identifying_word_features(ref_word, ref_label)             \
            + self.punctuation_features(ref_word, ref_label)                                \
            + self.pub_token.publisher_features(ref_word, ref_label)                        \
            + self.originator_token.editor_features(ref_word_list, ref_label_list, index)   \
            + [
                int(self.IS_ALL_CAPITAL.match(ref_word) is not None),                       # is element all capital
                int(self.IS_FIRST_CAPITAL.match(ref_word) is not None),                     # is first character capital
                int(self.IS_ALPHABET.match(ref_word) is not None),                          # is alphabet only, consider hyphenated words also
                int(self.IS_NUMERIC.match(ref_word) is not None),                           # is numeric only, consider the page range with - being also numeric
                int(self.IS_ALPHANUMERIC.match(ref_word) is not None),                      # is alphanumeric, must at least one digit and one alphabet character
                self.is_token_unknown(ref_word, ref_label),                                 # is it one of the words unable to guess
                self.pub_token.is_token_stopword(ref_word, ref_label),                      # is it one of tagged stopwords
              ]


    def segment(self, reference_str):
        """
        going to attempt and segment the reference string
        each token that is identified is removed from reference_str
        in the reverse order the identified tokens are inserted back to reference_str
        before feature extraction

        :param reference_str:
        :return:
        """
        if isinstance(reference_str, list):
            return []

        # start fresh
        self.numeric_token.clear()
        self.originator_token.clear()
        self.pub_token.clear()
        na_url = None
        na_month = None

        # step 1: remove any non essential tokens (ie, urls, months, etc)
        matches = self.URL_EXTRACTOR.findall(reference_str)
        if len(matches) > 0:
            na_url = []
            for i, url in enumerate(matches, start=1):
                na_url.append(url[0])
                reference_str = reference_str.replace(url[0], '|na_url_%d|'%i)
        extractor = self.MONTH_NAME_EXTRACTOR.search(reference_str)
        if extractor:
            na_month = extractor.group().strip()
            reference_str = reference_str.replace(na_month, '|na_month|')

        # step 2: identify doi/arxiv/ascl
        reference_str = self.numeric_token.segment_ids(reference_str)

        # step 3: identify list of authors and editors
        reference_str = self.originator_token.identify(reference_str)

        # step 4: identify title and journal substrings
        # but first remove any numerical identifying words
        reference_str = self.pub_token.identify(self.numeric_token.remove_identifying_words(reference_str).strip(),
                                                self.nltk_tagger,
                                                self.originator_token.indices(),
                                                self.originator_token.have_editor())

        # step 5: identify year, volume, page, issue
        reference_str = self.numeric_token.segment_numerals(reference_str)

        # collect all tokens that has not been identified
        self.unknown_tokens = self.TOKENS_NOT_IDENTIFIED.findall(reference_str)
        if na_url:
            self.unknown_tokens.append(' '.join(na_url))
        if na_month:
            self.unknown_tokens.append(na_month)

        # now put the identified tokens back into the string, and before tokenizing and sending to crf

        # step 5 reverse
        reference_str = self.numeric_token.assemble_stage1(reference_str)

        # step 4 reverse
        reference_str = self.pub_token.assemble(reference_str)

        # step 3 reverse
        reference_str = self.originator_token.assemble(reference_str)

        # tokenize
        ref_words = list(filter(None, [w.strip() for w in self.REFERENCE_TOKENIZER.split(
                                            self.ADD_SPACE_BETWEEN_TWO_IDENTIFIED_TOKENS.sub(r'\1 \2', reference_str))]))

        # step 2 reverse
        ref_words = self.numeric_token.assemble_stage2(ref_words)

        # step 1 reverse
        if na_month:
            ref_words[ref_words.index('|na_month|')] = na_month
        if na_url:
            for i, url in enumerate(na_url, start=1):
                ref_words[ref_words.index('|na_url_%d|'%i)] = url

        return ref_words


    def author_initials_proper(self, reference_str):
        """
        make sure author initials is formatted properly, capitalized, with dot, first and middle separate

        :param reference_str:
        :return:
        """
        def replacement_lastname_first(match):
            """
            add space and dots after initials if need to

            :param match:
            :return:
            """
            lastname = match.group('lastname').capitalize()
            first_initial = match.group('first_initial').upper()
            middle_initial = match.group('middle_initial').upper() if match.group('middle_initial') else None
            glue = match.group('glue').lstrip('.') if match.group('glue') else None
            if middle_initial:
                # negative lookahead did not work in re, so have to go this way
                if (first_initial + middle_initial).lower() == 'jr':
                    return match.groups(0)
                return r"{lastname}{first_initial}. {middle_initial}.{glue}".format(
                    lastname=lastname, first_initial=first_initial, middle_initial=middle_initial, glue=glue)
            return r"{lastname}{first_initial}.{glue}".format(
                lastname=lastname, first_initial=first_initial, glue=glue)

        def replacement_lastname_last(match):
            """
            add space and dots after initials if need to

            :param match:
            :return:
            """
            first_initial = match.group('first_initial').upper()
            middle_initial = match.group('middle_initial').upper() if match.group('middle_initial') else None
            glue = match.group('glue') if match.group('glue') else None
            lastname = match.group('lastname').lstrip().capitalize()
            if middle_initial:
                # negative lookahead did not work in re, so have to go this way
                if (first_initial + middle_initial).lower() == 'jr':
                    return match.groups(0)
                return r"{first_initial}. {middle_initial}. {lastname}{glue}".format(
                    first_initial=first_initial, middle_initial=middle_initial, lastname=lastname, glue=glue)
            return r"{first_initial}. {lastname}{glue}".format(
                first_initial=first_initial, lastname=lastname, glue=glue)

        try:
            author_part = self.SEPARATE_AUTHOR.search(reference_str).group(1).rstrip('.')
            # separate first and middle initials if there are any attached, add dot after each
            # make sure there is a dot after single character, repeat to capture middle name
            # first see what pattern do we have, last name first, or initials first
            if self.LASTNAME_FIRST.search(author_part):
                reference_str = reference_str.replace(author_part,
                                    self.TO_FORMAT_INITIALS_PROPER_LASTNAME_FIRST.sub(replacement_lastname_first, author_part))
            else:
                reference_str = reference_str.replace(author_part,
                                    self.TO_FORMAT_INITIALS_PROPER_LASTNAME_LAST.sub(replacement_lastname_last, author_part))
        except:
            pass

        return reference_str

    def pre_processing(self, reference_str):
        """
        
        :param reference_str: 
        :return: 
        """
        # remove any numbering that appears before the reference to start with authors
        # exception is the year
        if self.IS_START_WITH_YEAR.search(reference_str) is None:
            reference_str = self.START_WITH_AUTHOR.search(reference_str).group()

        # also if for some reason et al. has been put in double quoted! remove them
        reference_str = self.QUOTES_AROUND_ETAL_REMOVE.sub(r"\1\3\5", reference_str)
        # if there is a hypen either between initials, or after initials and before dot, remove it
        for rhni, replace in zip(self.TO_REMOVE_HYPEN_NEAR_INITIAL, [r"\1 \3", r"\1\3", r"\1. \3"]):
            reference_str = rhni.sub(replace, reference_str)
        # add dots after initials, separate first and middle if needed
        reference_str = self.author_initials_proper(reference_str)
        # if no colon after the identifer, add it in
        reference_str = self.ADD_COLON_TO_IDENTIFIER.sub(r"\1:", reference_str)
        # if there is a url for DOI turned it to recognizable DOI
        reference_str = self.URL_TO_DOI.sub(r"DOI:", reference_str)
        # if there is a url for arxiv turned it to recognizable arxiv
        reference_str = self.URL_TO_ARXIV.sub(r"arXiv:", reference_str)
        # if there is a url for ascl turned it to recognizable ascl
        reference_str = self.URL_TO_ASCL.sub(r"ascl:", reference_str)

        for rwb in self.WORD_BREAKER_REMOVE:
            reference_str = rwb.sub(r'\1\3', reference_str)

        return reference_str
    

    def classify(self, reference_str):
        """
        Run the classifier on input data
        
        :param reference_str:
        :return: list of words and the corresponding list of labels
        """
        reference_str = self.pre_processing(reference_str)
        ref_words = self.segment(reference_str)

        features = []
        for i in range(len(ref_words)):
            features.append(self.get_data_features(ref_words, i, []))

        ref_labels = self.decoder(self.crf.predict([np.array(features)])[0])
        return ref_words, ref_labels


    def parse(self, reference_str):
        """

        :param reference_str:
        :return:
        """
        if self.IGNORE_IF.search(reference_str):
            return None
        words, labels = self.classify(reference_str)
        return self.reference(reference_str, words, labels)


    def tokenize(self, reference_str):
        """
        used for unittest only

        :param reference_str:
        :return:
        """
        if self.IGNORE_IF.search(reference_str):
            return None
        words, _ = self.classify(reference_str)
        return words


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
