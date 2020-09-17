import sys, os
project_home = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../'))
if project_home not in sys.path:
    sys.path.insert(0, project_home)

from flask_testing import TestCase
import unittest

import referencesrv.app as app
from referencesrv.parser.crf import CRFClassifierText
from referencesrv.parser.getDataXML import get_xml_tagged_data, get_xml_tagged_data_training, crossref_extract_volume_from_journal
from stubdata import dataXML

class TestCRFClassifier(TestCase):
    def create_app(self):
        app_ = app.create_app()
        return app_

    def test_get_num_states(self):
        """ test num states """
        crf_text = CRFClassifierText()
        crf_text.create_crf()
        self.assertEqual(crf_text.get_num_states(), 43)


class TestCRFClassifierText(TestCase):

    maxDiff = None

    def create_app(self):
        app_ = app.create_app()
        return app_

    def setUp(self):
        """ executed before each test """
        self.crf_text = CRFClassifierText()
        self.crf_text.load()

    def tearDown(self):
        """ executed after each test """
        pass

    def test_001(self):
        """ test having an arxiv id """
        reference_str = u'C. Virgo, B. Abbott et al., GW170817: Observation of Gravitational Waves from a Binary Neutron Star, Phys. Rev. Lett. 119 (2017) 161101, [1710.05832].'
        self.assertEqual(self.crf_text.parse(reference_str),
                         {'title': u'GW170817: Observation Gravitational Waves Binary Neutron Star',
                          'journal': u'Phys Rev Lett',
                          'arxiv': u'arXiv:1710.05832',
                          'refstr': 'C. Virgo, B. Abbott et al., GW170817: Observation of Gravitational Waves from a Binary Neutron Star, Phys. Rev. Lett. 119 (2017) 161101, [1710.05832].',
                          'volume': '119',
                          'authors': u'C. Virgo, B. Abbott et al.',
                          'year': u'2017',
                          'page': u'161101'})

    def test_002(self):
        """ test having a doi """
        reference_str = u'Elisabete da Cunha et al. "The Taipan Galaxy Survey: Scientific Goals and Observing Strat- egy". In: Publications of the Astronomical Society of Australia 34, e047 (2017), e047. DOI: 10. 1017/ pasa. 2017.41. arXiv: 1706.01246.'
        self.assertEqual(self.crf_text.parse(reference_str),
                         {'doi': u'doi:10.1017/pasa.2017.41',
                          'title': u'Taipan Galaxy Survey: Scientific Goals Observing Strategy',
                          'journal': u'Publications Astronomical Society Australia',
                          'arxiv': u'arXiv:1706.01246',
                          'refstr': u'Elisabete da Cunha et al. "The Taipan Galaxy Survey: Scientific Goals and Observing Strat- egy". In: Publications of the Astronomical Society of Australia 34, e047 (2017), e047. DOI: 10. 1017/ pasa. 2017.41. arXiv: 1706.01246.',
                          'volume': u'34',
                          'authors': u'Elisabete da Cunha et al.',
                          'year': u'2017',
                          'page': u'e047'})

    def test_003(self):
        """ where there is no doi/arxiv/ascl and also no page number """
        reference_str = 'Gray, D. F. 1992, The observation and analysis of stellar photospheres., Vol. 20'
        self.assertEqual(self.crf_text.parse(reference_str),
                         {'volume': u'20',
                          'journal': u'observation analysis stellar photospheres',
                          'year': u'1992',
                          'refstr': u'Gray, D. F. 1992, The observation and analysis of stellar photospheres., Vol. 20',
                          'authors': u'Gray, D. F.'})

    def test_004(self):
        """ having both title and journal and volume, issue and page """
        reference_str = 'Bhattacharya, A., Pati, D., Pillai, N. S., and Dunson, D. B. (2015). Dirichlet Laplace priors for optimal shrinkage. "J. Amer. Statist. Assoc.", 110(512):1479-1490.'
        words, labels = self.crf_text.classify(reference_str)
        self.assertEqual(self.crf_text.reference(reference_str, words, labels),
                         {'title': u'Dirichlet Laplace priors optimal shrinkage',
                          'journal': u'J Amer Statist Assoc',
                          'authors': u'Bhattacharya, A., Pati, D., Pillai, N. S., and Dunson, D. B.',
                          'refstr': u'Bhattacharya, A., Pati, D., Pillai, N. S., and Dunson, D. B. (2015). Dirichlet Laplace priors for optimal shrinkage. "J. Amer. Statist. Assoc.", 110(512):1479-1490.',
                          'volume': u'110',
                          'year': u'2015',
                          'issue': u'512',
                          'page': u'1479-1490'})

    def test_005(self):
        """ when both title and journal exists and journal is quoted only """
        reference_str = "C. J. Fewster and E.-A. Kontou. A new derivation of singularity theorems with weakened energy hypotheses. 'Class. Quant. Grav.', 37(6):065010, 2020."
        self.assertEqual(self.crf_text.parse(reference_str),
                         {'title': u'new derivation singularity theorems weakened energy hypotheses',
                          'journal': u'Class Quant Grav',
                          'authors': u'C. J. Fewster and E. A. Kontou.',
                          'refstr': u"C. J. Fewster and E.-A. Kontou. A new derivation of singularity theorems with weakened energy hypotheses. 'Class. Quant. Grav.', 37(6):065010, 2020.",
                          'volume': u'37',
                          'year': u'2020',
                          'issue': u'6',
                          'page': u'065010'})

    def test_006(self):
        """ when both title and journal exists and both are quoted """
        reference_str = 'R. Dave, D. N. Spergel, P. J. Steinhardt, and B. D. Wandelt, "Halo properties in cosmological simulations of selfinteracting cold dark matter", "Astrophys. J." 547 (2001) 574-589, [astro-ph/0006218].'
        self.assertEqual(self.crf_text.parse(reference_str),
                         {'title': u'Halo properties cosmological simulations selfinteracting cold dark matter',
                          'journal': u'Astrophys J',
                          'arxiv': u'arXiv:astro-ph/0006218',
                          'refstr': u'R. Dave, D. N. Spergel, P. J. Steinhardt, and B. D. Wandelt, "Halo properties in cosmological simulations of selfinteracting cold dark matter", "Astrophys. J." 547 (2001) 574-589, [astro-ph/0006218].',
                          'volume': u'547',
                          'authors': u'R. Dave, D. N. Spergel, P. J. Steinhardt, and B. D. Wandelt',
                          'year': u'2001',
                          'page': u'574-589'})

    def test_007(self):
        """ when both title and journal exists and title is quoted only """
        reference_str = "D. M. Ghilencea, 'Stueckelberg Breaking of Weyl Conformal Geometry and Applications to Gravity', Phys. Rev. D 101 (2020) 045010."
        self.assertEqual(self.crf_text.parse(reference_str),
                         {'title': u'Stueckelberg Breaking Weyl Conformal Geometry Applications Gravity',
                          'journal': u'Phys Rev D',
                          'authors': u'D. M. Ghilencea',
                          'refstr': u"D. M. Ghilencea, 'Stueckelberg Breaking of Weyl Conformal Geometry and Applications to Gravity', Phys. Rev. D 101 (2020) 045010.",
                          'volume': u'101',
                          'year': u'2020',
                          'page': u'045010'})

    def test_008(self):
        """ when both title and journal exits, title is quoted, journal is followed by in possibly """
        reference_str = 'J. Toomre, "Some travels in the land of nonlinear convection and magnetism," in EAS Publications Series, EAS Publications Series, Vol. 82 (2019) pp. 273-294'
        self.assertEqual(self.crf_text.parse(reference_str),
                         {'title': u'travels land nonlinear convection magnetism',
                          'journal': u'EAS Publications Series',
                          'authors': u'J. Toomre',
                          'refstr': u'J. Toomre, "Some travels in the land of nonlinear convection and magnetism," in EAS Publications Series, EAS Publications Series, Vol. 82 (2019) pp. 273-294',
                          'volume': u'82',
                          'year': u'2019',
                          'page': u'273-294'})

    def test_009(self):
        """ when there is a single quote and an apostrophe in title """
        reference_str = "F. London, 'Quantum-Mechanical Interpretation of Weyl's Theory', Zeit. Phys. 42 (1927) 375."
        self.assertEqual(self.crf_text.parse(reference_str),
                         {'title': u"Quantum-Mechanical Interpretation Weyl Theory",
                          'journal': u'Zeit Phys',
                          'authors': u'F. London',
                          'refstr': u"F. London, 'Quantum-Mechanical Interpretation of Weyl's Theory', Zeit. Phys. 42 (1927) 375.",
                          'volume': u'42',
                          'year': u'1927',
                          'page': u'375'})

    def test_010(self):
        """ when there is a space before quote and also the second substring is publication not journal """
        reference_str = 'A. R. Liddle and D. H. Lyth, " Cosmological Inflation and Large-Scale Structure", Cambridge University Press, 2000.'
        self.assertEqual(self.crf_text.parse(reference_str),
                         {'title': u'Cosmological Inflation Large-Scale Structure',
                          'year': u'2000',
                          'refstr': u'A. R. Liddle and D. H. Lyth, " Cosmological Inflation and Large-Scale Structure", Cambridge University Press, 2000.',
                          'authors': u'A. R. Liddle and D. H. Lyth'})

    def test_011(self):
        """ when year appears in the title or journal """
        reference_str = "Krist, J. E. & Hook, R. N. 1997, in The 1997 HST Calibration Workshop with a New Generation of Instruments, ed. S. Casertano, R. Jedrzejewski, T. Keyes, & M. Stevens, 192"
        self.assertEqual(self.crf_text.parse(reference_str),
                         {'title': u'1997 HST Calibration Workshop New Generation Instruments',
                          'authors': u'Krist, J. E. and Hook, R. N.',
                          'refstr': u'Krist, J. E. & Hook, R. N. 1997, in The 1997 HST Calibration Workshop with a New Generation of Instruments, ed. S. Casertano, R. Jedrzejewski, T. Keyes, & M. Stevens, 192',
                          'volume': u'192',
                          'year': u'1997'})

    def test_012(self):
        """ when there is parenthesis in the middle of title with commas """
        reference_str = 'J. Miller, M. D. Kruskal and B. B. Godfrey, Taub-NUT (Newman, Unti, Tamburino) metric and incompatible extensions, Physical Review D 4 (1971) 2945.'
        self.assertEqual(self.crf_text.parse(reference_str),
                         {'title': u'Taub-NUT Newman Unti Tamburino metric incompatible extensions',
                          'journal': u'Physical Review D',
                          'authors': u'J. Miller, M. D. Kruskal and B. B. Godfrey',
                          'refstr': u'J. Miller, M. D. Kruskal and B. B. Godfrey, Taub-NUT (Newman, Unti, Tamburino) metric and incompatible extensions, Physical Review D 4 (1971) 2945.',
                          'volume': u'4',
                          'year': u'1971',
                          'page': u'2945'})

    def test_013(self):
        """
        when the same word is both part of title and journal crf tags all to be either title or all journal
        have seen this with `and` as well (please see test_journal_only_variations)
        for this example I have checked and service resolves it
          "score": "0.9",
          "bibcode": "1960stat.book..282B",
          "reference": "Babcock, H. W. 1960, Stellar Magnetic Fields, in Stellar Atmospheres, ed. J. L. Greenstein (Chicago Univ. Press), 282"
        """
        reference_str = 'Babcock, H. W. 1960, Stellar Magnetic Fields, in Stellar Atmospheres, ed. J. L. Greenstein (Chicago Univ. Press), 282'
        self.assertEqual(self.crf_text.parse(reference_str),
                         {'title': u'Magnetic Fields',
                          'journal': u'Stellar Atmospheres',
                          'authors': u'Babcock, H. W.',
                          'refstr': u'Babcock, H. W. 1960, Stellar Magnetic Fields, in Stellar Atmospheres, ed. J. L. Greenstein (Chicago Univ. Press), 282',
                          'volume': u'282',
                          'year': u'1960'})

    def test_014(self):
        """ when there are many dashes, in addition to field specifier in reference """
        reference_str = 'Schwinger J. S. On gauge invariance and vacuum polarization // Phys. Rev. -- 1951. -- Vol. 82. -- P. 664-679.'
        self.assertEqual(self.crf_text.parse(reference_str),
                         {'title': u'gauge invariance vacuum polarization',
                          'journal': u'Phys Rev',
                          'authors': u'Schwinger J. S.',
                          'refstr': u'Schwinger J. S. On gauge invariance and vacuum polarization // Phys. Rev. -- 1951. -- Vol. 82. -- P. 664-679.',
                          'volume': u'82',
                          'year': u'1951',
                          'page': u'664-679'})

    def test_015(self):
        """ reference with NA sections """
        reference_str = 'B. A. Trubnikov, Particle Interactions in a Fully Ionized Plasma, Reviews of Plasma Physics, Vol. 1 (Consultants Bureau, New York, 1965) p. 105'
        self.assertEqual(self.crf_text.parse(reference_str),
                         {'title': u'Particle Interactions Fully Ionized',
                          'journal': u'Plasma Reviews Physics',
                          'authors': u'B. A. Trubnikov',
                          'refstr': u'B. A. Trubnikov, Particle Interactions in a Fully Ionized Plasma, Reviews of Plasma Physics, Vol. 1 (Consultants Bureau, New York, 1965) p. 105',
                          'volume': u'1',
                          'year': u'1965',
                          'page': u'105'})

    def test_016(self):
        """ when both title and journal exists and neither is quoted """
        # note the same word in title and journal that has been tagged to be in journal both times
        reference_str = 'B. A. Trubnikov, Particle Interactions in a Fully Ionized Plasma, Reviews of Plasma Physics, Vol. 1 (Consultants Bureau, New York, 1965) p. 105'
        self.assertEqual(self.crf_text.parse(reference_str),
                         {'title': u'Particle Interactions Fully Ionized',
                          'journal': u'Plasma Reviews Physics',
                          'authors': u'B. A. Trubnikov',
                          'refstr': u'B. A. Trubnikov, Particle Interactions in a Fully Ionized Plasma, Reviews of Plasma Physics, Vol. 1 (Consultants Bureau, New York, 1965) p. 105',
                          'volume': u'1',
                          'year': u'1965',
                          'page': u'105'})

    def test_017(self):
        """ another more complicated reference string, just to be sure.... """
        reference_str = 'Murayama, M., Nakahashi, K., and Obayashi, S., "Numerical simulation of vortical flows using vorticity confinement with unstructured grid." In 39th Aerospace Sciences Meeting and Exhibit, Reno, NV, Jan. 2001, AIAA paper 2001-0606.'
        self.assertEqual(self.crf_text.parse(reference_str),
                         {'title': u'Numerical simulation vortical flows using vorticity confinement unstructured grid',
                          'journal': u'39th Aerospace Sciences Meeting Exhibit',
                          'authors': u'Murayama, M., Nakahashi, K., and Obayashi, S.',
                          'refstr': u'Murayama, M., Nakahashi, K., and Obayashi, S., "Numerical simulation of vortical flows using vorticity confinement with unstructured grid." In 39th Aerospace Sciences Meeting and Exhibit, Reno, NV, Jan. 2001, AIAA paper 2001-0606.',
                          'year': u'2001'})

    def test_018(self):
        """ when there is a decimal point number in title """
        reference_str = 'R. Tullmann, P. P. Plucinsky, T. J. Gaetz, P. Slane, J. P. Hughes, I. Harrus, and T. G. Pannuti, Searching for the Pulsar in G18.95-1.1: Discovery of an X-ray Point Source and Associated Synchrotron Nebula with Chandra, Astrophys. J. 720, 848 (2010)'
        self.assertEqual(self.crf_text.parse(reference_str),
                         {'title': u'Searching Pulsar G18 95-1: Discovery X-ray Point Source Associated Synchrotron Nebula Chandra',
                          'journal': u'Astrophys J',
                          'authors': u'R. Tullmann, P. P. Plucinsky, T. J. Gaetz, P. Slane, J. P. Hughes, I. Harrus, and T. G. Pannuti',
                          'refstr': u'R. Tullmann, P. P. Plucinsky, T. J. Gaetz, P. Slane, J. P. Hughes, I. Harrus, and T. G. Pannuti, Searching for the Pulsar in G18.95-1.1: Discovery of an X-ray Point Source and Associated Synchrotron Nebula with Chandra, Astrophys. J. 720, 848 (2010)',
                          'volume': u'720',
                          'year': u'2010',
                          'page': u'848'})

    def test_019(self):
        """ when title starts with digits  """
        reference_str = 'Desorgher, L., Fluckiger, E. O., & Gurtner, M. 2006, in 36th COSPAR Scientific Assembly, Vol. 36'
        self.assertEqual(self.crf_text.parse(reference_str),
                         {'volume': u'36',
                          'journal': u'36th COSPAR Scientific Assembly',
                          'year': u'2006',
                          'refstr': u'Desorgher, L., Fluckiger, E. O., & Gurtner, M. 2006, in 36th COSPAR Scientific Assembly, Vol. 36',
                          'authors': u'Desorgher, L., Fluckiger, E. O., and Gurtner, M.'})

    def test_020(self):
        """ when there is an editor list following `edited by` """
        # note the extra and at the end of journal which is part of editor, but crf has tagged it as journal, possibly becasue
        # was not able to differentiate much between the and that is part of journal and the one that is part of editor, a few words away from each other
        reference_str = 'L. Sriramkumar, in Vignettes in Gravitation and Cosmology, edited by L. Sriramkumar and T. Seshadri (World Scientific, Singapore, 2012) pp. 207-249'
        self.assertEqual(self.crf_text.parse(reference_str),
                         {'title': u'Vignettes Gravitation Cosmology',
                          'year': u'2012',
                          'page': u'207-249',
                          'refstr': u'L. Sriramkumar, in Vignettes in Gravitation and Cosmology, edited by L. Sriramkumar and T. Seshadri (World Scientific, Singapore, 2012) pp. 207-249',
                          'authors': u'L. Sriramkumar'})

    def test_021(self):
        """ when there is an editor list following `ed.` """
        reference_str = 'Krist, J. E. & Hook, R. N. 1997, in The 1997 HST Calibration Workshop with a New Generation of Instruments, ed. S. Casertano, R. Jedrzejewski, T. Keyes, & M. Stevens, 192'
        self.assertEqual(self.crf_text.parse(reference_str),
                         {'volume': u'192',
                          'title': u'1997 HST Calibration Workshop New Generation Instruments',
                          'year': u'1997',
                          'refstr': u'Krist, J. E. & Hook, R. N. 1997, in The 1997 HST Calibration Workshop with a New Generation of Instruments, ed. S. Casertano, R. Jedrzejewski, T. Keyes, & M. Stevens, 192',
                          'authors': u'Krist, J. E. and Hook, R. N.'})

    def test_022(self):
        """ when journal abbreviation is lower case """
        reference_str = 'Verela et al., 2016, a&a, 589, 37'
        self.assertEqual(self.crf_text.parse(reference_str),
                         {'journal': u'a&a',
                          'authors': u'Verela et al.',
                          'refstr': u'Verela et al., 2016, a&a, 589, 37',
                          'volume': u'589',
                          'year': u'2016',
                          'page': u'37'})

    def test_023(self):
        """ generic title only reference """
        reference_str = u"Van Cleve J. E., Caldwell D. A., 2016, Kepler Instrument Handbook (KSCI-19033-002). NASA Ames Research Center"
        self.assertEqual(self.crf_text.parse(reference_str),
                         {'journal': u'Kepler Instrument Handbook',
                          'year': u'2016',
                          'refstr': u'Van Cleve J. E., Caldwell D. A., 2016, Kepler Instrument Handbook (KSCI-19033-002). NASA Ames Research Center',
                          'authors': u'Van Cleve J. E., Caldwell D. A.'})

    def test_024(self):
        """ having `the` and apostrophe in journal name """
        reference_str = "Chakrabarty, D., Jonker, P. G., & Markwardt, C. B. 2008, The Astronomer's Telegram, 1490"
        self.assertEqual(self.crf_text.parse(reference_str),
                         {'volume': u'1490',
                          'journal': u"Astronomer Telegram",
                          'year': u'2008',
                          'refstr': u"Chakrabarty, D., Jonker, P. G., & Markwardt, C. B. 2008, The Astronomer's Telegram, 1490",
                          'authors': u'Chakrabarty, D., Jonker, P. G., and Markwardt, C. B.'})

    def test_025(self):
        """ book reference """
        reference_str = 'M. E. Peskin and D. V. Schroeder, "An Introduction to Quantum Field Theory". Addison-Wesley, Reading, USA, 1995.'
        self.assertEqual(self.crf_text.parse(reference_str),
                         {'title': u'Introduction Quantum Field Theory',
                          'year': u'1995',
                          'refstr': u'M. E. Peskin and D. V. Schroeder, "An Introduction to Quantum Field Theory". Addison-Wesley, Reading, USA, 1995.',
                          'authors': u'M. E. Peskin and D. V. Schroeder'})

    def test_026(self):
        """ when there is year is alphanumeric """
        reference_str = 'Krause, O., Birkmann, S. M., Usuda, T., et al. 2008a, Science, 320, 1195'
        self.assertEqual(self.crf_text.parse(reference_str),
                         {'journal': u'Science',
                          'authors': u'Krause, O., Birkmann, S. M., Usuda, T., et al.',
                          'refstr': u'Krause, O., Birkmann, S. M., Usuda, T., et al. 2008a, Science, 320, 1195',
                          'volume': u'320',
                          'year': u'2008a',
                          'page': u'1195'})

    def test_027(self):
        """ when there is a url that is not useful """
        reference_str = 'Fesen, R. A., Hammell, M. C., Morse, J., et al. 2006, The Astrophysical Journal, 645, 283. http://stacks.iop.org/0004-637X/645/i=1/a=283'
        self.assertEqual(self.crf_text.parse(reference_str),
                         {'journal': u'Astrophysical Journal',
                          'authors': u'Fesen, R. A., Hammell, M. C., Morse, J., et al.',
                          'refstr': u'Fesen, R. A., Hammell, M. C., Morse, J., et al. 2006, The Astrophysical Journal, 645, 283. http://stacks.iop.org/0004-637X/645/i=1/a=283',
                          'volume': u'645',
                          'year': u'2006',
                          'page': u'283'})

    def test_028(self):
        """ journal information appear twice """
        # when there are some errors in reference, still enough information can be extracted
        # to allow matching with records in solr
        reference_str = 'Madec, P. Y., Kolb, J., Oberti, S., Paufique, J., La Penna, P., Hackenberg, W., Kuntschner, H., Argomedo, J., Kiekebusch, M., Donaldson, R., Suarez, M., and Arsenault, R., "Adaptive Optics Facility: control strategy and first on-sky results of the acquisition sequence Photo-Optical," in [""Proc. SPIE""], "Society of Photo-Optical Instrumentation Engineers (SPIE) Conference Series" 9909, 99090Z (Jul 2016).'
        self.assertEqual(self.crf_text.parse(reference_str),
                         {'title': 'Adaptive Optics Facility: control strategy first results acquisition sequence Photo-Optical',
                          'journal': 'Proc SPIE Society Instrumentation Engineers Conference Series',
                          'authors': 'Madec, P. Y., Kolb, J., Oberti, S., Paufique, J., La Penna, P., Hackenberg, W., Kuntschner, H., Argomedo, J., Kiekebusch, M., Donaldson, R., Suarez, M., and Arsenault, R.',
                          'refstr': 'Madec, P. Y., Kolb, J., Oberti, S., Paufique, J., La Penna, P., Hackenberg, W., Kuntschner, H., Argomedo, J., Kiekebusch, M., Donaldson, R., Suarez, M., and Arsenault, R., "Adaptive Optics Facility: control strategy and first on-sky results of the acquisition sequence Photo-Optical," in [""Proc. SPIE""], "Society of Photo-Optical Instrumentation Engineers (SPIE) Conference Series" 9909, 99090Z (Jul 2016).',
                          'volume': '9909',
                          'year': '2016',
                          'page': '99090Z'})

    def test_029(self):
        """ when there is a colon after author list """
        # when there are some errors in reference, for example multiple double quotes, or journal stated twice
        # still enough information can be extracted to allow matching with records in solr
        reference_str = 'Colwell, J.E., Esposito, L.W.:  Journal of Geophysical Research: Planets 98(E4), 7387 (1993)'
        self.assertEqual(self.crf_text.parse(reference_str),
                         {'journal': u'Journal Geophysical',
                          'authors': u'Colwell, J. E., Esposito, L. W.',
                          'refstr': u'Colwell, J.E., Esposito, L.W.:  Journal of Geophysical Research: Planets 98(E4), 7387 (1993)',
                          'volume': u'98',
                          'year': u'1993',
                          'issue': u'E4',
                          'page': u'7387'})

    def test_030(self):
        """ where there is a doi and url to the doi, that could complicate tagging doi
        also when there is month of publication which we do not need and want to get tagged as NA """
        reference_str = 'Maxim Pospelov and Yanwen Shang. Lorentz violation in horava-lifshitz-type theories. Phys. Rev. D, 85:105001, May 2012. doi:10.1103/PhysRevD.85.105001. URL https://link.aps.org/doi/10.1103/PhysRevD.85.105001.'
        self.assertEqual(self.crf_text.parse(reference_str),
                         {'doi': u'doi:10.1103/PhysRevD.85.105001',
                          'title': u'Lorentz violation horava-lifshitz-type theories',
                          'journal': u'Phys Rev D',
                          'authors': u'Maxim Pospelov and Yanwen Shang.',
                          'refstr': u'Maxim Pospelov and Yanwen Shang. Lorentz violation in horava-lifshitz-type theories. Phys. Rev. D, 85:105001, May 2012. doi:10.1103/PhysRevD.85.105001. URL https://link.aps.org/doi/10.1103/PhysRevD.85.105001.',
                          'volume': u'85',
                          'year': u'2012',
                          'page': u'105001'})

    def test_031(self):
        """ with no title """
        reference_str = 'Trujillo et al., 2018. Division for Planetary Sciences, vol 50, #311.09.'
        self.assertEqual(self.crf_text.parse(reference_str),
                         {'journal': 'Division Planetary Sciences',
                          'authors': 'Trujillo et al.',
                          'refstr': 'Trujillo et al., 2018. Division for Planetary Sciences, vol 50, #311.09.',
                          'volume': '50',
                          'year': '2018',
                          'page': '311.09'})

    def test_032(self):
        """ test for having both doi and arxiv nums """
        reference_str = 'K.E. Mesick, W.C. Feldman, E.R. Mullin, L.C. Stonehill, 2020, Icarus, 335, 113397, arXiv:1904.09036, doi:10.1016/j.icarus.2019.113397.'
        self.assertEqual(self.crf_text.parse(reference_str),
                         {'doi': u'doi:10.1016/j.icarus.2019.113397',
                          'journal': u'Icarus',
                          'arxiv': u'arXiv:1904.09036',
                          'refstr': u'K.E. Mesick, W.C. Feldman, E.R. Mullin, L.C. Stonehill, 2020, Icarus, 335, 113397, arXiv:1904.09036, doi:10.1016/j.icarus.2019.113397.',
                          'volume': u'335',
                          'authors': u'K. E. Mesick, W. C. Feldman, E. R. Mullin, L. C. Stonehill',
                          'year': u'2020',
                          'page': u'113397'})

    def test_033(self):
        """ test for having ascl id """
        reference_str = 'Czesla, S., Schroter, S., Schneider, C. P., et al. 2019, PyA: Python astronomy-related packages, ascl:1906.010'
        self.assertEqual(self.crf_text.parse(reference_str),
                         {'ascl': 'ascl:1906.010',
                          'year': '2019',
                          'title': 'PyA: Python astronomy-related packages',
                          'refstr': 'Czesla, S., Schroter, S., Schneider, C. P., et al. 2019, PyA: Python astronomy-related packages, ascl:1906.010',
                          'authors': 'Czesla, S., Schroter, S., Schneider, C. P., et al.'})

    def test_034(self):
        """ test when having last name only """
        reference_str = 'Trujillo and Sheppard, 2014. Nature 507, p. 471-474.'
        self.assertEqual(self.crf_text.parse(reference_str),
                         {'journal': 'Nature',
                          'authors': 'Trujillo and Sheppard',
                          'refstr': 'Trujillo and Sheppard, 2014. Nature 507, p. 471-474.', 'volume': '507',
                          'year': '2014',
                          'page': '471-474'})

    def test_035(self):
        """ only last name with multi parts, note that the first """
        reference_str = 'van der Klis 2000, ARA&A 38, 717'
        self.assertEqual(self.crf_text.parse(reference_str),
                         {'journal': 'ARA&A',
                          'authors': 'van der Klis',
                          'refstr': 'van der Klis 2000, ARA&A 38, 717',
                          'volume': '38',
                          'year': '2000',
                          'page': '717'})

    def test_036(self):
        """ imperfect reference string causing issue with identify author when
        there is no indication that author list is finished and title/journal is starting
        this would cause the first word from title/journal to be included in the author since
        it thinks there are two part last name """
        reference_str = 'M. Bander Fractional quantum hall effect in nonuniform magnetic fields (1990) Phys. Rev. B41 9028'
        self.assertEqual(self.crf_text.parse(reference_str),
                         {'journal': 'quantum hall effect nonuniform magnetic fields',
                          'authors': 'M. Bander Fractional',
                          'refstr': 'M. Bander Fractional quantum hall effect in nonuniform magnetic fields (1990) Phys. Rev. B41 9028',
                          'volume': 'B41',
                          'year': '1990',
                          'page': '9028'})

    def test_037(self):
        """ test with author list with initials first and having `Jr.` """
        reference_str = 'R. C. Nunes, E. M. Barboza, Jr., E. M. C. Abreu and J. A. Neto, "Probing the cosmological viability of non-gaussian statistics," JCAP 1608, 051 (2016).'
        self.assertEqual(self.crf_text.parse(reference_str),
                         {'title': 'Probing cosmological viability non-gaussian statistics',
                          'journal': 'JCAP',
                          'authors': 'R. C. Nunes, E. M. Barboza, Jr., E. M. C. Abreu and J. A. Neto',
                          'refstr': 'R. C. Nunes, E. M. Barboza, Jr., E. M. C. Abreu and J. A. Neto, "Probing the cosmological viability of non-gaussian statistics," JCAP 1608, 051 (2016).',
                          'volume': '1608',
                          'year': '2016',
                          'page': '051'})

    def test_038(self):
        """ test with last name first and having `Jr.` """
        reference_str = 'York, D. G., Adelman, J., Anderson, Jr., J. E., et al. 2000, AJ, 120, 1579'
        self.assertEqual(self.crf_text.parse(reference_str),
                         {'journal': 'AJ',
                          'authors': 'York, D. G., Adelman, J., Anderson, Jr., J. E., et al.',
                          'refstr': 'York, D. G., Adelman, J., Anderson, Jr., J. E., et al. 2000, AJ, 120, 1579',
                          'volume': '120',
                          'year': '2000',
                          'page': '1579'})

    def test_039(self):
        """ test with having full first name """
        reference_str = 'Nicholas H. Brummell, Thomas L. Clune, and Juri Toomre, "Penetration and Overshooting in Turbulent Compressible Convection," Astrophys. J. 570, 825-854 (2002)'
        self.assertEqual(self.crf_text.parse(reference_str),
                         {'title': 'Penetration Overshooting Turbulent Compressible Convection',
                          'journal': 'Astrophys J',
                          'authors': 'Nicholas H. Brummell, Thomas L. Clune, and Juri Toomre',
                          'refstr': 'Nicholas H. Brummell, Thomas L. Clune, and Juri Toomre, "Penetration and Overshooting in Turbulent Compressible Convection," Astrophys. J. 570, 825-854 (2002)',
                          'volume': '570',
                          'year': '2002',
                          'page': '825-854'})

    def test_040(self):
        """ test when collaborators is listed in addition and after the authors """
        reference_str = 'B.P. Abbott, et al., [LIGO/Virgo Collaborations], AS- TROPHYSICAL IMPLICATIONS OF THE BINARY BLACK HOLE MERGER GW150914, Astrophys. J. Lett. 818, L22 (2016)'
        self.assertEqual(self.crf_text.parse(reference_str),
                         {'title': 'ASTROPHYSICAL IMPLICATIONS BINARY BLACK HOLE MERGER GW150914',
                          'journal': 'Astrophys J Lett',
                          'authors': 'B. P. Abbott, et al., LIGO / Virgo Collaborations',
                          'refstr': 'B.P. Abbott, et al., [LIGO/Virgo Collaborations], AS- TROPHYSICAL IMPLICATIONS OF THE BINARY BLACK HOLE MERGER GW150914, Astrophys. J. Lett. 818, L22 (2016)',
                          'volume': '818',
                          'year': '2016',
                          'page': 'L22'})

    def test_041(self):
        """ test when there is a hypen in collaborators """
        reference_str = 'K. Akiyama, et al., [The Event Horizon Telescope Col- laboration], First M87 Event Horizon Telescope Results. I. The Shadow of the Supermassive Black Hole, Astro- phys. J. L. 875, L1 (2019).'
        self.assertEqual(self.crf_text.parse(reference_str),
                         {'title': 'First M87 Event Horizon Telescope Results Shadow Supermassive Black Hole',
                          'journal': 'Astrophys J L',
                          'authors': 'K. Akiyama, et al., Event Horizon Telescope Collaboration',
                          'refstr': 'K. Akiyama, et al., [The Event Horizon Telescope Col- laboration], First M87 Event Horizon Telescope Results. I. The Shadow of the Supermassive Black Hole, Astro- phys. J. L. 875, L1 (2019).',
                          'volume': '875',
                          'year': '2019',
                          'page': 'L1'})

    def test_042(self):
        """ test capturing editor, when `in` is before the title of the book, then it is followed by editor list, and finally by `eds.` """
        reference_str = 'K. S. Thorne, "Gravitational radiation," in "Three hundred years of gravitation", S. W. Hawking and W. Israel, eds., ch. 9, pp. 330-458. Cambridge University Press, Cambridge, 1987.'
        self.crf_text.parse(reference_str)
        self.assertEqual(self.crf_text.originator_token.remove_editors(reference_str),
                         'K. S. Thorne, "Gravitational radiation," Three hundred years of gravitation", ,ch. 9, pp. 330-458. Cambridge University Press, Cambridge, 1987.')

    def test_043(self):
        """ test capturing editor, when editors are sandwiched between `in` and `ed.` """
        reference_str = 'Novikov I. D., Thorne K. S., 1973, in C. Dewitt & B. S. Dewitt ed., Black Holes (Les Astres Occlus). pp 343-450'
        self.crf_text.parse(reference_str)
        self.assertEqual(self.crf_text.originator_token.remove_editors(reference_str),
                         'Novikov I. D., Thorne K. S., 1973, Black Holes (Les Astres Occlus). pp 343-450')

    def test_044(self):
        """ test capturing editor, note that not all `eds.` are going to signal editors, hence no editor here """
        reference_str = 'Kiefer, C. Quantum Gravity, 3rd ed.; Oxford University Press: Oxford, UK, 2012. 19'
        self.crf_text.parse(reference_str)
        self.assertEqual(self.crf_text.originator_token.remove_editors(reference_str), reference_str)

    def test_045(self):
        """ test identifying `volume:page` pattern """
        reference_str = 'Arzoumanian, D., Andre, P., et al., 2019. Astronomy & Astrophysics, 621:A42'
        parsed_record = self.crf_text.parse(reference_str)
        self.assertEqual(parsed_record['volume'], '621')
        self.assertEqual(parsed_record['page'], 'A42')
        self.assertEqual(parsed_record.get('issue', ''), '')

    def test_046(self):
        """ test identifying `volume issue:page` pattern """
        reference_str = 'J. P. Perez-Beaupuits, R. Gusten, M. Spaans, V. Ossenkopf, K. M. Menten, M. A. Requena-Torres, et al. Disentangling the excitation conditions of the dense gas in M17 SW. "A&A", 10 583:A107, November 2015.'
        parsed_record = self.crf_text.parse(reference_str)
        self.assertEqual(parsed_record['volume'], '10')
        self.assertEqual(parsed_record['page'], 'A107')
        self.assertEqual(parsed_record['issue'], '583')

    def test_047(self):
        """ test identifying `volume:page_start-page_end` pattern """
        reference_str = 'M. Houde, P. Bastien, J. L. Dotson, C. D. Dowell, R. H. Hildebrand, R. Peng, et al. On the Measurement of the Magnitude and Orientation of the Magnetic Field in Molecular Clouds. "ApJ", 569:803-814, April 2002.'
        parsed_record = self.crf_text.parse(reference_str)
        self.assertEqual(parsed_record['volume'], '569')
        self.assertEqual(parsed_record['page'], '803-814')
        self.assertEqual(parsed_record.get('issue', ''), '')

    def test_048(self):
        """ test when there are two arxiv identifiers """
        reference_str = 'Keaton J. Burns, Geoffrey M. Vasil, Jeffrey S. Oishi, Daniel Lecoanet, and Benjamin P. Brown, "Dedalus: A Flexible Framework for Numerical Simulations with Spectral Methods," arXiv e-prints , arXiv:1905.10388 (2019), arXiv:1905.10388 [astro-ph.IM]'
        self.assertEqual(self.crf_text.parse(reference_str),
                         {'title': u'Dedalus: Flexible Framework Numerical Simulations Spectral Methods',
                          'journal': u'e-prints',
                          'arxiv': u'arXiv:1905.10388',
                          'refstr': u'Keaton J. Burns, Geoffrey M. Vasil, Jeffrey S. Oishi, Daniel Lecoanet, and Benjamin P. Brown, "Dedalus: A Flexible Framework for Numerical Simulations with Spectral Methods," arXiv e-prints , arXiv:1905.10388 (2019), arXiv:1905.10388 [astro-ph.IM]',
                          'authors': u'Keaton J. Burns, Geoffrey M. Vasil, Jeffrey S. Oishi, Daniel Lecoanet, and Benjamin P. Brown',
                          'year': u'2019'})

    def test_049(self):
        """ test splitting the reference when there are doi/arxiv identifiers """
        reference_str = "K.E. Mesick, W.C. Feldman, E.R. Mullin, L.C. Stonehill, 2020, Icarus, 335, 113397, arXiv:1904.09036, doi:10.1016/j.icarus.2019.113397."
        self.assertEqual(self.crf_text.tokenize(reference_str),
                         ['K', '.', 'E', '.', 'Mesick', ',', 'W', '.', 'C', '.', 'Feldman', ',', 'E', '.', 'R', '.',
                          'Mullin', ',', 'L', '.', 'C', '.', 'Stonehill', ',', '2020', ',', 'Icarus', ',', '335', ',',
                          '113397', ',', 'arXiv', ':', '1904.09036', ',', 'doi', ':', '10.1016/j.icarus.2019.113397',
                          '.'])

    def test_050(self):
        """ test splitting the reference when there are no identifiers """
        reference_str = "K.E. Mesick, W.C. Feldman, E.R. Mullin, L.C. Stonehill, 2020, Icarus, 335."
        self.assertEqual(self.crf_text.tokenize(reference_str),
                         ['K', '.', 'E', '.', 'Mesick', ',', 'W', '.', 'C', '.', 'Feldman', ',', 'E', '.', 'R', '.',
                          'Mullin', ',', 'L', '.', 'C', '.', 'Stonehill', ',', '2020', ',', 'Icarus', ',', '335', '.'])

    def test_051(self):
        """ test identifying `volume(issue):page_start-page_end` pattern """
        reference_str = 'M. Wang, J. Y. Lu, K. Kabin, H. Z. Yuan, X. Ma, Z. Q. Liu, Y. F. Yang, J. S. Zhao, and G. Li. The influence of IMF clock angle on the cross section of the tail bow shock. "Journal of Geophysical Research (Space Physics)", 121(11):11,077-11,085, Nov 2016.'
        self.assertEqual(self.crf_text.parse(reference_str),
                         {'title': u'influence IMF clock angle cross section tail bow shock',
                          'journal': u'Journal Geophysical Research Space Physics',
                          'authors': u'M. Wang, J. Y. Lu, K. Kabin, H. Z. Yuan, X. Ma, Z. Q. Liu, Y. F. Yang, J. S. Zhao, and G. Li.',
                          'refstr': u'M. Wang, J. Y. Lu, K. Kabin, H. Z. Yuan, X. Ma, Z. Q. Liu, Y. F. Yang, J. S. Zhao, and G. Li. The influence of IMF clock angle on the cross section of the tail bow shock. "Journal of Geophysical Research (Space Physics)", 121(11):11,077-11,085, Nov 2016.',
                          'volume': u'121',
                          'year': u'2016',
                          'issue': u'11',
                          'page': u'11,077-11,085'})


if __name__ == "__main__":
    unittest.main()
