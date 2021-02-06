# import sys, os
# project_home = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../'))
# if project_home not in sys.path:
#     sys.path.insert(0, project_home)
#
# from flask_testing import TestCase
# import unittest
#
# import re
#
# import referencesrv.app as app
# from referencesrv.parser.crf import CRFClassifierText
#
# from referencesrv.resolver.authors import get_author_pattern, get_authors, normalize_single_author, \
#     normalize_author_list, get_first_author, get_first_author_last_name, count_matching_authors, \
#     add_author_evidence
# from referencesrv.resolver.common import Evidences, NotResolved, Undecidable, NoSolution, DeferredSourceMatcher, \
#     SOURCE_MATCHER, Solution, Hypothesis
# from referencesrv.resolver.pytrigdict import get_trigrams, TrigIndex, Trigdict
# from referencesrv.resolver.sourcematchers import TrigdictSourceMatcher, SourceMatcher
# from referencesrv.resolver.scoring import get_score_for_reference_identifier, get_score_for_input_fields, \
#     get_score_for_reference_identifier, get_book_score_for_input_fields, get_thesis_score_for_input_fields
# from referencesrv.resolver.journalfield import get_best_bibstem_for, add_volume_evidence, clean_ads_page, \
#     compute_page_delta, add_page_evidence, compute_pubstring_statistics, string_similarity, add_publication_evidence, \
#     has_word, has_thesis_indicators, cook_title_string
# from referencesrv.resolver.solve import make_solr_condition, inspect_doubtful_solutions, inspect_ambiguous_solutions, \
#     choose_solution, solve_reference
# from referencesrv.resolver.hypotheses import Hypotheses
# from referencesrv.resolver.solrquery import Querier
# from referencesrv.resolver.specialrules import iter_journal_specific_hypotheses, get_score_for_baas_match
# from referencesrv.resolver.sourcematchers import load_source_matcher
#
#
# class TestCRFClassifierText(TestCase):
#
#     maxDiff = None
#
#     # def create_app(self):
#     #     app_ = app.create_app()
#     #     return app_
#
#     def create_app(self):
#         self.current_app = app.create_app(**{
#             'REFERENCE_SERVICE_LIVE': False
#            })
#         return self.current_app
#
#     def setUp(self):
#         """ executed before each test """
#         self.crf_text = CRFClassifierText()
#         self.crf_text.load()
#
#     def tearDown(self):
#         """ executed after each test """
#         pass
#
# if __name__ == "__main__":
#     unittest.main()
