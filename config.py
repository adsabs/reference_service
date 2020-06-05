# encoding=utf8
# included included for the presense of unicode, for example `Akademiai Kiadò, in list of academic publishers

LOGGING_LEVEL = 'INFO'

# must be here for adsmutils to override it using env vars
# but if left empty (resolving to False) it won't be used
SERVICE_TOKEN = None

# configuration for accessing solr db
# these values can be overwritten by local_config values
REFERENCE_SERVICE_SOLRQUERY_URL = "https://api.adsabs.harvard.edu/v1/search/query"
REFERENCE_SERVICE_MAX_RECORDS_SOLR = 100

REFERENCE_SERVICE_QUERY_FIELDS_SOLR = "author,author_norm,first_author_norm,year,title,pub,pub_raw," \
                                      "volume,issue,page,page_range,bibstem,bibcode,identifier,doi,doctype"

EVIDENCE_SCORE_RANGE = [-1,1]

REFERENCE_STOP_WORDS = [
    'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves', 'you',
    'your', 'yours', 'yourself', 'yourselves', 'he', 'him', 'his',
    'himself', 'she', 'her', 'hers', 'herself', 'it', 'its', 'itself',
    'they', 'them', 'their', 'theirs', 'themselves', 'what', 'which',
    'who', 'whom', 'this', 'that', 'these', 'those', 'am', 'is', 'are',
    'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'having',
    'do', 'does', 'did', 'doing', 'a', 'an', 'the', 'and', 'but', 'if',
    'or', 'because', 'as', 'until', 'while', 'of', 'at', 'by', 'for',
    'with', 'about', 'against', 'between', 'into', 'through', 'during',
    'before', 'after', 'above', 'below', 'to', 'from', 'up', 'down', 'in',
    'out', 'on', 'off', 'over', 'under', 'again', 'further', 'then',
    'once', 'here', 'there', 'when', 'where', 'why', 'how', 'all', 'any',
    'both', 'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no',
    'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very', 's',
    't', 'can', 'will', 'just', 'don', 'should', 'now', 'id', 'var', 'in',
    'function', 'js', 'd', 'script', '\'script', 'fjs', 'document', 'r',
    'b', 'g', 'e', '\'s', 'c', 'f', 'h', 'l', 'k'
]

# common abbreviations in references; ADS has these expanded,
# so we want to expand them, too.
JOURNAL_ABBREVIATION = {
    'J.': 'Journal',
    'Comput.': 'Computing',
    'Rev.': 'Review',
    'Phys.': 'Physical',
    'Annu.': 'Annual',
    'Nucl.': 'Nuclear',
    'Part.': 'Science',
    'Planet.': 'Planetary',
    'Conf.': 'Conference',
    'Sci.': 'Science',
}

# a list of (lower-cased) indicators in source fields for thesis-like stuff
# (* is the only solr metacharacter allowed)
THESIS_INDICATOR_WORDS = [u'thesis', u'ms', u'ph', u'phd', u'dissert*']

# A factor by which matching authors are discounted if the first author is missing
MISSING_FIRST_AUTHOR_FACTOR = 0.3

# A negative confidence when one page has a "qualifier" (the L for
# letter, or a P for the pink pages) and the other doesn't.
NO_LETTER_DEMERIT = -0.3

# minimal score a solution needs to be accepted on the first round
# of resolving.
MIN_SCORE_FIRST_ROUND = 0.7

# A list of keys that should be joined with blanks if multiple strings
# in a list come back from solr.  Note that you probably need to
# change scoring functions if ever multiple volumes, pages, years,
# or bibcodes were to come back.
SOLR_KEYS_TO_JOIN = ["year', u'title', u'thesis', u'pub', u'volume', u'page', u'bibcode"]

# this is false if testing mode
REFERENCE_SERVICE_LIVE = True

