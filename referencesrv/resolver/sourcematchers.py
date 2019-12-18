"""
This module contains the source matcher, a class to turn strings
people use to reference publications into bibstems.

"""

import os
import re
import time
import traceback

try:
    import cPickle as pickle
except ImportError:
    import pickle

from flask import current_app
from referencesrv.resolver import pytrigdict

class Error(Exception):
    pass

class SourceMatcher(object):
    """An abstract base for all source matchers.

    All getXXX methods return lists of bibstems;  since it is (unfortunately)
    well possible that two different publications have a common title,
    there is no point in having interfaces not returning sequences.
    """
    def exactmatch(self, source_spec):
        """
        Returns a list of bibstems if source_spec matches an entry
        in self's data exatly, None otherwise.
        
        :param source_spec: 
        :return: 
        """
        raise Error, 'exactmatch not implemented for this SourceMatcher'

    def bestmatches(self, source_spec, num_best):
        """
        returns the up to num_best best matches for source_spec in a
        list of tuples (score, bibstem).  Doubles may be present, and
        no order should be assumed.
        
        :param source_spec: 
        :param num_best: 
        :return: 
        """
        raise Error, 'bestmatches not implemented for this SourceMatcher'

    def is_conf_stem(self, stem):
        """
        returns True if we believe stem belongs to a conference.  It
        doesn't really belong here, but since the only information
        source of this is the files that are used to build a SourceMatcher,
        we're handling it here, anyway.
        
        :param stem: 
        :return: 
        """
        raise Error, 'is_conf_stem not implemented for this SourceMatcher'

    def __getitem__(self, source_spec):
        """
        returns a list of (score, bibstem) for the best match for source_spec
        
        :param source_spec: 
        :return: 
        """
        raise Error, '__getitem__ not implemented for this SourceMatcher'

