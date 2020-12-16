# -*- coding: utf-8 -*-
import sys, os
project_home = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../'))
if project_home not in sys.path:
    sys.path.insert(0, project_home)

from flask_testing import TestCase
import unittest

import re

import referencesrv.app as app
from referencesrv.resolver.authors import get_author_pattern, get_authors, normalize_single_author, \
    normalize_author_list, get_first_author, get_first_author_last_name, count_matching_authors, \
    add_author_evidence
from referencesrv.resolver.common import Evidences, NotResolved, Undecidable, NoSolution, DeferredSourceMatcher, \
    SOURCE_MATCHER, Solution, Hypothesis
from referencesrv.resolver.pytrigdict import get_trigrams, TrigIndex, Trigdict
from referencesrv.resolver.sourcematchers import TrigdictSourceMatcher, SourceMatcher
from referencesrv.resolver.scoring import get_score_for_reference_identifier, get_score_for_input_fields, \
    get_score_for_reference_identifier, get_book_score_for_input_fields, get_thesis_score_for_input_fields
from referencesrv.resolver.journalfield import get_best_bibstem_for, add_volume_evidence, clean_ads_page, \
    compute_page_delta, add_page_evidence, compute_pubstring_statistics, string_similarity, add_publication_evidence, \
    has_word, has_thesis_indicators, cook_title_string
from referencesrv.resolver.solve import make_solr_condition, inspect_doubtful_solutions, inspect_ambiguous_solutions, \
    choose_solution, solve_reference
from referencesrv.resolver.hypotheses import Hypotheses
from referencesrv.resolver.solrquery import Querier
from referencesrv.resolver.specialrules import iter_journal_specific_hypotheses, get_score_for_baas_match
from referencesrv.resolver.sourcematchers import load_source_matcher