# source http://www.apsstylemanual.org/oldmanual/resources/publishers.htm
REFERENCE_SERVICE_ACADEMIC_PUBLISHERS = [
    "AAAS","Abakon","Ablex","Academic","Acta","Addison-Wesley","Adriatica","Akademiai Kiadò","Akademische","Aldine",
    "Allen & Unwin","Almqvist & Wiksell","American Chemical Society","American Mathematical Society",
    "AMA (American Medical Association)","American Society of Agricultural Engineers","Annual Reviews",
    "Ann Arbor Science","Appleton","Appleton-Century Crofts","Arco","Arnold","Arrowsmith","Arscia","Athlone",
    "Aulendorf","Avi","Axon","Balkema","Balliere","Balliere, Tindal, & Cox","Barnes & Noble","Basic","Bermann",
    "Benjamin","Benjamin/Cunnings","Birkhäuser","BI-Science Webster","Blackwell","Blakiston","Boehringer Ingelheim",
    "Bowker","Braumuller","Brockhaus","Brooks-Cole","Brown University Press","Bunge","Burman & Schwarzenburg",
    "Butterworths","Cambridge University Press","Cattell","Chapman & Hall","Christian-Albrechts-Universität",
    "Carey & Hart","Christophers","Churchill Livingstone","Claitor's","Clarendon","Classics Medical Library","CNRS",
    "Cold Spring Harbor","Columbia University Press","Congressprint","Cornell University Press",
    "CRC (Chemical Rubber Company Press)","Croom Helm","CSIC","Czech Academy Science","Dahlen",
    "Dalhousie University Press","Davis","Dawson","de Gruyter","Dekker","Dorsey","Doubleday","Dover",
    "Dowden, Hutchinson & Ross","Draeger","Dutton","Duxbury","Eden","El Ateneo","Elsevier","Elsevier/North-Holland",
    "Engleman","Erlbaum","Excerpta Medica","FADL","Fischer","Fitzer","Freeman","Futura","(Aulo) Gaggi","Garland",
    "Geigy","Gordon & Breach","Granada","Green","Grosse","Grune & Stratton","Guilford",
    "Haer Institute for Electrophysiological Research","Hafner","Halsted","Harper & Row","Harvard University Press",
    "Heineman","Heinemann","Hippokrates","Hodder & Stoughton","(Paul B.) Hoeber","Hodges & Smith","Holden-Day",
    "Holt, Rinehart, & Winston","Horwood","(Hans) Huber","Humana","Human Kinetics","Hutchinson","Igaku Shoin",
    "Illinois Institute for Technogical Research","Indiana University Press","INSERM","Instrument Society of America",
    "Interscience","Interstate","Iowa State University Press","ISI (Institute for Scientific Information)",
    "Johns Hopkins University Press","Josiah Macy, Jr. Foundation","Junk","Karger","Karolinska Institutet","Kemper",
    "Kodansha","Ladd Research Industries","Lea & Febiger","Le Seuil","Lewis","Lippincott","Liss","Little, Brown",
    "Liviana","Livingstone","Lloyd-Luke","Logos","Longman","Longman Canada","Longmans Green","Macmillan","Maloin",
    "Mandrich","Masson","Merriam","Methuen","McGill University Press","McGraw-Hill","MTP (Medical Technical Press)",
    "Minerva Medica","MIT Press","Mosby","Munksgaard","Murby","NASA","National Committee on Poultry and Eggs",
    "National Institutes of Health", "National Research Council", "Naval Underwater Systems Center","Navchetan",
    "Newman","Nijhoff","North-Holland","Northwestern University Press", "Norton","NY Academy Science","Oldenbourg",
    "Oliver & Boyd","Oriel","Oxford University Press","Palais-Royal", "Pergamon","Piccin","Pickering","Pierce Chemical",
    "Pitman","Plenum","Port City","Praeger","Prentice-Hall", "Princeton University Press","Quin & Boden","Quintessence",
    "Raven","Rayburn","Reinhold","Reynolds","RK-Trych", "Roche","Rockefeller University Press","Routledge",
    "Rutgers University Press","Samson & Wallin","Saunders", "Schenkman","Schattauer","Schuman","Schwabe","Scott",
    "Scott, Foresman","Scottish Academic","Scribner","Sector", "SEM","Shaw","Sijthoff","Sijthoff & Noordhoff",
    "Simulation Councils","Sinauer","Slack","(Joseph) Smith","Spartan", "Spectrum","Springer-Verlag",
    "Stanford University Press","Stratton", "Swets & Zeitlinger","Symposia Specialists","Taniguchi Foundation",
    "Taylor & Francis","Thieme","Thomas","Ulmer",
    "Universitetsforlaget","Universities Federation for Animal Welfare (UFAW)","University Park",
    "University of California Press","University of Chicago Press","University of Delhi Press",
    "University of Illinois Press","University of Kentucky Press","University of Michigan Press",
    "University of Minnesota Press","University of Nebraska Press","University of Pennsylvania Press",
    "University of Rochester Press","University of Texas Press","University of Tokyo Press",
    "University of Washington Press","University of Western Ontario Press","University of Wisconsin Press",
    "Unwin","Upjohn","Urban & Schwarzenberg","US Government Printing Office","Vaillant-Carmanne",
    "Vallabhbhai Patel Chest Institute","Vandenhoeck","Vanderbilt University Press","Van Gorcum","Van Nostrand",
    "Van Nostrand Reinhold","Vincent","Vital Raoul Lataste","Washington State University Press","Whitefriars",
    "Wiley-Interscience","Wiley-Liss","Williams & Wilkins","Winston","Wirsiers","Wissenschaftliche","Wistar",
    "Wolters-Noordhoff","Worth","Wright","Yale University Press","Year Book","Yorke"
]

