import sys, os
project_home = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../'))
if project_home not in sys.path:
    sys.path.insert(0, project_home)

from flask_testing import TestCase
import unittest

import referencesrv.app as app
from referencesrv.parser.crf import CRFClassifierText, CRFClassifierXML
from referencesrv.parser.getDataXML import get_xml_tagged_data, get_xml_tagged_data_training, crossref_extract_volume_from_journal
from stubdata import dataXML

class TestCRFClassifier(TestCase):
    def create_app(self):
        app_ = app.create_app()
        return app_


class TestCRFClassifierText(TestCase):
    def create_app(self):
        app_ = app.create_app()
        return app_


    def test_a_reference(self):
        """

        """
        crf_text = CRFClassifierText()
        X_train, y_train = crf_text.get_train_data()
        crf_text.train(X_train, y_train)

        X_test, y_test = crf_text.get_test_data()
        score = crf_text.evaluate(X_test, y_test)
        self.assertTrue(score > 0.90)

        reference_str = 'Bhattacharya, A., Pati, D., Pillai, N. S., and Dunson, D. B. (2015). Dirichlet Laplace priors for optimal shrinkage. "J. Amer. Statist. Assoc.", 110(512):1479-1490.'
        words, labels = crf_text.classify(reference_str)
        self.assertEqual(crf_text.reference(reference_str, words, labels),
                         {'title': 'Dirichlet Laplace priors for optimal shrinkage',
                          'journal': 'J Amer Statist Assoc',
                          'authors': 'Bhattacharya, A., Pati, D., Pillai, N. S., and Dunson, D. B.',
                          'refstr': 'Bhattacharya, A., Pati, D., Pillai, N. S., and Dunson, D. B. (2015). Dirichlet Laplace priors for optimal shrinkage. "J. Amer. Statist. Assoc.", 110(512):1479-1490.',
                          'volume': '110',
                          'year': '2015',
                          'issue': '512',
                          'page': '1479-1490'})

    def test_get_ready_with_arxiv_id(self):
        """

        :return:
        """
        crf_text = CRFClassifierText()
        if crf_text.get_ready():
            reference_str = "C. Virgo, B. Abbott et al., GW170817: Observation of Gravitational Waves from a Binary Neutron Star, Phys. Rev. Lett. 119 (2017) 161101, [1710.05832]."
            self.assertEqual(crf_text.parse(reference_str),
                             {'title': 'GW170817 Observation of Gravitational Waves from a Binary Neutron Star',
                              'journal': 'Phys Rev Lett',
                              'arxiv': '1710.05832',
                              'refstr': 'C. Virgo, B. Abbott et al., GW170817: Observation of Gravitational Waves from a Binary Neutron Star, Phys. Rev. Lett. 119 (2017) 161101, [1710.05832].',
                              'volume': '119',
                              'authors': 'C. Virgo, B. Abbott et al.',
                              'year': '2017',
                              'page': '161101'})

    def test_get_ready_with_doi(self):
        """

        :return:
        """
        crf_text = CRFClassifierText()
        if crf_text.get_ready():
            reference_str = 'Elisabete da Cunha et al. "The Taipan Galaxy Survey: Scientific Goals and Observing Strat- egy". In: Publications of the Astronomical Society of Australia 34, e047 (2017), e047. DOI: 10. 1017/ pasa. 2017.41. arXiv: 1706.01246.'
            self.assertEqual(crf_text.parse(reference_str),
                             {'doi': '10.1017/pasa.2017.41',
                              'title': 'The Taipan Galaxy Survey Scientific Goals and Observing',
                              'journal': 'Publications of the Astronomical Society of Australia',
                              'arxiv': '1706.01246',
                              'refstr': 'Elisabete da Cunha et al. "The Taipan Galaxy Survey: Scientific Goals and Observing Strat- egy". In: Publications of the Astronomical Society of Australia 34, e047 (2017), e047. DOI: 10. 1017/ pasa. 2017.41. arXiv: 1706.01246.',
                              'volume': '34',
                              'authors': 'Elisabete da Cunha et al.',
                              'year': '2017',
                              'page': 'e047'})


    def test_get_ready_no_identifier(self):
        """

        :return:
        """
        crf_text = CRFClassifierText()
        if crf_text.get_ready():
            reference_str = "C. Virgo, B. Abbott et al., GW170817: Observation of Gravitational Waves from a Binary Neutron Star, Phys. Rev. Lett. 119 (2017)."
            self.assertEqual(crf_text.parse(reference_str),
                             {'title': 'GW170817 Observation of Gravitational Waves from a Binary Neutron Star',
                              'journal': 'Phys Rev Lett',
                              'authors': 'C. Virgo, B. Abbott et al.',
                              'refstr': 'C. Virgo, B. Abbott et al., GW170817: Observation of Gravitational Waves from a Binary Neutron Star, Phys. Rev. Lett. 119 (2017).',
                              'volume': '119',
                              'year': '2017'})

    def test_get_ready_no_title(self):
        """

        :return:
        """
        crf_text = CRFClassifierText()
        if crf_text.get_ready():
            reference_str = 'Trujillo et al., 2018. Division for Planetary Sciences, vol 50, #311.09.'
            self.assertEqual(crf_text.parse(reference_str),
                             {'journal': 'Division for Planetary Sciences',
                              'authors': 'Trujillo et al.',
                              'refstr': 'Trujillo et al., 2018. Division for Planetary Sciences, vol 50, #311.09.',
                              'volume': '50',
                              'year': '2018',
                              'page': '311.09'})

    def test_get_num_states(self):
        crf_text = CRFClassifierText()
        if crf_text.get_ready():
            self.assertEqual(crf_text.get_num_states(), 37)

    def test_split_reference(self):
        """

        """
        crf_text = CRFClassifierText()
        reference = "K.E. Mesick, W.C. Feldman, E.R. Mullin, L.C. Stonehill, 2020, Icarus, 335, 113397, arXiv:1904.09036, doi:10.1016/j.icarus.2019.113397."
        segment_dict = {'arxiv': '1904.09036', 'doi': 'doi:10.1016/j.icarus.2019.113397', 'page': '113397'}
        self.assertEqual(crf_text.split_reference(reference, segment_dict),
                         ['K', '.', 'E', '.', 'Mesick', ',', 'W', '.', 'C', '.', 'Feldman', ',', 'E', '.', 'R', '.',
                          'Mullin', ',', 'L', '.', 'C', '.', 'Stonehill', ',', '2020', ',', 'Icarus', ',', '335', ',',
                          '113397', ',', 'arXiv', ':', '1904.09036', ',', 'doi:10.1016/j.icarus.2019.113397', '.'])
        # with no identifiers
        reference = "K.E. Mesick, W.C. Feldman, E.R. Mullin, L.C. Stonehill, 2020, Icarus, 335."
        self.assertEqual(crf_text.split_reference(reference, {}),
                         ['K', '.', 'E', '.', 'Mesick', ',', 'W', '.', 'C', '.', 'Feldman', ',', 'E', '.', 'R', '.',
                          'Mullin', ',', 'L', '.', 'C', '.', 'Stonehill', ',', '2020', ',', 'Icarus', ',', '335', '.'])

    def test_identify_ids(self):
        """

        """
        reference_str = "K.E. Mesick, W.C. Feldman, E.R. Mullin, L.C. Stonehill, 2020, Icarus, 335, 113397, arXiv:1904.09036, doi:10.1016/j.icarus.2019.113397."
        self.assertEqual(CRFClassifierText().identify_ids(reference_str),
                         {'arxiv': '1904.09036', 'ascl': '', 'doi': 'doi:10.1016/j.icarus.2019.113397', 'issn': '', 'version': ''})

    def test_identify_editors(self):
        """

        """
        reference_str = 'K. S. Thorne, "Gravitational radiation," in "Three hundred years of gravitation", S. W. Hawking and W. Israel, eds., ch. 9, pp. 330-458. Cambridge University Press, Cambridge, 1987.'
        _, segment_dict = CRFClassifierText().identify_editors(reference_str, {})
        self.assertEqual(segment_dict['editors'], 'S. W. Hawking and W. Israel')

    def test_identify_authors(self):
        """

        """
        reference_str = 'Trujillo and Sheppard, 2014. Nature 507, p. 471-474.'
        self.assertEqual(CRFClassifierText().identify_authors(reference_str), 'Trujillo and Sheppard')

    def test_identify_volume_page_issue(self):
        """

        :return:
        """
        reference_str = 'Arzoumanian, D., Andre, P., et al., 2019. Astronomy & Astrophysics, 621:A42'
        token_dict = CRFClassifierText().identify_numeric_tokens(reference_str)
        self.assertEqual(token_dict['volume'], '621')
        self.assertEqual(token_dict['page'], 'A42')
        self.assertEqual(token_dict['issue'], '')

        reference_str = 'J. P. Perez-Beaupuits, R. Gusten, M. Spaans, V. Ossenkopf, K. M. Menten, M. A. Requena-Torres, et al. Disentangling the excitation conditions of the dense gas in M17 SW. "A&A", 10 583:A107, November 2015.'
        token_dict = CRFClassifierText().identify_numeric_tokens(reference_str)
        self.assertEqual(token_dict['volume'], '10')
        self.assertEqual(token_dict['page'], 'A107')
        self.assertEqual(token_dict['issue'], '583')

        # test page range
        reference_str = 'M. Houde, P. Bastien, J. L. Dotson, C. D. Dowell, R. H. Hildebrand, R. Peng, et al. On the Measurement of the Magnitude and Orientation of the Magnetic Field in Molecular Clouds. "ApJ", 569:803-814, April 2002.'
        token_dict = CRFClassifierText().identify_numeric_tokens(reference_str)
        self.assertEqual(token_dict['volume'], '569')
        self.assertEqual(token_dict['page'], '803-814')
        self.assertEqual(token_dict['issue'], '')