class TestResolver(TestCase):

    def create_app(self):
        self.current_app = app.create_app(**{
            'REFERENCE_SERVICE_LIVE': False
           })
        return self.current_app

    def test_get_author_pattern(self):
        """
        Test the return value to be re.compile
        """
        ref_string = "Demleitner, M., Accomazzi, A., Eichhorn, G., et al. 2001, Astronomical Data Analysis Software and Systems X, 238, 321"
        retype = type(re.compile('hello, world'))

        self.assertEqual(isinstance(get_author_pattern(ref_string), retype), True)


    def test_get_authors(self):
        """
        test get_authors
        """
        # when there is no comma before the and
        self.assertEqual(get_authors(u'S. Kung and F. Bayer: "Collected Junk", A&A 2009'), 'S. Kung and F. Bayer')
        # when there is a comma after both lastname and first initials
        self.assertEqual(get_authors(u'Przybilla, N., & Maeder, A. 2010'), 'Przybilla, N., & Maeder, A.')
        # when initials are trailing and there is no dot, recognized first author lastname only
        self.assertEqual(get_authors(u'Przybilla N & Maeder A 2010'), 'Przybilla')
        # when initials are leading and there are no dots, recognized first author lastname only
        self.assertTrue(get_authors('N Przybilla & A Maeder 2010'), 'Przybilla')
        # where there is a `Collaboration` and also `and xxx colleagues` in the list of authors
        self.assertEqual(get_authors(u'Gaia Collaboration, and 625 colleagues 2016. The Gaia mission. Astronomy and Astrophysics 595, A1.'),
                         'Gaia Collaboration, and 625 colleagues')
        # where there is a `co-authors` in the list of authors
        self.assertEqual(get_authors(u'N., Zhao, Y., Diaz-Santos, T., and 18 co-authors, 2017, "ApJS" 230, 1'),
                         'N., Zhao, Y., Diaz-Santos, T., and 18 co-authors')


    def test_normalize_single_author(self):
        """
        Test the return value of a normalized form for a single author string
        """
        ref_string = "Henneken, E.~A., Muench, G., Holm Nielsen, L., Blanco-Cuaresma, S., Accomazzi, A. 2019. Capturing Software Citations in Astronomy and Planetary Sciences. Lunar and Planetary Science Conference 1569."
        normalized = "henneken, e.~a., muench, g., holm nielsen, l., blanco cuaresma, s., accomazzi, a. 2019. capturing software citations in astronomy and planetary sciences. lunar and planetary science conference 1569."
        self.assertEqual(normalize_single_author(ref_string), normalized)


    def test_normalize_author_list(self):
        """
        Ensure that authorString is returned in the form AuthorLast1; AuthorLast2
        """
        self.assertEqual(normalize_author_list("Foo, N.A., Bar, C. K. "), 'Foo, N.A.; Bar, C. K.')
        self.assertEqual(normalize_author_list("N.A. Foo and C. K. Bar"), 'Foo, N.A.; Bar, C. K.')
        self.assertEqual(normalize_author_list("M. d'Alembert & K.V.U. vanBeuren"), "d'Alembert, M.; vanBeuren, K.V.U.")
        self.assertEqual(normalize_author_list("L. von Beethoven-Tschaikowski et al."), 'von Beethoven-Tschaikowski, L.')
        self.assertEqual(normalize_author_list("Abazajian, K. N., Adelman-McCarthy, J. K."), 'Abazajian, K. N.; Adelman-McCarthy, J. K.')
        self.assertEqual(normalize_author_list("Foo, N.A., Bar, C. K. ", initials=False), 'Foo; Bar')
        self.assertEqual(normalize_author_list("N.A. Foo and C. K. Bar", initials=False), 'Foo; Bar')
        self.assertEqual(normalize_author_list("M. de Alembert & K.V.U. vanBeuren", initials=False), 'de Alembert; vanBeuren')
        self.assertEqual(normalize_author_list("L. von Beethoven-Tschaikowski et al.", initials=False), 'von Beethoven-Tschaikowski')
        self.assertEqual(normalize_author_list("Lastname maybe or not", initials=False), "Lastname")
        self.assertEqual(normalize_author_list("lastname maybe or not", initials=False), "lastname maybe or not")

    def test_get_first_author(self):
        """
        Ensure that the return value is the last name of the first author in authorString.
        """
        with self.assertRaises(Exception) as context:
            get_first_author("")
        self.assertTrue('Both leading and trailing found without a majority' in context.exception)

        self.assertEqual(get_first_author("Joy, K.-C."), 'Joy')
        self.assertEqual(get_first_author("K.-C. Joy", initials=True), 'Joy, K.-C.')


    def test_get_first_author_last_name(self):
        """
        Ensure that the return value is the last name of the first author of the normalised authors in authors string.
        """
        self.assertEqual(get_first_author_last_name("Foo, Z.-H.; Bar, G."), 'Foo')
        self.assertEqual(get_first_author_last_name(None), None)


    def test_count_matching_authors(self):
        """
        Verifies that statistics returned on the authors matching between ref_authors and ads_authors is correct.
        """
        self.assertEqual(count_matching_authors("Abraham, Z ; Iben, I", ['Abraham, Zulema', 'Iben, Icko, Jr.']),
                         (0, 0, 2, False))
        self.assertEqual(count_matching_authors("Iben, I; Abraham, Z", ['Abraham, Zulema', 'Iben, Icko, Jr.']),
                         (0, 0, 2, False))
        self.assertEqual(count_matching_authors("Abraham, Z", ['Abraham, Zulema', 'Iben, Icko, Jr.']),
                         (1, 0, 1, False))
        self.assertEqual(count_matching_authors("Abraham, Z, Noname", ['Abraham, Zulema', 'Iben, Icko, Jr.']),
                         (1, 1, 1, False))
        self.assertEqual(count_matching_authors("Foobar, K.C.D., Noname", ['Abraham, Zulema', 'Iben, Icko, Jr.']),
                         (2, 2, 0, True))
        self.assertEqual(count_matching_authors("Z. Abraham, I. Iben", ['Abraham, Zulema', 'Iben, Icko, Jr.']),
                         (0, 0, 2, False))
        with self.assertRaises(Exception) as context:
            count_matching_authors("Abraham, Z ; Iben, I", None)
        self.assertTrue('ADS paper without authors -- what should we do?' in context.exception)


    def test_add_author_evidence(self):
        """
        Test adding an evidence for ref_authors matching ads_authors.
        """
        # one author match
        evidences = Evidences()
        add_author_evidence(evidences, 'Lefkimmiatis, S.', ['lefkimmiatis, s', 'unser, m'], 'lefkimmiatis, s', False)
        self.assertEqual(evidences['authors'], 0.5)

        # first author missing
        evidences = Evidences()
        add_author_evidence(evidences, 'Lefkimmiatis, S.', ['lefkimmiatis, s', 'unser, m'], 'Foo', False)
        self.assertEqual(evidences['authors'], 0.15)

        # has etal
        evidences = Evidences()
        add_author_evidence(evidences, 'L.Zhong', ['zheng, m', 'chen, w', 'zhang, x', 'liu, x', 'wu, q', 'yu, j'], 'zheng, m', True)
        self.assertEqual(evidences['authors'], 0)


    def test_get_trigrams(self):
        """
        test trigrams present in a_string.
        """
        self.assertEqual(get_trigrams("ab"), [])
        self.assertEqual(get_trigrams("abc"), ['abc'])
        self.assertEqual(get_trigrams("acab aca"), ['aca', 'cab', 'ab ', 'b a', ' ac', 'aca'])


    def test_TrigIndex_lookup(self):
        """
        Test the lookup method which is the index that determine the
        n expansions that have the most trigrams in common with its first
        argument.  It should return a list of these expansions.
        """
        ti = TrigIndex(["abcd", "bcde", "zzy cde"])
        self.assertEqual(ti.lookup("abc cde", 4),
                        [('abcd', 0.6326530612244898), ('bcde', 0.6326530612244898), ('zzy cde', 0.6938775510204082)])
        self.assertEqual(ti.lookup("abc cde", 1),
                         [('zzy cde', 0.6938775510204082)])
        self.assertEqual(ti.lookup("knall", 10), [])

    def test_Trigdict(self):
        """
        Test Trigdic class
        """
        d = Trigdict()
        d["KL"], d["KLOM"], d["KLOM"] = "Short", "Hallo", "Second"
        d["AKLOM"], d["PKLOP"], d["PKLOA"] = "Hillo", "Hullo", "pHullo"
        self.assertEqual(d["KL"], [(1, 'Short')])
        self.assertEqual(d["KLOM"], [(1.0, 'Hallo'), (1.0, 'Second')])
        self.assertEqual(d["PKLOOO"], [(0.7777777777777778, 'Hullo')])
        self.assertEqual(str(d.bestmatches("KLOMA", 3)),
                         "[(0.6799999999999999, 'pHullo'), (0.76, 'Hillo'), (0.88, 'Hallo'), (0.88, 'Second')]")
        self.assertEqual(d.exactmatch("PKLOA"), [(1, 'pHullo')])
        self.assertEqual(d.exactmatch("PKLOOO"), None)
        self.assertEqual(d.values(), set(['Hallo', 'Second', 'Hullo', 'pHullo', 'Hillo']))


    def test_SourceMatcher(self):
        """
        Test the parent class SourceMatcher
        """
        s = SourceMatcher()
        with self.assertRaises(Exception) as context:
            s.exactmatch("A&A")
        self.assertTrue('exactmatch not implemented for this SourceMatcher' in context.exception)
        with self.assertRaises(Exception) as context:
            s.bestmatches("A&A", 2)
        self.assertTrue('bestmatches not implemented for this SourceMatcher' in context.exception)
        with self.assertRaises(Exception) as context:
            s.is_conf_stem("A&A")
        self.assertTrue('is_conf_stem not implemented for this SourceMatcher' in context.exception)
        with self.assertRaises(Exception) as context:
            s["A&A"]
        self.assertTrue('__getitem__ not implemented for this SourceMatcher' in context.exception)


    def test_TrigdictSourceMatcher(self):
        """
        Test TrigdictSourceMatcher class
        """
        s = TrigdictSourceMatcher()
        self.assertEqual(s["A&A"][0][0], 1.0)
        self.assertEqual(s["...."], [])
        self.assertEqual(s.is_conf_stem('A&AS.....'), False)
        self.assertEqual(s.is_conf_stem('LPI......'), True)

        # pass in the files
        authority_files = [os.path.abspath(os.path.join(__file__ ,'../../..')) + '/resolver/sourcematcher_dat/' + s
                               for s in ['journals.dat',
                                         'journals_abbrev.dat',
                                         'conferences.dat',
                                         'conferences_abbrev.dat',
                                         'preprints.dat',
                                         'bibstems.dat',
                                         'journals_not_ADS.dat']]
        s = TrigdictSourceMatcher(authority_files)
        self.assertEqual(s.exactmatch("A&A")[0][0], 1.0)
        self.assertEqual(s.exactmatch("Ap J"), None)


    def test_exactmatch(self):
        """
        test exact match, verify that the score is 1.0 if found and if not found should return None
        """
        s = TrigdictSourceMatcher()
        self.assertEqual(s.exactmatch("A&A")[0][0], 1.0)
        self.assertEqual(s.exactmatch("Ap J"), None)


    def test_bestmatches(self):
        """
        test best matches, verify that best matches for Astronomy and Astrophysics Supplement
        includes the following:
        [(0.8977355734112491, 'aard.conf', 'ASTRONOMY AND ASTROPHYSICS RECENT DEVELOPMENTS'),
         (0.9013878743608473, 'A&AS.....', 'ASTRON & ASTROPHYS SUPPLEMENT'),
         (0.912344777209642,  'aap..rept', 'ASTRONOMY AND ASTROPHYSICS PANEL REPORTS'),
         (0.912344777209642,  'aap..rept', 'ASTRONOMY AND ASTROPHYSICS PANEL REPORTS'),
         (0.9196493791088386, 'AASPP....', 'ASTRONONOMY AND ASTROPHYSICS SERIES'),
         (0.9196493791088386, 'AASPP....', 'ASTRONONOMY AND ASTROPHYSICS SERIES'),
         (0.9211102994886778, 'A&ARv....', 'ASTRONOMY AND ASTROPHYSICS REVIEW'),
         (0.9211102994886778, 'A&ARv....', 'ASTRONOMY AND ASTROPHYSICS REVIEW'),
         (0.9211102994886778, 'A&ARv....', 'ASTRONOMY AND ASTROPHYSICS REVIEW'),
         (0.9298758217677137, 'JApAS....', 'JOURNAL OF ASTROPHYSICS AND ASTRONOMY SUPPLEMENT'),
         (0.9517896274653032, 'A&AS.....', 'ASTRON AND ASTROPHYS SUPPLEMENT'),
         (0.9722425127830533, 'ChJAS....', 'CHINESE JOURNAL OF ASTRONOMY AND ASTROPHYSICS SUPPLEMENT'),
         (0.9897735573411249, 'A&AS.....', 'ASTRONOMY AND ASTROPHYSICS SUPPLEMENT SERIES'),
         (0.9897735573411249, 'A&AS.....', 'ASTRONOMY AND ASTROPHYSICS SUPPLEMENT SERIES'),
         (1.0,                'A&AS.....', 'ASTRONOMY AND ASTROPHYSICS SUPPLEMENT')]
        """
        s = TrigdictSourceMatcher()
        best_matches = s.bestmatches("Astronomy and Astrophysics Supplement", 10)
        print best_matches
        self.assertTrue(len(filter(lambda x: x[1] == 'A&AS.....', best_matches)) > 0)
        self.assertTrue(len(filter(lambda x: x[1] == 'ChJAS....', best_matches)) > 0)
        self.assertTrue(len(filter(lambda x: x[1] == 'JApAS....', best_matches)) > 0)
        self.assertTrue(len(filter(lambda x: x[1] == 'aap..rept', best_matches)) > 0)
        self.assertTrue(len(filter(lambda x: x[1] == 'aard.conf', best_matches)) > 0)
        bestmatches = s.bestmatches("Ap J", 3)
        self.assertTrue(len(filter(lambda x: x[0] == 1.0 and x[1] == 'ApJ......', bestmatches)) == 1)


    def test_authority_files_errors(self):
        """
        test that if there is any problem in the authority files it is captured
        """
        s = TrigdictSourceMatcher()
        self.assertEqual(s.load_one_source(os.path.dirname(__file__) + '/stubdata/bibstems.dat'), True)
        filename = os.path.dirname(__file__) + '/stubdata/conferences.dat'
        with self.assertRaises(Exception) as context:
            s.load_one_source(filename)
        self.assertTrue('Some entries in %s have errors and were skipped'%(filename) in context.exception)
        filename = os.path.dirname(__file__) + '/stubdata/foo.dat'
        with self.assertRaises(Exception) as context:
            s.load_one_source(filename)
        self.assertTrue('%s does not appear to be a source authority file'%(filename) in context.exception)


    def test_DeferredSourceMatcher(self):
        """
        test DeferredSourceMatcher class
        """
        sm = DeferredSourceMatcher()
        self.assertEqual(sm.__bases__, (object,))
        self.assertEqual(sm.__name__, 'Unready source matcher')
        self.assertEqual(SOURCE_MATCHER.__name__, 'Unready source matcher')


    def test_Evidences(self):
        """
        test the Evidences class
        """
        e1 = Evidences()
        e1.add_evidence(1, 'bibcode')
        e2 = Evidences()
        e2.add_evidence(0, 'bibcode')
        self.assertEqual(e1 < e2, False)
        self.assertEqual(e1 < None, False)
        self.assertEqual(e1 <= e2, False)
        self.assertEqual(e1 <= None, False)
        self.assertEqual(e1 > e2, True)
        self.assertEqual(e1 > None, True)
        self.assertEqual(e1 >= e2, True)
        self.assertEqual(e1 >= None, True)
        self.assertEqual(e1 == e2, False)
        self.assertEqual(e1 == None, False)
        self.assertEqual(len(e1), 1)
        self.assertEqual(str(e2), 'Evidences(bibcode=0)')
        e2.add_evidence(1, 'year')
        e2.add_evidence(0.5, 'author')
        self.assertEqual(e2.sum(), 1.5)
        e3 = Evidences()
        self.assertEqual(e3.get_score(), None)
        self.assertEqual(e3.has_veto(), False)
        e3.add_evidence(0, 'bibcode')
        self.assertEqual(e3.has_veto(), True)
        self.assertEqual(e3.single_veto_from('bibcode'), True)
        e3.add_evidence(0, 'year')
        self.assertEqual(e3.single_veto_from('bibcode'), False)
        self.assertEqual(e3.count_votes(), False)
        e4 = Evidences()
        e4.add_evidence(1, 'authors')
        e4.add_evidence(1, 'year')
        e4.add_evidence(1, 'page')
        self.assertEqual(e4.has_veto(), False)
        e4.add_evidence(0, 'pub')
        self.assertEqual(e4.has_veto(), True)
        self.assertEqual(e4.count_votes(), True)
        self.assertEqual(e4['year'], 1)
        self.assertEqual(e1['year'], None)
        self.assertEqual(e1['authors'], None)


    def test_Solution(self):
        """
        test Solution class
        """
        e = Evidences()
        e.add_evidence(1, 'bibcode')
        s = Solution(cited_bibcode='2013SPIE.8004.2013Z', score=e)
        self.assertEqual(str(s), '1.0 2013SPIE.8004.2013Z')
        self.assertEqual(repr(s), "'2013SPIE.8004.2013Z'")


    def test_not_resolved(self):
        """
        test NotResolved exception class
        """
        nr = NotResolved(raw_ref='test reference needs to be long so that we can cut it and show 40 characters only', citing_bibcode=None)
        self.assertEqual(str(nr), 'NOT RESOLVED: test reference needs to be long so that ...')


    def test_no_solution(self):
        """
        test NoSolution exception class
        """
        ns = NoSolution(reason='In Testing Mode')
        self.assertEqual(str(ns), 'In Testing Mode')
        ns = NoSolution(reason='In Testing Mode', ref='test reference')
        self.assertEqual(str(ns),'In Testing Mode: test reference')


    def test_make_solr_condition(self):
        """
        test rearranging authors for solr query
        """
        self.assertEqual(make_solr_condition("title", "Far: From here to there (and back)"),
                         'title:(Far AND From AND here AND \\to AND there AND \\and AND back)')
        self.assertEqual(make_solr_condition("title~", "Meteorological Journal Kept Apartments Royal Society"),
                         'title:"Meteorological Journal Kept Apartments Royal Society"~')
        self.assertEqual(make_solr_condition("title", ""), None)
        self.assertEqual(make_solr_condition("author", "B. Traven and D. d'Vaucouleurs"),
                         'author:("Traven, B" AND "d\'Vaucouleurs, D")')
        self.assertEqual(make_solr_condition("first_author_norm~", "frisken gibson, s"),
                         'first_author:"frisken gibson"~')
        self.assertEqual(make_solr_condition("arxiv", "1904.07238"), 'identifier:("arxiv:1904.07238")')
        self.assertEqual(make_solr_condition("ascl", "1906.010"), 'identifier:("ascl:1906.010")')
        self.assertEqual(make_solr_condition("doi","10.1364/JOSAA.9.000154"), 'doi:"10.1364/JOSAA.9.000154"')
        # self.assertEqual(make_solr_condition("page", "154"), 'page:("?54" or "1?4" or "15?")')
        # for now since wildcard ? has been turned off when preceding any character, use this expanded version
        page_query = '"a54" or "b54" or "c54" or "d54" or "e54" or "f54" or "g54" or "h54" or "i54" or "j54" or ' \
                     '"k54" or "l54" or "m54" or "n54" or "o54" or "p54" or "q54" or "r54" or "s54" or "t54" or ' \
                     '"u54" or "v54" or "w54" or "x54" or "y54" or "z54" or "054" or "154" or "254" or "354" or ' \
                     '"454" or "554" or "654" or "754" or "854" or "954" or "1?4" or "15?"'
        self.assertEqual(make_solr_condition("page", "154"), 'page:(%s)'%page_query)
        self.assertEqual(make_solr_condition("bibstem", "JOSAA"), 'bibstem:(JOSAA)')
        self.assertEqual(make_solr_condition("year", "1992"), 'year:"1992"')
        self.assertEqual(make_solr_condition("year~", "1992"), 'year:[1987 TO 1997]')


    def test_solve_reference(self):
        """
        testing solve_reference with various fields
        """
        # testing with author, title, year, volume, and page
        ref = {'title': "The NASA Astrophysics Data System's Decadal Plan for the 2020s",
               'authors': 'Accomazzi, A.',
               'volume': '233',
               'year': '2019',
               'page': '207.04'}
        self.assertEqual(str(solve_reference(Hypotheses(ref))), '1.0 2019AAS...23320704A')
        # testing with author, publication name, and year
        ref = {'authors': 'Accomazzi, A.',
               'journal': 'AAS233 Meeting',
               'volume': '0',
               'page': '0',
               'year': '2019'}
        with self.assertRaises(Exception) as context:
            solve_reference(Hypotheses(ref))
        self.assertTrue('Hypotheses exhausted' in context.exception)
        # when we have multiple solutions and not enough reference information to decide which
        ref = {'title': "The NASA Astrophysics Data System's Decadal Plan for the 2020s",
               'authors': 'Accomazzi, A., Kurtz, M., Henneken, E., et al',
               'volume': '233',
               'year': '2019'}
        with self.assertRaises(Exception) as context:
            solve_reference(Hypotheses(ref))
        self.assertTrue('Hypotheses exhausted' in context.exception)
        ref = {'authors': 'Accomazzi, A., et al',
               'journal': 'AAS233 Meeting',
               'volume': '233',
               'year': '2019',
               'page': '0'}
        # when journal, volume, and year match
        # use title from first record and authors from the second record,
        # however the first record is authored by the only one author and
        # it is the same first author of the second record
        # verify that the first record is returned
        self.assertEqual(str(solve_reference(Hypotheses(ref))), '0.8 2019AAS...23320704A')


    def test_add_volume_evidence(self):
        """
        test add_volume_evidence
        """
        # both reference and ads missing volume values
        self.assertEqual(add_volume_evidence(Evidences(), None, None, None, None), None)
        self.assertEqual(add_volume_evidence(Evidences(), '', '', '', ''), None)
        # when one is missing
        evidences = Evidences()
        self.assertEqual(add_volume_evidence(evidences, '233', '', '', ''), None)
        self.assertEqual(evidences.get_score(), -1)
        evidences = Evidences()
        self.assertEqual(add_volume_evidence(evidences, '', '233', '', ''), None)
        self.assertEqual(evidences.get_score(), -1)
        # when matched
        evidences = Evidences()
        self.assertEqual(add_volume_evidence(evidences, '233', '233', '', ''), None)
        self.assertEqual(evidences.get_score(), 1)
        # when unmatched
        evidences = Evidences()
        self.assertEqual(add_volume_evidence(evidences, '223', '233', '', ''), None)
        self.assertEqual(evidences.get_score(), 0.7)
        # when not integer, but matched
        evidences = Evidences()
        self.assertEqual(add_volume_evidence(evidences, '233-3', '233-3', '', ''), None)
        self.assertEqual(evidences.get_score(), 1)
        # when not integer, unmatched
        evidences = Evidences()
        self.assertEqual(add_volume_evidence(evidences, '223-3', '233-3', '', ''), None)
        self.assertEqual(evidences.get_score(), -1)
        # when volume is year and there is an issue
        evidences = Evidences()
        self.assertEqual(add_volume_evidence(evidences, '233', '2018', '233', ''), None)
        self.assertEqual(evidences.get_score(), 1)


    def test_clean_ads_page(self):
        """
        test clean_ads_page
        """
        self.assertEqual(clean_ads_page('32B'), '32')
        self.assertEqual(clean_ads_page('207.04'), '207.04')
        self.assertEqual(clean_ads_page('33-45'), '33')
        self.assertEqual(clean_ads_page('IV92-IV99'), 'IV92-IV99')


    def test_compute_page_delta(self):
        """
        test compute_page_delta
        """
        self.assertEqual(compute_page_delta("23", "23"), 1)
        self.assertEqual(compute_page_delta("21", "234"), 0)
        self.assertEqual(compute_page_delta("32", "L32", "L"), 1)
        self.assertEqual(compute_page_delta("32", "L32", "P"), 1 + self.current_app.config['NO_LETTER_DEMERIT'])
        self.assertEqual(compute_page_delta("32", "32B"), 1 + self.current_app.config['NO_LETTER_DEMERIT'])
        self.assertEqual(compute_page_delta("A32", "32"), 1 + self.current_app.config['NO_LETTER_DEMERIT'])
        self.assertEqual(compute_page_delta("", ""), None)
        self.assertEqual(compute_page_delta("23", None), 0)
        self.assertEqual(compute_page_delta(":M20", "23"), 0)
        self.assertEqual(compute_page_delta(":M20", ":M20"), 1)
        self.assertEqual(compute_page_delta("233", "23"), 0)
        self.assertEqual(compute_page_delta("23", "0"), 0)


    def test_add_page_evidence(self):
        """
        test add_page_evidence
        """
        self.assertEqual(add_page_evidence(Evidences(), None, None), None)
        self.assertEqual(add_page_evidence(Evidences(), 23, 0), None)


    def test_compute_pubstring_statistics(self):
        """
        test compute_pubstring_statistics
        """
        self.assertEqual(compute_pubstring_statistics("A&A", "Astronomy and Astrophysics", "A&A"), (1, 0))
        self.assertEqual(compute_pubstring_statistics("A&AS", "Astronomy and Astrophysics", "A&A"), (1, 1))


    def test_string_similarity(self):
        """
        test string_similarity
        """
        self.assertEqual(string_similarity(None, None), -1)
        self.assertEqual(string_similarity('', ''), -1)
        self.assertTrue(string_similarity('The NASA Astrophysics Data System’s Decadal Plan for the 2020s',
                                          'Transitioning from ADS Classic to the new ADS search platform')
                        < 0.15)


    def test_add_publication_evidence(self):
        """
        test add_publication_evidence
        """
        evidences = Evidences()
        add_publication_evidence(evidences,
                                 'The NASA Astrophysics Data System’s Decadal Plan for the 2020s',
                                 'AAS',
                                 '',
                                 'The NASA Astrophysics Data System’s Decadal Plan for the 2020s',
                                 '2019AAS...23320704A',
                                 'AAS')
        self.assertEqual(evidences.get_score(), 1)
        evidences = Evidences()
        add_publication_evidence(evidences,
                                 'Nucl. Instrum. Methods Phys. Res. A',
                                 '',
                                 '',
                                 'Nuclear Instruments and Methods in Physics Research A',
                                 '1997NIMPA.389...81B',
                                 'NIMPA')
        self.assertEqual(evidences.get_score(), 0.6)
        evidences = Evidences()
        add_publication_evidence(evidences,
                                 'The NASA Astrophysics Data System’s Decadal Plan for the 2020s',
                                 '',
                                 '',
                                 '',
                                 '2019AAS...23320704A',
                                 'AAS')
        self.assertEqual(evidences.get_score(), -1)
        evidences = Evidences()
        add_publication_evidence(evidences,
                                 '',
                                 '',
                                 '',
                                 'Nuclear Instruments and Methods in Physics Research A',
                                 '1997NIMPA.389...81B',
                                 'NIMPA')
        self.assertEqual(evidences.get_score(), None)
        # when there is an error in reference, the author is not parsed properly,
        # and hence journal is not identified correctly, if ads bibstem is in ref_str, do not penalize
        evidences = Evidences()
        add_publication_evidence(evidences,
                                 'iaz',
                                 '',
                                 'Simon-D iaz, S., Castro, N., Garc ia, M., & Herrero, A. 2011a, in IAUS, Vol. 272, 310-312',
                                 'Active OB Stars: Structure, Evolution, Mass Loss, and Critical Limits',
                                 '2011IAUS..272..310S',
                                 'IAUS')
        self.assertEqual(evidences.get_score(), None)
        evidences = Evidences()
        add_publication_evidence(evidences, '', '', '', '', '', '')
        self.assertEqual(evidences.get_score(), None)


    def test_has_word(self):
        """
        test has_word
        """
        self.assertEqual(has_word("Foo, 23, 123", "1"), False)
        self.assertEqual(has_word("Foo, 23, 123", "Foo"), True)
        self.assertEqual(has_word("Foo, 23, 123", "23"), True)
        self.assertEqual(has_word("Foo, 23, 123", "123"), True)


    def test_has_thesis_indicators(self):
        """
        test has_thesis_indicators
        """
        self.assertEqual(has_thesis_indicators(u"2007b, PhD thesis , Cornell"), True)
        self.assertEqual(has_thesis_indicators(u"Astrophdical Journal"), False)
        self.assertEqual(has_thesis_indicators(u"CORNELL UNIVERSITY, 1969. Dissertation Abstracts International, Volume: 30-07, Section: B, page: 3319."), True)
        #self.assertEqual(0, 1)


    def test_cook_title_string(self):
        """
        test cook_title_string
        """
        self.assertEqual(cook_title_string("Untimely results in atomic spec."), 'Untimely results atomic')
        self.assertEqual(cook_title_string("a b c, a cat was in the snow"), '')


    def test_Querier(self):
        solrquery = Querier()
        self.assertEqual(solrquery.make_params('author:("Accomazzi, A") AND year:"2019" AND bibstem:(AAS)'),
                         {'q': 'author:("Accomazzi, A") AND year:"2019" AND bibstem:(AAS)',
                          'rows': '100',
                          'fl': u'author,author_norm,first_author_norm,year,title,pub,pub_raw,volume,issue,page,page_range,bibstem,bibcode,identifier,doi,doctype'})

        # no author_norm
        solution = {u'bibcode': u'2013JARS....7.3461V',
                    u'author': [u'Vasuki, Perumal', u'Mohamed Mansoor Roomi, S.'],
                    u'title': [u'Particle swarm optimization-based despeckling and decluttering of wavelet packet transformed synthetic aperture radar images'],
                    u'doctype': u'article', u'pub': u'Journal of Applied Remote Sensing',
                    u'pub_raw': u'Journal of Applied Remote Sensing, Volume 7, id. 073461 (2013).',
                    u'volume': u'7',
                    u'year': u'2013',
                    u'page': [u'073461']}
        self.assertEqual(solrquery.massage_solution(solution),
                         {u'pub': u'Journal of Applied Remote Sensing', u'volume': u'7',
                          'author_norm': ['Vasuki, Perumal', 'Mohamed Mansoor Roomi, S.'], u'year': u'2013',
                          'first_author_norm': 'vasuki, perumal', u'bibcode': u'2013JARS....7.3461V',
                          u'author': [u'Vasuki, Perumal', u'Mohamed Mansoor Roomi, S.'],
                          u'title': u'Particle swarm optimization-based despeckling and decluttering of wavelet packet transformed synthetic aperture radar images',
                          u'doctype': u'article',
                          u'pub_raw': u'Journal of Applied Remote Sensing, Volume 7, id. 073461 (2013).',
                          u'page': u'073461'})