# source: http://www.apsstylemanual.org/oldmanual/resources/publishers.htm
REFERENCE_SERVICE_ACADEMIC_PUBLISHERS_LOCATIONS = [
    'Aberdeen', 'AL', 'Ames', 'Amsterdam', 'Ann Arbor', 'Assen', 'Austin', 'Australia', 'Baltimore', 'Bari', 'Basel',
    'Baton Rouge', 'Beijing', 'Belgium', 'Belmont', 'Berkeley', 'Berlin', 'Bern', 'Bethesda', 'Birmingham',
    'Bloomington', 'Boca Raton', 'Bologna', 'Boston', 'Bristol', 'Brunswick', 'Brussels', 'Budapest', 'Buenos Aires',
    'Burlington', 'CA', 'Cadillac', 'Cambridge', 'Canada', 'Cape Town', 'Champaign', 'Chicago', 'Chichester',
    'Cleveland', 'Clifton', 'Cold Spring Harbor', 'Copenhagen', 'CT', 'Danville', 'DC', 'Delhi', 'Don Mills', 'Dublin',
    'Edinburgh', 'Elmsford', 'Englewood Cliffs', 'Evanston', 'FL', 'France', 'Frankfurt', 'Geneva', 'Germany',
    'Glenview', 'Gottingen', 'Greenbelt', 'Groningen', 'Grosse Point Park', 'Groves', 'Halifax', 'Heidelberg',
    'Hillsdale', 'Hingham', 'Homewood', 'IA', 'Ibaraki', 'IL', 'IN', 'Italy', 'Japan', 'Jena', 'Kalamazoo', 'Kiel',
    'KY', 'LA', 'La Jolla', 'Lancaster', 'Leiden', 'Leipzig', 'Leningrad', 'Lexington', 'Liege', 'Lincoln', 'Lisse',
    'London', 'London', 'Los Angeles', 'Lyons', 'MA', 'Madison', 'Madrid', 'MD', 'Menlo Park', 'MI', 'Miami',
    'Minneapolis', 'MN', 'MO', 'Montreal', 'Moscow', 'Mount Kisco', 'Munich', 'N. Scituate', 'Nashville', 'NE',
    'New Delhi', 'New Haven', 'New London', 'New York', 'NJ', 'Norwood', 'NY', 'O\'Hare', 'OH', 'Orlando', 'Oslo',
    'Oss', 'Oxford', 'PA', 'Padua', 'Palo Alto', 'Paris', 'Philadelphia', 'Pittsburgh', 'Prague', 'Princeton',
    'Providence', 'Pullman', 'Quebec', 'Rabway', 'Reading', 'RI', 'Rochester', 'Rockford', 'Rome',
    'Royal Tunbridge Wells', 'Rutgers', 'San Francisco', 'Seattle', 'South Africa', 'Springfield', 'St.Albans',
    'St.Joseph', 'St.Louis', 'Stanford', 'Stockholm', 'Stroudsburg', 'Stuttgart', 'Sunderland', 'Sweden',
    'Sydney', 'The Hague', 'The Netherlands', 'Thorofare', 'TN', 'Tokyo', 'Torino', 'Toronto', 'TX', 'UK',
    'Uppsala', 'Urbana', 'Utrecht', 'Vienna', 'VT', 'WA', 'Warsaw', 'Washington', 'Westport', 'WI', 'Wiesbaden']

REFERENCE_SERVICE_STOP_WORDS = [
     'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves', 'you',
     'your', 'yours', 'yourself', 'yourselves', 'he', 'him', 'his',
     'himself', 'she', 'her', 'hers', 'herself', 'it', 'its', 'itself',
     'they', 'them', 'their', 'theirs', 'themselves', 'what', 'which',
     'who', 'whom', 'this', 'that', 'these', 'those', 'am', 'is', 'are',
     'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'having',
     'do', 'does', 'did', 'doing', 'a', 'an', 'the', 'and', 'but', 'if',
     'or', 'because', 'as', 'until', 'while', 'of', 'at', 'by', 'for',
     'with', 'about', 'against', 'between', 'into', 'through', 'during',
     'before', 'after', 'above', 'below', 'to', 'from', 'up', 'down', 'in',
     'out', 'on', 'off', 'over', 'under', 'again', 'further', 'then',
     'once', 'here', 'there', 'when', 'where', 'why', 'how', 'all', 'any',
     'both', 'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no',
     'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very', 's',
     't', 'can', 'will', 'just', 'don', 'should', 'now', 'id', 'var', 'in',
     'function', 'js', 'd', 'script', '\'script', 'fjs', 'document', 'r',
     'b', 'g', 'e', '\'s', 'c', 'f', 'h', 'l', 'k']

# For caching
REDIS_URL = "redis://localhost:6379/0"
REDIS_NAME_PREFIX = "reference_service_"
# save to cache for a day
# REDIS_EXPIRATION_TIME = 86400
# eventually a day, for debug purposes, for now lets keep it for one hour
REDIS_EXPIRATION_TIME = 3600