class TrigdictSourceMatcher(SourceMatcher):
    """A SourceMatcher using a combined trigram and Levenshtein string edit 
    distance ranking.  
    
    It may be constructed with a list of paths to the authority files.  
    These have to be in the format

    <ignored>\\n(<authline>\\n)+
    with <authline> either
    <bibstem>\\t<pubType>\\t<source name>
    or
    <bibstem>\\t<source name>

    PubType is a char specifying that the bibstem refers to a conference (C) or
    to something else (R, J).  If files in the second format are given,
    bibstems in them are assumed to be conferences if the string
    "conferences" appears in their file name.

    If constucted without an argument, this uses the default ADS bibstem
    definitions.
    """
    def __init__(self, authority_files=None, load_sources=True):
        """

        :param authority_files:
        """
        if authority_files is not None:
            self.authority_files = authority_files
        else:
            self.authority_files = [os.path.dirname(__file__) + '/sourcematcher_dat/' + s
                    for s in ['journals.dat',
                              'journals_abbrev.dat',
                              'conferences.dat',
                              'conferences_abbrev.dat',
                              'preprints.dat',
                              'aps_abbrev.dat',
                              'bibstems.dat' ]]
        if load_sources:
            self.bibstem_words = {}
            self.load_sources()

    def add_pub(self, stem, source):
        """
        enters stem as value for source.

        :param stem:
        :param source:
        :return:
        """
        key = re.sub('[^A-Za-z0-9&]+', ' ', source).strip().upper()
        self.source_dict[key] = stem
        self.bibstem_words.setdefault(stem, set()).update(key.lower().split())

    def load_two_part_source(self, source_filename, source_lines):
        """
        helps for load_one_source.

        :param source_filename:
        :param source_lines:
        :return:
        """
        read_with_errors = False
        lineno = 1
        confstems_type = 0
        if source_filename.find('conferences')!=-1:
            confstems_type = 1
        for ln in source_lines:
            lineno += 1
            try:
                stem, source = ln.split('\t', 1)
                stem = stem.strip()[-9:]
                # bibstem is at least 3 characters
                if len(stem.strip()) < 3:
                    current_app.logger.error('sourcematchers.py: warning: skipping entry %s in file %s\n'%(ln.strip(),source_filename))
                    read_with_errors = True
                    continue
                self.add_pub(stem, source)
                if confstems_type:
                    self.confstems[stem] = 1
            except ValueError:
                current_app.logger.error('sourcematchers.py: %s (%d): skipping source line: %s'%(source_filename,lineno,ln))
                read_with_errors = True
        return read_with_errors

    def load_three_part_source(self, source_filename, source_lines):
        """
        is a helper for load_one_source.

        :param source_filename:
        :param source_lines:
        :return:
        """
        read_with_errors = False
        lineno = 1
        for ln in source_lines:
            lineno += 1
            try:
                stem, pubType, source = ln.split('\t', 2)
                stem = stem.strip()[-9:]
                if len(stem.strip()) < 3:
                    current_app.logger.error('sourcematchers.py: warning: skipping entry %s in file %s\n'%(ln.strip(),source_filename))
                    read_with_errors = True
                    continue
                self.add_pub(stem, source)
                if pubType=='C':
                    self.confstems[stem] = 1
            except ValueError:
                current_app.logger.error('sourcematchers.py: %s (%d): skipping source line: %s'%(source_filename,lineno,ln))
                read_with_errors = True
        return read_with_errors

    def load_one_source(self, source_filename):
        """
        handles one authority file including format auto-detection.

        :param source_filename:
        :return:
        """
        source_lines = open(source_filename).readlines()
        del source_lines[0]
        if len(source_lines[0].split('\t'))==2:
            return self.load_two_part_source(source_filename, source_lines)
        elif len(source_lines[0].split('\t'))==3:
            return self.load_three_part_source(source_filename, source_lines)
        else:
            raise Error, '%s does not appear to be a source authority file'%(source_filename)

    def load_sources(self):
        """
        creates a trigdict and populates it with data from self.autorityFiles

        :return:
        """
        self.confstems = {}
        self.source_dict = pytrigdict.Trigdict()
        for filename in self.authority_files:
            self.load_one_source(filename)
        # We want to allow naked bibstems in references, too
        for stem in list(self.source_dict.values()):
            clean_stem = stem.replace('.', '').upper()
            self.add_pub(clean_stem, stem)

    def exactmatch(self, source_spec):
        """
        Returns a bibcode if source_spec matches an entry in self's data
        exatly, None otherwise.

        :param source_spec:
        :return:
        """
        return self.source_dict.exactmatch(source_spec)

    def bestmatches(self, source_spec, num_best):
        """
        returns the up to num_best best matches for source_spec in a
        list of tuples (score, bibstem).  Doubles may be present, and
        no order should be assumed.

        :param source_spec:
        :param num_best:
        :return:
        """
        return self.source_dict.bestmatches(source_spec, num_best)

    def is_conf_stem(self, stem):
        """
        see SourceMatcher.is_conf_stem.

        :param stem:
        :return:
        """
        return self.confstems.has_key(stem)

    def __getitem__(self, source_spec):
        """
        returns the (score, bibstem) for the best match for source_spec

        :param source_spec:
        :return:
        """
        return self.source_dict[source_spec]

    def has_key(self, stem):
        """

        :param stem:
        :return:
        """
        return self.source_dict.has_key(stem)

source_matcher_pickle_file = os.path.dirname(__file__) + '/serialized_files/sourceMatcher.pkl'

def create_source_matcher():
    """
    create TrigdictSourceMatcher object and save it to a pickle file

    :return:
    """
    try:
        start_time = time.time()
        source_matcher = TrigdictSourceMatcher()
        with open(source_matcher_pickle_file, "wb") as f:
            pickler = pickle.Pickler(f, -1)
            pickler.dump(source_matcher.source_dict)
            pickler.dump(source_matcher.bibstem_words)
            pickler.dump(source_matcher.confstems)
            current_app.logger.info("saved source_matcher in %s."%source_matcher_pickle_file)
            current_app.logger.debug("source matcher files processed and saved in %s ms" % ((time.time() - start_time) * 1000))
            return source_matcher
    except Exception as e:
        current_app.logger.error('Exception: %s' % (str(e)))
        current_app.logger.error(traceback.format_exc())
        return None

def load_source_matcher():
    """
    load TrigdictSourceMatcher object from pickle file

    :return:
    """
    try:
        start_time = time.time()
        source_matcher = TrigdictSourceMatcher(load_sources=False)
        with open(source_matcher_pickle_file, "rb") as f:
            unpickler = pickle.Unpickler(f)
            source_matcher.source_dict = unpickler.load()
            source_matcher.bibstem_words = unpickler.load()
            source_matcher.confstems = unpickler.load()
            current_app.logger.info("loaded source_matcher from %s."%source_matcher_pickle_file)
            current_app.logger.debug("source matcher loaded in %s ms" % ((time.time() - start_time) * 1000))
            return source_matcher
    except Exception as e:
        current_app.logger.error('Exception: %s' % (str(e)))
        current_app.logger.error(traceback.format_exc())
        return None