class TestCRFClassifierXML(TestCase):
    def create_app(self):
        app_ = app.create_app()
        return app_

    def test_a_reference(self):
        """

        """
        crf_xml = CRFClassifierXML()
        X_train, y_train = crf_xml.get_train_data()
        crf_xml.train(X_train, y_train)

        X_test, y_test = crf_xml.get_test_data()
        score = crf_xml.evaluate(X_test, y_test)
        self.assertTrue(score > 0.90)

        raw_references = [u'<ADSBIBCODE>2013SoPh..287..441T</ADSBIBCODE>',
                          u'<citation_list doi="10.1007/s11207-012-0088-4" file="doi/10.1007/./s1/12/07/-0/12/-0/08/8-/4//metadata.xml" bibcode="2013SoPh..287..441T"><citation key="88_CR1"><journal_title>Astrophys. J.</journal_title><author>A. Bemporad</author><volume>720</volume><first_page>130</first_page><cyear>2010</cyear><unstructured_citation>Bemporad, A., Mancuso, S.: 2010, Astrophys. J. 720, 130. doi: 10.1088/0004-637X/720/1/130 .</unstructured_citation></citation></citation_list>']

        self.assertEqual(crf_xml.parse(raw_references),
                         [{'refplaintext': u'Bemporad, A., Mancuso, S.: 2010, Astrophys. J. 720, 130. doi: 10.1088/0004-637X/720/1/130 .',
                           'journal': u'Astrophys J',
                           'refstr': "{u'unstructured_citation': u'Bemporad, A., Mancuso, S.: 2010, Astrophys. J. 720, 130. doi: 10.1088/0004-637X/720/1/130 .', u'author': u'A. Bemporad', u'journal_title': u'Astrophys. J.', u'cyear': u'2010', u'volume': u'720', u'@key': u'88_CR1', u'first_page': u'130'}",
                           'volume': u'720',
                           'authors': u'Bemporad, A',
                           'page': u'130',
                           'year': u'2010'}])