class TestResolverHypotheses(TestCase):

    def create_app(self):
        self.current_app = app.create_app(**{
            'REFERENCE_SERVICE_LIVE': False
           })
        return self.current_app


    def setUp(self):
        """
        load the necessary objects
        """
        self.current_app.extensions['source_matcher'] = load_source_matcher()


    def test_a_Hypothesis(self):
        """
        test Hypothesis class
        """
        h = Hypothesis(name="test_arxiv_id", hints={'arxiv':'1905.07407'},
                       get_score_function=get_score_for_reference_identifier, input_fields={'arxiv':'1905.07407'})
        s = h.get_score({'identifier':['arXiv:1905.07407'], 'bibcode': '2019arXiv190507407S'}, h)
        self.assertEqual(s['bibcode'], 1)
        self.assertEqual(h.get_detail('has_etal'), None)


    def test_get_score_for_input_fields(self):
        """
        test scoring function get_score_for_input_fields
        """
        result_record= {u'bibcode': u'1992JOSAA...9..154F',
                        u'author': [u'Frisken Gibson, Sarah', u'Lanni, Frederick'],
                        u'title': u'Experimental test of an analytical model of aberration in an oil-immersion objective lens used in three-dimensional light microscopy',
                        u'doctype': u'article',
                        u'pub': u'Journal of the Optical Society of America A',
                        u'pub_raw': u'Journal of the Optical Society of America A, vol. 9, issue 1, p. 154',
                        u'volume': u'9',
                        u'author_norm': ['frisken gibson, s', 'lanni, f'],
                        u'year': u'1992',
                        u'first_author_norm': 'frisken gibson, s',
                        u'identifier': [u'1992JOSAA...9..154F', u'10.1364/JOSAA.9.000154', u'10.1364/JOSAA.9.000154'],
                        u'page': u'154'}
        input_fields= {'volume': u'9',
                       'year': u'1992',
                       'pub': u'J. Opt. Soc. Am. A',
                       'author': u'S.  Frisken-Gibson,F.  Lanni'}
        hypothesis = Hypothesis("testing", {
                            "author": input_fields["author"],
                            "bibstem": get_best_bibstem_for(input_fields["pub"]),
                            "year": input_fields["year"],
                            "volume": input_fields["volume"],
                            "pub": input_fields["pub"]},
                            get_score_for_input_fields,
                       input_fields=input_fields,
                       has_etal=False)
        evidences = get_score_for_input_fields(result_record, hypothesis)
        # matches are authors, year, pub, and volume
        self.assertEqual(evidences.get_score(), 4)


    # def test_inspect_doubtful_solutions(self):
    #     """
    #     test doubtful solutions, when there is more than one possible solution without a doubt (i.e., all fields have
    #     in evidences have positive values
    #     :return:
    #     """
    #     e1 = Evidences()
    #     e1.add_evidence(0.11, 'authors')
    #     e1.add_evidence(0.15, 'year')
    #     e2 = Evidences()
    #     e2.add_evidence(0.05, 'authors')
    #     e2.add_evidence(0.21, 'year')
    #     e3 = Evidences()
    #     e3.add_evidence(0.05, 'authors')
    #     e3.add_evidence(0.21, 'year')
    #     e3.add_evidence(-1, 'page')
    #
    #     input_fields = {u'bibcode': u'1992JOSAA...9..154F',
    #                     u'author': [u'Frisken Gibson, Sarah', u'Lanni, Frederick'],
    #                     u'year': u'1992'}
    #     hypothesis = Hypothesis("testing-fielded-author/year", {
    #                         "author": input_fields["author"],
    #                         "year": input_fields["year"]},
    #                    get_score_for_input_fields,
    #                    input_fields=input_fields,
    #                    has_etal=False)
    #
    #     with self.assertRaises(Exception) as context:
    #         inspect_doubtful_solutions(scored_solutions=[(e1, {u'bibcode': u'1992JOSAA...9..154F'})],
    #                                    query_string='the_query', hypothesis=hypothesis)
    #     self.assertTrue('Try again if desperate' in context.exception)
    #     with self.assertRaises(Exception) as context:
    #         inspect_doubtful_solutions(scored_solutions=[(e1, {u'bibcode': u'1992JOSAA...9..154F'}),(e2, {u'bibcode': u'1992JOSAA...9..154F'})],
    #                                    query_string='the_query', hypothesis=hypothesis)
    #     self.assertEqual('No unique non-vetoed doubtful solution: the_query', str(context.exception))
    #     with self.assertRaises(Exception) as context:
    #         inspect_doubtful_solutions(scored_solutions=[(e3, {u'bibcode': u'1992JOSAA...9..154F'})],
    #                                    query_string='the_query', hypothesis=hypothesis)
    #     self.assertTrue('Try again if desperate' in context.exception)

    # def test_inspect_ambiguous_solutions(self):
    #     """
    #     test inspect_ambiguous_solutions
    #     :return:
    #     """
    #     e1 = Evidences()
    #     e1.add_evidence(0.11, 'authors')
    #     e1.add_evidence(0.15, 'year')
    #     e2 = Evidences()
    #     e2.add_evidence(0.05, 'authors')
    #     e2.add_evidence(0.21, 'year')
    #     e2.add_evidence(0.1, 'volume')
    #     e3 = Evidences()
    #     e3.add_evidence(0.05, 'authors')
    #     e3.add_evidence(0.21, 'year')
    #     e3.add_evidence(-1, 'page')
    #     e4 = Evidences()
    #     e4.add_evidence(0.05, 'authors')
    #     e4.add_evidence(0.21, 'year')
    #
    #     input_fields = {u'bibcode': u'1992JOSAA...9..154F',
    #                     u'author': [u'Frisken Gibson, Sarah', u'Lanni, Frederick'],
    #                     u'year': u'1992',
    #                     u'volume': u'9'}
    #     hypothesis = Hypothesis("testing-fielded-author/year", {
    #                         "author": input_fields["author"],
    #                         "year": input_fields["year"]},
    #                    get_score_for_input_fields,
    #                    input_fields=input_fields,
    #                    has_etal=False)
    #     scored_solutions = [(e1, {u'bibcode': u'1992JOSAA...9..154F'})]
    #     self.assertEqual(inspect_ambiguous_solutions(scored_solutions=scored_solutions,
    #                                     query_string='the_query', hypothesis=hypothesis),
    #                      scored_solutions[0])
    #     with self.assertRaises(Exception) as context:
    #         inspect_ambiguous_solutions(scored_solutions=[(e3, {u'bibcode': u'1992JOSAA...9..154F'})],
    #                                     query_string='the_query', hypothesis=hypothesis)
    #     self.assertTrue('Try again if desperate' in context.exception)
    #     scored_solutions = [(e1, {u'bibcode': u'1992JOSAA...9..154F'}), (e2, {u'bibcode': u'1992JOSAA...9..154F'})]
    #     self.assertEqual(inspect_ambiguous_solutions(scored_solutions=scored_solutions,
    #                                     query_string='the_query', hypothesis=hypothesis),
    #                      scored_solutions[1])
    #     e1.add_evidence(0.05, 'title')
    #     e4.add_evidence(0.05, 'title')
    #     scored_solutions = [(e1, {u'bibcode': u'1992JOSAA...9..154F', u'title': u'Experimental test of an analytical model of aberration in an oil-immersion objective lens used in three-dimensional light microscopy', u'year': u'1992'}),
    #                         (e4, {u'bibcode': u'1992JOSAA...9..154F', u'title': u'Experimental test of an analytical model of aberration in an oil-immersion objective lens used in three-dimensional light microscopy'})]
    #     self.assertEqual(inspect_ambiguous_solutions(scored_solutions=scored_solutions,
    #                                     query_string='the_query', hypothesis=hypothesis),
    #                      scored_solutions[1])
    #     scored_solutions = [(e1, {u'bibcode': u'1992JOSAA...9..154F', u'title': u'title1 Experimental test of an analytical model of aberration in an oil-immersion objective lens used in three-dimensional light microscopy', u'year': u'1992'}),
    #                         (e4, {u'bibcode': u'1992JOSAA...9..154F', u'title': u'title2 Experimental test of an analytical model of aberration in an oil-immersion objective lens used in three-dimensional light microscopy'})]
    #     with self.assertRaises(Exception) as context:
    #         inspect_ambiguous_solutions(scored_solutions=scored_solutions,
    #                                     query_string='the_query', hypothesis=hypothesis)
    #     self.assertTrue('Ambiguous the_query.' in context.exception)


    # def test_choose_solution(self):
    #     """
    #
    #     :return:
    #     """
    #     e1 = Evidences()
    #     e1.add_evidence(0.0, 'authors')
    #     e1.add_evidence(0.3, 'year')
    #     e1.add_evidence(0, 'page')
    #     e1.add_evidence(-0.6, 'pubstring')
    #     e1.add_evidence(0, 'volume')
    #     e2 = Evidences()
    #     e2.add_evidence(1.0, 'authors')
    #     e2.add_evidence(1.0, 'year')
    #     e2.add_evidence(0, 'page')
    #     e2.add_evidence(0.6, 'pubstring')
    #     e2.add_evidence(1, 'volume')
    #     e3 = Evidences()
    #     e3.add_evidence(1.0, 'authors')
    #     e3.add_evidence(1.0, 'year')
    #     e3.add_evidence(1.0, 'page')
    #     e3.add_evidence(0.8, 'pubstring')
    #     e3.add_evidence(0.8, 'volume')
    #
    #     solution = {u'bibcode': u'2013JARS....7.3461V',
    #                 u'author': [u'Vasuki, Perumal', u'Mohamed Mansoor Roomi, S.'],
    #                 u'title': u'Particle swarm optimization-based despeckling and decluttering of wavelet packet transformed synthetic aperture radar images',
    #                 u'doctype': u'article', u'pub': u'Journal of Applied Remote Sensing',
    #                 u'pub_raw': u'Journal of Applied Remote Sensing, Volume 7, id. 073461 (2013).',
    #                 u'volume': u'7', u'author_norm': ['vasuki, p', 'mohamed mansoor roomi, s'], u'year': u'2013',
    #                 u'first_author_norm': 'vasuki, p',
    #                 u'identifier': [u'2013JARS....7.3461V', u'10.1117/1.JRS.7.073461', u'10.1117/1.JRS.7.073461'],
    #                 u'page': u'073461'}
    #
    #     hypothesis = Hypothesis("testing-fielded-author/year", {
    #                                 "author": solution["author"],
    #                                 "year": solution["year"]},
    #                             get_score_for_input_fields,
    #                             input_fields=solution,
    #                             has_etal=False)
    #
    #     with self.assertRaises(Exception) as context:
    #         choose_solution(candidates=[], query_string='the_query', hypothesis=hypothesis)
    #     self.assertTrue('Not even a doubtful solution' in context.exception)
    #     with self.assertRaises(Exception) as context:
    #         choose_solution(candidates=[(e1, solution)], query_string='the_query', hypothesis=hypothesis)
    #     self.assertEqual('No unique non-vetoed doubtful solution: the_query', str(context.exception))
    #     candidates = [(e2, solution)]
    #     self.assertTrue(choose_solution(candidates=candidates, query_string='the_query', hypothesis=hypothesis),
    #                     candidates[0])
    #     with self.assertRaises(Exception) as context:
    #         choose_solution(candidates=[(e2, solution), (e2, solution)], query_string='the_query', hypothesis=hypothesis)
    #     self.assertTrue('2 solutions with equal (good) score.' in context.exception)
    #     candidates = [(e2, solution), (e3, solution)]
    #     self.assertTrue(choose_solution(candidates=candidates, query_string='the_query', hypothesis=hypothesis),
    #                     candidates[0])


    # def test_get_score_for_reference_identifier(self):
    #     """
    #     test get_score_for_reference_identifier
    #     """
    #     # reference is DOI
    #     solution = {u"bibcode": u"2019NatNa..14...89C",
    #                 u"doi":[u"10.1038/s41565-018-0319-4"]}
    #
    #     ref = {"doi":"10.1038/s41565-018-0319-4"}
    #     hypothesis = Hypothesis("testing-fielded-DOI", {
    #                                 "doi": ref["doi"]},
    #                             get_score_for_reference_identifier,
    #                             input_fields=ref)
    #     self.assertEqual(get_score_for_reference_identifier(solution, hypothesis).get_score(), 1)
    #
    #     # if it does not match
    #     ref = {"doi":"no match"}
    #     hypothesis = Hypothesis("testing-fielded-DOI", {
    #                                 "doi": ref["doi"]},
    #                             get_score_for_reference_identifier,
    #                             input_fields=ref)
    #     self.assertEqual(get_score_for_reference_identifier(solution, hypothesis).get_score(), -1)
    #
    #     # reference is arxiv id which is available in eid in solr
    #     solution = {u"bibcode": u"2019arXiv190501258L",
    #                 u"identifier": [u"arXiv:1905.01258"]}
    #
    #     ref = {"arxiv":"1905.01258"}
    #     hypothesis = Hypothesis("testing-fielded-arxiv", {
    #                                 "arxiv": ref["arxiv"]},
    #                             get_score_for_reference_identifier,
    #                             input_fields=ref)
    #     self.assertEqual(get_score_for_reference_identifier(solution, hypothesis).get_score(), 1)
    #
    #     # if it does not match
    #     ref = {"arxiv":"no match"}
    #     hypothesis = Hypothesis("testing-fielded-arxiv", {
    #                                 "arxiv": ref["arxiv"]},
    #                             get_score_for_reference_identifier,
    #                             input_fields=ref)
    #     self.assertEqual(get_score_for_reference_identifier(solution, hypothesis).get_score(), -1)
    #
    #
    # def test_get_book_score_for_input_fields(self):
    #     """
    #     test get_book_score_for_input_fields
    #     """
    #     solution = {
    #         u"doctype":u"book",
    #         u"year":u"2019",
    #         u"bibcode":u"2019msme.book.....R",
    #         u"bibstem":u"msme",
    #         u"identifier":[u"2019msme.book.....R"],
    #         u"pub_raw":u"Meteoroids: Sources of Meteors on Earth and Beyond. Editors: Galina O. Ryabova, David J. Asher and Margaret D. Campbell-Brown. ISBN 9781108426718. Cambridge University Press, 2019",
    #         u"pub":u"Meteoroids: Sources of Meteors on Earth and Beyond. Editors: Galina O. Ryabova",
    #         u"first_author_norm":u"Ryabova, G",
    #         u"author":[u"Ryabova, Galina O.", u"Asher, David J.", u"Campbell-Brown, Margaret J."],
    #         u"title":u"Meteoroids: Sources of Meteors on Earth and Beyond",
    #         u"author_norm":["Ryabova, G", "Asher, D", "Campbell-Brown, M"]
    #     }
    #     # note passing in a mistaken year by a character
    #     ref = {"authors": "Ryabova, G., Asher, D., Campbell Brown, M.",
    #            "title": "Meteoroids: Sources of Meteors on Earth and Beyond",
    #            "year": "2009"}
    #     normalized_authors = normalize_author_list(ref["authors"], initials=True)
    #     # note that specifying hints here is useless since we are passing the solution in already
    #     # put it here to know what information was used in the query corresponding to the scare function called
    #     hypothesis = Hypothesis("test-fielded-book-title", {
    #                        "author": normalized_authors,
    #                         "title": ref["title"],
    #                         "year": ref["year"]},
    #                     get_book_score_for_input_fields,
    #                     input_fields=ref,
    #                     page_qualifier=ref.get("qualifier"),
    #                     has_etal=False,
    #                     normalized_authors=normalized_authors)
    #     self.assertEqual(get_book_score_for_input_fields(solution, hypothesis).get_score(), 2.75)
    #
    #
    # def test_get_thesis_score_for_input_fields(self):
    #     """
    #     test get_thesis_score_for_input_fields
    #     """
    #     solution = {
    #         u"first_author_norm": u"Rowden, P",
    #         u"year":u"2019",
    #         u"bibcode":u"2019PhDT........11R",
    #         u"identifier":[u"2019PhDT........11R"],
    #         u"author":[u"Rowden, Pamela M."],
    #         u"pub":u"Ph.D. Thesis",
    #         u"doctype":u"phdthesis",
    #         u"pub_raw":u"PhD These, The Open University, 2019",
    #         u"title":u"False Positives and Shallow Eclipsing Binaries in Transiting Exoplanet Surveys",
    #         u"author_norm":[u"Rowden, P"]
    #     }
    #     ref = {"authors": "Rowden, P.", "year": "2019", "refstr": "PhD These, The Open University, 2019"}
    #     # note that specifying hints here is useless since we are passing the solution in already
    #     # put it here to know what information was used in the query corresponding to the scare function called
    #     normalized_authors = normalize_author_list(ref["authors"], initials=True)
    #     hypothesis = Hypothesis("test-fielded-thesis", {
    #                         "author": normalized_authors,
    #                         "pub_escaped": "(%s)"%" or ".join(self.current_app.config["THESIS_INDICATOR_WORDS"]),
    #                         "year": ref["year"]},
    #                     get_thesis_score_for_input_fields,
    #                     input_fields=ref,
    #                     normalized_authors=normalized_authors)
    #     self.assertEqual(get_thesis_score_for_input_fields(solution, hypothesis).get_score(), 3)
    #
    #     # wrong initial
    #     ref = {"authors": "Rowden, R.", "year": "2019", "refstr": "PhD These, The Open University, 2019"}
    #     # note that specifying hints here is useless since we are passing the solution in already
    #     # put it here to know what information was used in the query corresponding to the scare function called
    #     normalized_authors = normalize_author_list(ref["authors"], initials=True)
    #     hypothesis = Hypothesis("test-fielded-thesis", {
    #                         "author": normalized_authors,
    #                         "pub_escaped": "(%s)"%" or ".join(self.current_app.config["THESIS_INDICATOR_WORDS"]),
    #                         "year": ref["year"]},
    #                     get_thesis_score_for_input_fields,
    #                     input_fields=ref,
    #                     normalized_authors=normalized_authors)
    #     self.assertEqual(get_thesis_score_for_input_fields(solution, hypothesis).get_score(), 1)
    #
    #     # mistaken year
    #     ref = {"authors": "Rowden, P.", "year": "2018", "refstr": "PhD These, The Open University, 2019"}
    #     normalized_authors = normalize_author_list(ref["authors"], initials=True)
    #     hypothesis = Hypothesis("test-fielded-thesis", {
    #                         "author": normalized_authors,
    #                         "pub_escaped": "(%s)"%" or ".join(self.current_app.config["THESIS_INDICATOR_WORDS"]),
    #                         "year": ref["year"]},
    #                     get_thesis_score_for_input_fields,
    #                     input_fields=ref,
    #                     normalized_authors=normalized_authors)
    #     self.assertEqual(get_thesis_score_for_input_fields(solution, hypothesis).get_score(), 2.75)
    #
    #     # no thesis indication
    #     solution = {
    #         u"first_author_norm": u"Rowden, P",
    #         u"year": u"2019",
    #         u"bibcode": u"2019PhDT........11R",
    #         u"identifier":[u"2019PhDT........11R"],
    #         u"author":[u"Rowden, Pamela M."],
    #         u"pub": u"Ph.D. Thesis",
    #         u"doctype": u"phdthesis",
    #         u"pub_raw": u"no indicator, The Open University, 2019",
    #         u"title":u"False Positives and Shallow Eclipsing Binaries in Transiting Exoplanet Surveys",
    #         u"author_norm":[u"Rowden, P"]
    #     }
    #     ref = {"authors": "Rowden, P.", "year": "2019", "refstr": "PhD These, The Open University, 2019"}
    #     hypothesis = Hypothesis("test-fielded-thesis", {
    #                         "author": normalized_authors,
    #                         "pub_escaped": "(%s)"%" or ".join(self.current_app.config["THESIS_INDICATOR_WORDS"]),
    #                         "year": ref["year"]},
    #                     get_thesis_score_for_input_fields,
    #                     input_fields=ref,
    #                     normalized_authors=normalized_authors)
    #     self.assertEqual(get_thesis_score_for_input_fields(solution, hypothesis).get_score(), 1)
    #
    #     # if solution contians multiple authors, penalize
    #     solution = {
    #         u"first_author_norm": u"Rowden, P",
    #         u"year": u"2019",
    #         u"bibcode": u"2019PhDT........11R",
    #         u"identifier":[u"2019PhDT........11R"],
    #         u"author":[u"Rowden, Pamela M.", u"Grady, M. M."],
    #         u"pub": u"Ph.D. Thesis",
    #         u"doctype": u"phdthesis",
    #         u"pub_raw": u"PhD These, The Open University, 2019",
    #         u"title":u"False Positives and Shallow Eclipsing Binaries in Transiting Exoplanet Surveys",
    #         u"author_norm":[u"Rowden, P", u"Grady, M"]
    #     }
    #     self.assertEqual(get_thesis_score_for_input_fields(solution, hypothesis).get_score(), 2.9)


    def test_add_publication_evidence_error(self):
        """
        test add_publication_evidence for when there is a typo in the reference journal
        """
        solution = {u'bibcode': u'2018AJ....156..102S',
                    u'author': [u'Stassun, Keivan G.', u'Oelkers, Ryan J.', u'Pepper, Joshua', u'Paegert, Martin', u'De Lee, Nathan', u'Torres, Guillermo', u'Latham, David W.', u'Charpinet, St\xe9phane', u'Dressing, Courtney D.', u'Huber, Daniel', u'Kane, Stephen R.', u'L\xe9pine, S\xe9bastien', u'Mann, Andrew', u'Muirhead, Philip S.', u'Rojas-Ayala, B\xe1rbara', u'Silvotti, Roberto', u'Fleming, Scott W.', u'Levine, Al', u'Plavchan, Peter'],
                    u'bibstem': u'AJ',
                    u'doctype': u'article',
                    u'pub': u'The Astronomical Journal',
                    u'pub_raw': u'The Astronomical Journal, Volume 156, Issue 3, article id. 102, <NUMPAGES>39</NUMPAGES> pp. (2018).',
                    u'volume': u'156',
                    u'doi': [u'10.3847/1538-3881/aad050'],
                    u'author_norm': ['stassun, k', 'oelkers, r', 'pepper, j', 'paegert, m', 'de lee, n', 'torres, g', 'latham, d', 'charpinet, s', 'dressing, c', 'huber, d', 'kane, s', 'lepine, s', 'mann, a', 'muirhead, p', 'rojas ayala, b', 'silvotti, r', 'fleming, s', 'levine, a', 'plavchan, p'],
                    u'year': u'2018',
                    u'first_author_norm': 'stassun, k',
                    u'title': u'The TESS Input Catalog and Candidate Target List',
                    u'identifier': [u'2017arXiv170600495S', u'2018AJ....156..102S', u'10.3847/1538-3881/aad050', u'2017arXiv170600495S', u'arXiv:1706.00495', u'10.3847/1538-3881/aad050'],
                    u'issue': u'3',
                    u'page': u'102'}
        # note that journal was supposed to be AJ
        ref = {'journal': u'ApJ',
               'authors': u'Stassun, K. G., Oelkers, R. J., Pepper, J., et al.',
               'refstr': u'Stassun, K. G., Oelkers, R. J., Pepper, J., et al. 2018, ApJ, 156, 102',
               'volume': u'156',
               'year': u'2018',
               'page': u'102'}
        normalized_authors = normalize_author_list(ref["authors"], initials=True)
        hypothesis = Hypothesis("testing-fielded-author/year/volume/page", {
                            "author": normalized_authors,
                            "year": ref["year"],
                            "volume": ref["volume"],
                            "page": ref["page"]},
                        get_score_for_input_fields,
                        input_fields=ref,
                        page_qualifier='',
                        has_etal='et al' in ref["authors"],
                        normalized_authors=normalized_authors)
        self.assertEqual(get_score_for_input_fields(solution, hypothesis).get_score(), 4.0)


    def test_iter_journal_specific_hypotheses(self):
        """
        test iter_journal_specific_hypotheses
        """
        # "bibcode":"2019BAAS...51c.440B"
        ref = {'title': "Studying the Reionization Epoch with QSO Absorption Lines",
               'authors': "Becker, G., D'Aloisio, A., Davies, F., Hennawi, J., Simcoe, R.",
               'volume': "51",
               'year': "2019",
               'page': "440",
               'journal': "Bulletin of the American Astronomical Society",
               'refstr': "Becker, G., D'Aloisio, A., Davies, F., Hennawi, J., Simcoe, R. (2019). Studying the Reionization Epoch with QSO Absorption Lines. Bulletin of the American Astronomical Society, Vol. 51, p.440."}
        hypothesis = iter_journal_specific_hypotheses('BAAS', ref['authors'], ref['year'], ref['journal'],
                                                              ref['volume'], ref['page'], ref['refstr'])
        tried_hypothesis = ['extra-BAAS->DDA', 'extra-BAAS->AAS', 'extra-BAAS->DPS']
        for i, h in enumerate(hypothesis):
            self.assertEqual(h.name, tried_hypothesis[i])

        # "bibcode":"2009lpsc.book.....A"
        ref = {'title': "Lectures on the Physics of Strongly Correlated Systems XIII",
               'authors': "Avella, A., Mancini, F.",
               'year': "2009",
               'book': "Lectures on the Physics of Strongly Correlated Systems XIII by Adolfo Avella",
               'refstr': "Avella, A., Mancini, F. (2009). Lectures on the Physics of Strongly Correlated Systems XIII by Adolfo Avella, Ferdinando Mancini, Springer, ISBN: 978-0-7354-0699-5"}
        hypothesis = iter_journal_specific_hypotheses('LPSC', ref['authors'], ref['year'], ref['book'],
                                                              None, None, ref['refstr'])
        tried_hypothesis = ['LPSC-ignore-volume']
        for i, h in enumerate(hypothesis):
            self.assertEqual(h.name, tried_hypothesis[i])

        # "bibcode":"2019ApJ...875L..24L"
        ref = {'title': "Simulating the Dark Matter Decay Signal from the Perseus Galaxy Cluster",
               'authors': "Lovell, M., Iakubovskyi, D., Barnes, D., Bose, S., Frenk, C., Theuns, T., Hellwing, W.",
               'year': "2019",
               'volume': "875",
               'page': "L24",
               'journal': "The Astrophysical Journal",
               'refstr': "Lovell, M., Iakubovskyi, D., Barnes, D., Bose, S., Frenk, C., Theuns, T., Hellwing, W., The Astrophysical Journal Letters, Volume 875, Issue 2, article id. L24, 8 pp. (2019)."}
        hypothesis = iter_journal_specific_hypotheses('ApJ', ref['authors'], ref['year'], ref['journal'],
                                                              None, None, ref['refstr'])
        tried_hypothesis = ['extra-ApJ->ApJL']
        for i, h in enumerate(hypothesis):
            self.assertEqual(h.name, tried_hypothesis[i])

        # "bibcode":"2019SPIE10866E....M"
        ref = {'title': "Optogenetics and Optical Manipulation 2019",
               'authors': "Mohanty, S., Jansen, E.",
               'year': "2019",
               'volume': "10866",
               'journal': "Society of Photo-Optical Instrumentation Engineers (SPIE) Conference Series",
               'refstr': "Mohanty, S., Jansen, E., Optogenetics and Optical Manipulation 2019.  Edited by Mohanty, Samarendra K.; Jansen, E. Duco. Proceedings of the SPIE, Volume 10866 (2019)."}
        hypothesis = iter_journal_specific_hypotheses(None, ref['authors'], ref['year'], ref['journal'],
                                                              None, None, ref['refstr'])
        self.assertEqual(next(hypothesis).name, 'fielded-confser-SPIE')


    def test_get_score_for_baas_match(self):
        """
        test get_score_for_baas_match
        """
        # "bibcode":"2019BAAS...51c.440B"
        solution = {u"identifier":[u"2019astro2020T.440B", u"2019BAAS...51c.440B",
                      u"https://baas.aas.org/wp-content/uploads/2019/05/440_becker.pdf",
                      u"https://baas.aas.org/wp-content/uploads/2019/05/440_becker.pdf",
                      u"2019astro2020T.440B"],
                    u"year":u"2019",
                    u"page":u"440",
                    u"bibcode":"2019BAAS...51c.440B",
                    u"author":[u"Becker, George", u"D'Aloisio, Anson", u"Davies, Frederick B.", u"Hennawi, Joseph F.", u"Simcoe, Robert A."],
                    u"pub":"Bulletin of the American Astronomical Society",
                    u"volume":"51",
                    u"first_author_norm":"Becker, G",
                    u"doctype":"abstract",
                    u"pub_raw":"Astro2020: Decadal Survey on Astronomy and Astrophysics, science white papers, no. 440; Bulletin of the American Astronomical Society, Vol. 51, Issue 3, id. 440 (2019)",
                    u"eid":u"440",
                    u"title":u"Studying the Reionization Epoch with QSO Absorption Lines",
                    u"author_norm":[u"Becker, G", u"D'Aloisio, A", u"Davies, F", u"Hennawi, J", u"Simcoe, R"]}
        input_fields = {'title': "Studying the Reionization Epoch with QSO Absorption Lines",
                        'author': "Becker, G., D'Aloisio, A., Davies, F., Hennawi, J., Simcoe, R.",
                        'volume': "51",
                        'year': "2019",
                        'page': "440",
                        'pub': "Bulletin of the American Astronomical Society",
                        'refstr': "Becker, G., D'Aloisio, A., Davies, F., Hennawi, J., Simcoe, R. (2019). Studying the Reionization Epoch with QSO Absorption Lines. Bulletin of the American Astronomical Society, Vol. 51, p.440."}
        # exact match
        hypothesis = Hypothesis("testing", None,
                       get_score_for_input_fields,
                       input_fields=input_fields,
                       expected_bibstem=get_best_bibstem_for(input_fields["pub"]))
        self.assertEqual(get_score_for_baas_match(solution, hypothesis).get_score(), 1.0)
        # no matching expected_bibcode
        hypothesis = Hypothesis("testing", None,
                       get_score_for_input_fields,
                       input_fields=input_fields,
                       expected_bibstem="no match")
        self.assertEqual(get_score_for_baas_match(solution, hypothesis), -1)


    # def test_identify_incomplete(self):
    #     """
    #     test when parsed reference is incomplete
    #     """
    #     ref = {'year': '2020',
    #            'refstr': '[4] Bennett, J. S., & Sijacki, D. 2020, arXiv e-prints,',
    #            'authors': 'Bennett, J. S., and Sijacki, D.'}
    #     with self.assertRaises(Exception) as context:
    #         solve_reference(Hypotheses(ref))
    #     self.assertTrue('Not enough information to resolve the record.' in context.exception)
    #
    #
    # def test_build_bibcode(self):
    #     """
    #     test building bibcode to query solr with it
    #     """
    #     ref = {'journal': u'a&a',
    #            'authors': u'Verela et al.',
    #            'refstr': u'Verela et al., 2016, a&a, 589, 37',
    #            'volume': u'589',
    #            'year': u'2016',
    #            'page': u'37'}
    #     self.assertEqual(Hypotheses(ref).construct_bibcode(),
    #                      ['2016A&A...589...37V', '2016?????.589...37V', '2016A&A...589?..37V', '2016?????.589?..37V'])
    #     ref = {'journal': u'A&A',
    #            'authors': u'Shakura N. I., Sunyaev R. A.',
    #            'refstr': u'Shakura N. I., Sunyaev R. A., 1973, A&A, 24, 337',
    #            'volume': u'24',
    #            'year': u'1973',
    #            'page': u'337'}
    #     self.assertEqual(Hypotheses(ref).construct_bibcode(),
    #                      ['1973A&A....24..337S', '1973?????..24..337S', '1973A&A....24?.337S', '1973?????..24?.337S'])
    #     ref = {'journal': u'A&A',
    #            'authors': u'N. Aghanim et al., Planck Collaboration',
    #            'refstr': u'N. Aghanim et al., Planck Collaboration, "A&A" 641 (2020) A6.',
    #            'volume': u'641',
    #            'year': u'2020',
    #            'page': u'A6'}
    #     self.assertEqual(Hypotheses(ref).construct_bibcode(),
    #                      ['2020A&A...641A...6A', '2020?????.641A...6A'])



class TestResolverSolrQueryCase(TestCase):
    """
    set max number of solr records processing from 100 to 2 to verify no solution is returned
    """
    def create_app(self):
        self.current_app = app.create_app(**{
            'REFERENCE_SERVICE_LIVE': False,
            'REFERENCE_SERVICE_MAX_RECORDS_SOLR': 2
           })
        return self.current_app


    def test_Querier(self):
        solrquery = Querier()
        self.assertEqual(solrquery.query('author:("Accomazzi, A") AND year:"2019" AND bibstem:(AAS)'), None)



if __name__ == "__main__":
    unittest.main()
