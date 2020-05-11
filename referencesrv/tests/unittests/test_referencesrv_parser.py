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
#
# class TestCRFClassifier(TestCase):
#     def create_app(self):
#         app_ = app.create_app()
#         return app_
#
#
class TestCRFClassifierText(TestCase):
    def create_app(self):
        app_ = app.create_app()
        return app_

    def test_arxiv_id(self):
        """

        """
        crf_text = CRFClassifierText()
        crf_text.load()

        reference_str = "C. Virgo, B. Abbott et al., GW170817: Observation of Gravitational Waves from a Binary Neutron Star, Phys. Rev. Lett. 119 (2017) 161101, [1710.05832]."
        self.assertEqual(crf_text.parse(reference_str),
                         {'title': 'GW170817 Observation Gravitational Waves',
                          'journal': 'Phys Rev Lett',
                          'arxiv': '1710.05832',
                          'refstr': 'C. Virgo, B. Abbott et al., GW170817: Observation of Gravitational Waves from a Binary Neutron Star, Phys. Rev. Lett. 119 (2017) 161101, [1710.05832].',
                          'volume': '119',
                          'authors': 'C. Virgo, B. Abbott et al.',
                          'year': '2017',
                          'page': '161101'})

    def test_doi(self):
        """

        """
        crf_text = CRFClassifierText()
        crf_text.load()

        reference_str = 'Elisabete da Cunha et al. "The Taipan Galaxy Survey: Scientific Goals and Observing Strat- egy". In: Publications of the Astronomical Society of Australia 34, e047 (2017), e047. DOI: 10. 1017/ pasa. 2017.41. arXiv: 1706.01246.'
        self.assertEqual(crf_text.parse(reference_str),
                         {'doi': u'10.1017/pasa.2017.41',
                          'title': u'The Taipan Galaxy Survey',
                          'journal': u'Publications of the Astronomical Society of Australia',
                          'arxiv': u'arXiv:1706.01246',
                          'refstr': u'Elisabete da Cunha et al. "The Taipan Galaxy Survey: Scientific Goals and Observing Strat- egy". In: Publications of the Astronomical Society of Australia 34, e047 (2017), e047. DOI: 10. 1017/ pasa. 2017.41. arXiv: 1706.01246.',
                          'volume': u'34',
                          'authors': u'Elisabete da Cunha et al.',
                          'year': u'2017',
                          'page': u'e047'})

    def test_no_identifier(self):
        """
        where there is no doi/arxiv/ascl and also no page number
        """
        crf_text = CRFClassifierText()
        crf_text.load()

        reference_str = "Gray, D. F. 1992, The observation and analysis of stellar photospheres., Vol. 20"
        self.assertEqual(crf_text.parse(reference_str),
                         {'volume': u'20',
                          'journal': u'The observation and analysis of stellar photospheres',
                          'year': u'1992',
                          'refstr': u'Gray, D. F. 1992, The observation and analysis of stellar photospheres., Vol. 20',
                          'authors': u'Gray, D. F.'})

    def test_title_journal_variations(self):
        """

        """
        crf_text = CRFClassifierText()
        crf_text.load()

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
        # when both title and journal exists and journal is quoted only
        reference_str = "C. J. Fewster and E.-A. Kontou. A new derivation of singularity theorems with weakened energy hypotheses. 'Class. Quant. Grav.', 37(6):065010, 2020."
        self.assertEqual(crf_text.parse(reference_str),
                         {'title': u'A new derivation of singularity theorems with weakened energy hypotheses',
                          'journal': u'Class Quant Grav',
                          'authors': u'C. J. Fewster and E.-A. Kontou.',
                          'refstr': u"C. J. Fewster and E.-A. Kontou. A new derivation of singularity theorems with weakened energy hypotheses. 'Class. Quant. Grav.', 37(6):065010, 2020.",
                          'volume': u'37',
                          'year': u'2020',
                          'issue': u'6',
                          'page': u'065010'})
        # when both title and journal exists and both are quoted
        reference_str = 'R. Dave, D. N. Spergel, P. J. Steinhardt, and B. D. Wandelt, "Halo properties in cosmological simulations of selfinteracting cold dark matter", "Astrophys. J." 547 (2001) 574-589, [astro-ph/0006218].'
        self.assertEqual(crf_text.parse(reference_str),
                         {'title': u'Halo properties in cosmological simulations of selfinteracting cold dark matter',
                          'journal': u'Astrophys J',
                          'arxiv': u'astro-ph/0006218',
                          'refstr': u'R. Dave, D. N. Spergel, P. J. Steinhardt, and B. D. Wandelt, "Halo properties in cosmological simulations of selfinteracting cold dark matter", "Astrophys. J." 547 (2001) 574-589, [astro-ph/0006218].',
                          'volume': u'547',
                          'authors': u'R. Dave, D. N. Spergel, P. J. Steinhardt, and B. D. Wandelt',
                          'year': u'2001',
                          'page': u'574-589'})
        # when both title and journal exists and title is quoted only
        reference_str = "D. M. Ghilencea, 'Stueckelberg Breaking of Weyl Conformal Geometry and Applications to Gravity', Phys. Rev. D 101 (2020) 045010."
        self.assertEqual(crf_text.parse(reference_str),
                         {'title': u'Stueckelberg Breaking of Weyl Conformal Geometry and Applications to Gravity',
                          'journal': u'Phys Rev D',
                          'authors': u'D. M. Ghilencea',
                          'refstr': u"D. M. Ghilencea, 'Stueckelberg Breaking of Weyl Conformal Geometry and Applications to Gravity', Phys. Rev. D 101 (2020) 045010.",
                          'volume': u'101',
                          'year': u'2020',
                          'page': u'045010'})
        # when both title and journal exits, title is quoted, journal is followed by in possibly
        reference_str = "J. Toomre, \"Some travels in the land of nonlinear convection and magnetism,\" in EAS Publications Series, EAS Publications Series, Vol. 82 (2019) pp. 273-294"
        self.assertEqual(crf_text.parse(reference_str),
                         {'title': u'Some travels in the land of nonlinear convection and magnetism',
                          'journal': u'EAS Publications Series EAS Publications Series',
                          'authors': u'J. Toomre',
                          'refstr': u'J. Toomre, "Some travels in the land of nonlinear convection and magnetism," in EAS Publications Series, EAS Publications Series, Vol. 82 (2019) pp. 273-294',
                          'volume': u'82',
                          'year': u'2019',
                          'page': u'273-294'})
        # when there is a single quote and an apostrophe in title
        reference_str = "F. London, 'Quantum-Mechanical Interpretation of Weyl's Theory', Zeit. Phys. 42 (1927) 375."
        self.assertEqual(crf_text.parse(reference_str),
                         {'title': u"Quantum Mechanical Interpretation of Weyl's Theory",
                          'journal': u'Zeit Phys',
                          'authors': u'F. London',
                          'refstr': u"F. London, 'Quantum-Mechanical Interpretation of Weyl's Theory', Zeit. Phys. 42 (1927) 375.",
                          'volume': u'42',
                          'year': u'1927',
                          'page': u'375'})
        # when there is a space before quote and also the second substring is publication not journal
        reference_str = 'A. R. Liddle and D. H. Lyth, " Cosmological Inflation and Large-Scale Structure", Cambridge University Press, 2000.'
        self.assertEqual(crf_text.parse(reference_str),
                         {'title': u'Cosmological Inflation and Large Scale Structure',
                          'year': u'2000',
                          'refstr': u'A. R. Liddle and D. H. Lyth, " Cosmological Inflation and Large-Scale Structure", Cambridge University Press, 2000.',
                          'authors': u'A. R. Liddle and D. H. Lyth'})
        # when year appears in the title or journal
        reference_str = "Krist, J. E. & Hook, R. N. 1997, in The 1997 HST Calibration Workshop with a New Generation of Instruments, ed. S. Casertano, R. Jedrzejewski, T. Keyes, & M. Stevens, 192"
        self.assertEqual(crf_text.parse(reference_str),
                         {'journal': u'The 1997 HST Calibration Workshop with a New Generation of Instruments',
                          'authors': u'Krist, J. E. & Hook, R. N.',
                          'refstr': u'Krist, J. E. & Hook, R. N. 1997, in The 1997 HST Calibration Workshop with a New Generation of Instruments, ed. S. Casertano, R. Jedrzejewski, T. Keyes, & M. Stevens, 192',
                          'volume': u'192',
                          'year': u'1997'})
        # when there is parenthesis in the middle of title with commas
        reference_str = "J. Miller, M. D. Kruskal and B. B. Godfrey, Taub-NUT (Newman, Unti, Tamburino) metric and incompatible extensions, Physical Review D 4 (1971) 2945."
        self.assertEqual(crf_text.parse(reference_str),
                         {'title': u'Taub NUT Newman Unti Tamburino metric and incompatible extensions',
                          'journal': u'Physical Review D',
                          'authors': u'J. Miller, M. D. Kruskal and B. B. Godfrey',
                          'refstr': u'J. Miller, M. D. Kruskal and B. B. Godfrey, Taub-NUT (Newman, Unti, Tamburino) metric and incompatible extensions, Physical Review D 4 (1971) 2945.',
                          'volume': u'4',
                          'year': u'1971',
                          'page': u'2945'})
        # when the same word is both part of title and journal crf tags all to be either title or all journal
        # have seen this with `and` as well (please see test_journal_only_variations)
        # for this example I have checked and service resolves it
        #   "score": "0.9",
        #   "bibcode": "1960stat.book..282B",
        #   "reference": "Babcock, H. W. 1960, Stellar Magnetic Fields, in Stellar Atmospheres, ed. J. L. Greenstein (Chicago Univ. Press), 282"
        reference_str = "Babcock, H. W. 1960, Stellar Magnetic Fields, in Stellar Atmospheres, ed. J. L. Greenstein (Chicago Univ. Press), 282"
        self.assertEqual(crf_text.parse(reference_str),
                         {'title': u'Magnetic Fields',
                          'journal': u'Stellar Stellar Atmospheres',
                          'authors': u'Babcock, H. W.',
                          'refstr': u'Babcock, H. W. 1960, Stellar Magnetic Fields, in Stellar Atmospheres, ed. J. L. Greenstein (Chicago Univ. Press), 282',
                          'volume': u'282',
                          'year': u'1960'})
        # when there are many dashes, in addition to field specifier in reference
        reference_str = "Schwinger J. S. On gauge invariance and vacuum polarization // Phys. Rev. -- 1951. -- Vol. 82. -- P. 664-679."
        self.assertEqual(crf_text.parse(reference_str),
                         {'title': u'On gauge invariance and vacuum polarization',
                          'journal': u'Phys Rev',
                          'authors': u'Schwinger, J.S.',
                          'refstr': u'Schwinger J. S. On gauge invariance and vacuum polarization // Phys. Rev. -- 1951. -- Vol. 82. -- P. 664-679.',
                          'volume': u'82',
                          'year': u'1951',
                          'page': u'664-679'})
        # reference with NA sections
        reference_str = "B. A. Trubnikov, Particle Interactions in a Fully Ionized Plasma, Reviews of Plasma Physics, Vol. 1 (Consultants Bureau, New York, 1965) p. 105"
        self.assertEqual(crf_text.parse(reference_str),
                         {'title': u'Particle Interactions in a Fully Ionized',
                          'journal': u'Plasma Reviews of Plasma Physics',
                          'authors': u'B. A. Trubnikov',
                          'refstr': u'B. A. Trubnikov, Particle Interactions in a Fully Ionized Plasma, Reviews of Plasma Physics, Vol. 1 (Consultants Bureau, New York, 1965) p. 105',
                          'volume': u'1',
                          'year': u'1965',
                          'page': u'105'})
        # when both title and journal exists and neither is quoted
        # again notice the same word in title and journal that has been tagged to be in journal both times
        reference_str = "B. A. Trubnikov, Particle Interactions in a Fully Ionized Plasma, Reviews of Plasma Physics, Vol. 1 (Consultants Bureau, New York, 1965) p. 105"
        self.assertEqual(crf_text.parse(reference_str),
                         {'title': u'Particle Interactions in a Fully Ionized',
                          'journal': u'Plasma Reviews of Plasma Physics',
                          'authors': u'B. A. Trubnikov',
                          'refstr': u'B. A. Trubnikov, Particle Interactions in a Fully Ionized Plasma, Reviews of Plasma Physics, Vol. 1 (Consultants Bureau, New York, 1965) p. 105',
                          'volume': u'1',
                          'year': u'1965',
                          'page': u'105'})
        # another more complicated reference string, just to be sure....
        reference_str = 'Murayama, M., Nakahashi, K., and Obayashi, S., "Numerical simulation of vortical flows using vorticity confinement with unstructured grid." In 39th Aerospace Sciences Meeting and Exhibit, Reno, NV, Jan. 2001, AIAA paper 2001-0606.'
        self.assertEqual(crf_text.parse(reference_str),
                         {'title': u'Numerical simulation of vortical flows using vorticity confinement with unstructured grid',
                          'journal': u'39th Aerospace Sciences Meeting and Exhibit',
                          'authors': u'Murayama, M., Nakahashi, K., and Obayashi, S.',
                          'refstr': u'Murayama, M., Nakahashi, K., and Obayashi, S., "Numerical simulation of vortical flows using vorticity confinement with unstructured grid." In 39th Aerospace Sciences Meeting and Exhibit, Reno, NV, Jan. 2001, AIAA paper 2001-0606.',
                          'volume': u'0606',
                          'year': u'2001'})
        # when there is a decimal point number in title
        reference_str = "R. Tullmann, P. P. Plucinsky, T. J. Gaetz, P. Slane, J. P. Hughes, I. Harrus, and T. G. Pannuti, Searching for the Pulsar in G18.95-1.1: Discovery of an X-ray Point Source and Associated Synchrotron Nebula with Chandra, Astrophys. J. 720, 848 (2010)"
        self.assertEqual(crf_text.parse(reference_str),
                         {'title': u'Searching for the Pulsar in G18 95 1 1 Discovery ray Point Associated Synchrotron Nebula',
                          'journal': u'Astrophys J',
                          'authors': u'R. Tullmann, P. P. Plucinsky, T. J. Gaetz, P. Slane, J. P. Hughes, I. Harrus, and T. G. Pannuti',
                          'refstr': u'R. Tullmann, P. P. Plucinsky, T. J. Gaetz, P. Slane, J. P. Hughes, I. Harrus, and T. G. Pannuti, Searching for the Pulsar in G18.95-1.1: Discovery of an X-ray Point Source and Associated Synchrotron Nebula with Chandra, Astrophys. J. 720, 848 (2010)',
                          'volume': u'720',
                          'year': u'2010',
                          'page': u'848'})


    def test_journal_only_variations(self):
        """

        """
        crf_text = CRFClassifierText()
        crf_text.load()

        # when title starts with digits
        reference_str = "Desorgher, L., Fluckiger, E. O., & Gurtner, M. 2006, in 36th COSPAR Scientific Assembly, Vol. 36"
        self.assertEqual(crf_text.parse(reference_str),
                         {'volume': u'36',
                          'journal': u'36th COSPAR Scientific Assembly',
                          'year': u'2006',
                          'refstr': u'Desorgher, L., Fluckiger, E. O., & Gurtner, M. 2006, in 36th COSPAR Scientific Assembly, Vol. 36',
                          'authors': u'Desorgher, L., Fluckiger, E. O., & Gurtner, M.'})
        # when there is an editor list following `edited by`
        # note the extra and at the end of journal which is part of editor, but crf has tagged it as journal, possibly becasue
        # was not able to differentiate much between the and that is part of journal and the one that is part of editor, a few words away from each other
        reference_str = "L. Sriramkumar, in Vignettes in Gravitation and Cosmology, edited by L. Sriramkumar and T. Seshadri (World Scientific, Singapore, 2012) pp. 207-249"
        self.assertEqual(crf_text.parse(reference_str),
                         {'journal': u'Vignettes in Gravitation and Cosmology and',
                          'year': u'2012',
                          'page': u'207-249',
                          'refstr': u'L. Sriramkumar, in Vignettes in Gravitation and Cosmology, edited by L. Sriramkumar and T. Seshadri (World Scientific, Singapore, 2012) pp. 207-249',
                          'authors': u'L. Sriramkumar'})
        # when there is an editor list following `ed.`
        reference_str = "Krist, J. E. & Hook, R. N. 1997, in The 1997 HST Calibration Workshop with a New Generation of Instruments, ed. S. Casertano, R. Jedrzejewski, T. Keyes, & M. Stevens, 192"
        self.assertEqual(crf_text.parse(reference_str),
                         {'volume': u'192',
                          'journal': u'The 1997 HST Calibration Workshop with a New Generation of Instruments',
                          'year': u'1997',
                          'refstr': u'Krist, J. E. & Hook, R. N. 1997, in The 1997 HST Calibration Workshop with a New Generation of Instruments, ed. S. Casertano, R. Jedrzejewski, T. Keyes, & M. Stevens, 192',
                          'authors': u'Krist, J. E. & Hook, R. N.'})
        # when journal abbreviation is lower case
        reference_str = "Verela et al., 2016, a&a, 589, 37"
        self.assertEqual(crf_text.parse(reference_str),
                         {'journal': u'a&a',
                          'authors': u'Verela et al.',
                          'refstr': u'Verela et al., 2016, a&a, 589, 37',
                          'volume': u'589',
                          'year': u'2016',
                          'page': u'37'})
        # generic title only reference
        reference_str = "Van Cleve J. E., Caldwell D. A., 2016, Kepler Instrument Handbook (KSCI-19033-002). NASA Ames Research Center"
        self.assertEqual(crf_text.parse(reference_str),
                         {'journal': u'Kepler Instrument Handbook',
                          'year': u'2016',
                          'page': u'19033-002',
                          'refstr': u'Van Cleve J. E., Caldwell D. A., 2016, Kepler Instrument Handbook (KSCI-19033-002). NASA Ames Research Center',
                          'authors': u'Van Cleve J. E., Caldwell D. A.'})
        # having `the` and apostrophe in journal name
        reference_str = "Chakrabarty, D., Jonker, P. G., & Markwardt, C. B. 2008, The Astronomer's Telegram, 1490"
        self.assertEqual(crf_text.parse(reference_str),
                         {'volume': u'1490',
                          'journal': u"The Astronomer's Telegram",
                          'year': u'2008',
                          'refstr': u"Chakrabarty, D., Jonker, P. G., & Markwardt, C. B. 2008, The Astronomer's Telegram, 1490",
                          'authors': u'Chakrabarty, D., Jonker, P. G., & Markwardt, C. B.'})
        # book reference
        reference_str = 'M. E. Peskin and D. V. Schroeder, "An Introduction to Quantum Field Theory". Addison-Wesley, Reading, USA, 1995.'
        self.assertEqual(crf_text.parse(reference_str),
                         {'title': u'An Introduction to Quantum Field Theory',
                          'year': u'1995',
                          'refstr': u'M. E. Peskin and D. V. Schroeder, "An Introduction to Quantum Field Theory". Addison-Wesley, Reading, USA, 1995.',
                          'authors': u'M. E. Peskin and D. V. Schroeder'})

    def test_title_journal_with_errors(self):
        """
        when there are some errors in reference, for example multiple double quotes, or journal stated twice
        still enough information can be extracted to allow matching with records in solr

        """
        crf_text = CRFClassifierText()
        crf_text.load()

        # journal information appear twice
        reference_str = 'Madec, P. Y., Kolb, J., Oberti, S., Paufique, J., La Penna, P., Hackenberg, W., Kuntschner, H., Argomedo, J., Kiekebusch, M., Donaldson, R., Suarez, M., and Arsenault, R., \"Adaptive Optics Facility: control strategy and first on-sky results of the acquisition sequence," in [""Proc. SPIE""], "Society of Photo-Optical Instrumentation Engineers (SPIE) Conference Series" 9909, 99090Z (Jul 2016).'
        self.assertEqual(crf_text.parse(reference_str),
                         {'title': 'Adaptive Optics Facility control strategy sky results acquisition sequence Optical Instrumentation',
                          'journal': 'Proc SPIE SPIE',
                          'authors': 'Madec, P. Y., Kolb, J., Oberti, S., Paufique, J., La Penna, P., Hackenberg, W., Kuntschner, H., Argomedo, J., Kiekebusch, M., Donaldson, R., Suarez, M., and Arsenault, R.',
                          'refstr': 'Madec, P. Y., Kolb, J., Oberti, S., Paufique, J., La Penna, P., Hackenberg, W., Kuntschner, H., Argomedo, J., Kiekebusch, M., Donaldson, R., Suarez, M., and Arsenault, R., "Adaptive Optics Facility: control strategy and first on-sky results of the acquisition sequence," in [""Proc. SPIE""], "Society of Photo-Optical Instrumentation Engineers (SPIE) Conference Series" 9909, 99090Z (Jul 2016).',
                          'volume': '9909',
                          'year': '2016',
                          'page': '99090Z'})
        # when there is a colon after author list
        reference_str = "Colwell, J.E., Esposito, L.W.:  Journal of Geophysical Research: Planets 98(E4), 7387 (1993)"
        self.assertEqual(crf_text.parse(reference_str),
                         {'journal': u'Journal of Geophysical',
                          'authors': u'Colwell, J. E., Esposito, L. W.',
                          'refstr': u'Colwell, J.E., Esposito, L.W.:  Journal of Geophysical Research: Planets 98(E4), 7387 (1993)',
                          'volume': u'98',
                          'year': u'1993',
                          'issue': u'E4',
                          'page': u'7387'})


    def test_having_unknown_url_and_or_month(self):
        """
        where there is a doi and url to the doi, that could complicate tagging doi
        also when there is month of publication which we do not need and want to get tagged as NA

        """
        crf_text = CRFClassifierText()
        crf_text.load()

        reference_str = 'Maxim Pospelov and Yanwen Shang. Lorentz violation in horava-lifshitz-type theories. Phys. Rev. D, 85:105001, May 2012. doi:10.1103/PhysRevD.85.105001. URL https://link.aps.org/doi/10.1103/PhysRevD.85.105001.'
        self.assertEqual(crf_text.parse(reference_str),
                         {'doi': u'10.1103/PhysRevD.85.105001',
                          'title': u'Lorentz violation in horava lifshitz type theories',
                          'journal': u'Phys Rev D',
                          'authors': u'Maxim Pospelov and Yanwen Shang.',
                          'refstr': u'Maxim Pospelov and Yanwen Shang. Lorentz violation in horava-lifshitz-type theories. Phys. Rev. D, 85:105001, May 2012. doi:10.1103/PhysRevD.85.105001. URL https://link.aps.org/doi/10.1103/PhysRevD.85.105001.',
                          'volume': u'85',
                          'year': u'2012',
                          'page': u'105001'})


    def test_no_title(self):
        """

        """
        crf_text = CRFClassifierText()
        crf_text.load()

        reference_str = 'Trujillo et al., 2018. Division for Planetary Sciences, vol 50, #311.09.'
        self.assertEqual(crf_text.parse(reference_str),
                         {'journal': 'Division for Planetary Sciences',
                          'authors': 'Trujillo et al.',
                          'refstr': 'Trujillo et al., 2018. Division for Planetary Sciences, vol 50, #311.09.',
                          'volume': '50',
                          'year': '2018',
                          'page': '311.09'})


    def test_get_num_states(self):
        """

        """
        crf_text = CRFClassifierText()
        crf_text.create_crf()

        self.assertEqual(crf_text.get_num_states(), 39)


    def test_split_reference(self):
        """

        """
        crf_text = CRFClassifierText()
        reference = "K.E. Mesick, W.C. Feldman, E.R. Mullin, L.C. Stonehill, 2020, Icarus, 335, 113397, arXiv:1904.09036, doi:10.1016/j.icarus.2019.113397."
        segment_dict = {'arxiv': 'arXiv:1904.09036', 'doi': 'doi:10.1016/j.icarus.2019.113397', 'page': '113397'}
        self.assertEqual(crf_text.split_reference(reference, segment_dict),
                         ['K', '.', 'E', '.', 'Mesick', ',', 'W', '.', 'C', '.', 'Feldman', ',', 'E', '.', 'R', '.',
                          'Mullin', ',', 'L', '.', 'C', '.', 'Stonehill', ',', '2020', ',', 'Icarus', ',', '335', ',',
                          '113397', ',', 'arXiv', ':', 'arXiv:1904.09036', ',', 'doi', ':',
                          'doi:10.1016/j.icarus.2019.113397', '.'])
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
                         {'arxiv': 'arXiv:1904.09036', 'ascl': '', 'doi': '10.1016/j.icarus.2019.113397', 'issn': '', 'version': ''})

        reference_str = "Czesla, S., Schroter, S., Schneider, C. P., et al. 2019, PyA: Python astronomy-related packages, ascl:1906.010"
        self.assertEqual(CRFClassifierText().identify_ids(reference_str),
                         {'arxiv': '', 'ascl': 'ascl:1906.010', 'doi': '', 'issn': '', 'version': ''})


    def test_identify_authors(self):
        """

        """
        # only last name
        reference_str = 'Trujillo and Sheppard, 2014. Nature 507, p. 471-474.'
        self.assertEqual(CRFClassifierText().identify_authors(reference_str), 'Trujillo and Sheppard')

        # only last name with multi parts
        reference_str = "van der Klis 2000, ARA&A 38, 717"
        self.assertEqual(CRFClassifierText().identify_authors(reference_str), "van der Klis")

        # unable to identify when there is no indication that author list is finished and title/journal is starting
        reference_str = "M. Bander Fractional quantum hall effect in nonuniform magnetic fields (1990) Phys. Rev. B41 9028"
        self.assertEqual(CRFClassifierText().identify_authors(reference_str), "")

        # test author list with initials first and when there is Jr. indicator
        reference_str = 'R. C. Nunes, E. M. Barboza, Jr., E. M. C. Abreu and J. A. Neto, "Probing the cosmological viability of non-gaussian statistics," JCAP 1608, 051 (2016).'
        self.assertEqual(CRFClassifierText().identify_authors(reference_str), "R. C. Nunes, E. M. Barboza, Jr., E. M. C. Abreu and J. A. Neto")

        # test author list with last name first and when there is Jr. indicator
        reference_str = "York, D. G., Adelman, J., Anderson, Jr., J. E., et al. 2000, AJ, 120, 1579"
        self.assertEqual(CRFClassifierText().identify_authors(reference_str), "York, D. G., Adelman, J., Anderson, Jr., J. E., et al.")

        # test author list when first name is spelled out
        reference_str = 'Nicholas H. Brummell, Thomas L. Clune, and Juri Toomre, "Penetration and Overshooting in Turbulent Compressible Convection," Astrophys. J. 570, 825-854 (2002)'
        self.assertEqual(CRFClassifierText().identify_authors(reference_str), "Nicholas H. Brummell, Thomas L. Clune, and Juri Toomre")


    def test_identify_editors(self):
        """

        """
        # when `in` is before the title of the book, then it is followed by editor list, and finally by `eds.`
        reference_str = 'K. S. Thorne, "Gravitational radiation," in "Three hundred years of gravitation", S. W. Hawking and W. Israel, eds., ch. 9, pp. 330-458. Cambridge University Press, Cambridge, 1987.'
        editors, editors_removed = CRFClassifierText().identify_editors(reference_str)
        self.assertEqual(editors, 'S. W. Hawking and W. Israel')
        self.assertEqual(editors_removed, 'K. S. Thorne, "Gravitational radiation," Three hundred years of gravitation", ,ch. 9, pp. 330-458. Cambridge University Press, Cambridge, 1987.')

        # when editors are sandwiched between `in` and `ed.`
        reference_str = 'Novikov I. D., Thorne K. S., 1973, in C. Dewitt & B. S. Dewitt ed., Black Holes (Les Astres Occlus). pp 343-450'
        editors, editors_removed = CRFClassifierText().identify_editors(reference_str)
        self.assertEqual(editors, 'C. Dewitt & B. S. Dewitt')
        self.assertEqual(editors_removed, 'Novikov I. D., Thorne K. S., 1973, Black Holes (Les Astres Occlus). pp 343-450')

        # not all `eds.` are going to signal editors
        reference_str = 'Kiefer, C. Quantum Gravity, 3rd ed.; Oxford University Press: Oxford, UK, 2012. 19'
        editors, editors_removed = CRFClassifierText().identify_editors(reference_str)
        self.assertEqual(editors, '')
        self.assertEqual(editors_removed, reference_str)


    def test_identify_volume_page_issue(self):
        """

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
        crf_xml.create_crf()

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