class TestDataXML(TestCase):
    def create_app(self):
        app_ = app.create_app()
        return app_

    def test_extract_volume_from_journal(self):
        """

        """
        journal, volume = crossref_extract_volume_from_journal('Annual Review of Biophysics and Biophysical Chemistry, vol. 15')
        self.assertTrue(journal == 'Annual Review of Biophysics and Biophysical Chemistry' and volume == '15')

    def test_get_xml_tagged_data(self):
        """

        """
        training_files_path = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')), 'parser/training_files/')
        xml_ref_filenames = [training_files_path + 'S0019103517302440.xml',
                             training_files_path + '10.1073_pnas.1205221109.xref.xml']

        for i, xml_ref_filename in enumerate(xml_ref_filenames):
            with open(xml_ref_filename) as f:
                self.assertTrue(dataXML.train_1[i] == get_xml_tagged_data(f.read().splitlines()))

        # test springer read routine
        with open(training_files_path + 'iss5.springer.xml') as f:
            self.assertTrue(dataXML.train_3 == get_xml_tagged_data(f.read().splitlines()))

        # test when no buffer is passed in
        self.assertTrue(get_xml_tagged_data('') == None)

    def test_get_xml_tagged_data_training(self):
        """

        """
        training_files_path = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')), 'parser/training_files/')
        xml_ref_filenames = [training_files_path + 'S0019103517303470.xml',
                             training_files_path + '10.1371_journal.pone.0048146.xref.xml']

        for i, xml_ref_filename in enumerate(xml_ref_filenames):
            self.assertTrue(dataXML.train_2[i] == get_xml_tagged_data_training(xml_ref_filename))

if __name__ == "__main__":
    unittest.main()
