
def get_test_data():
    """
    query is author:("Accomazzi, A") AND year:"2019" AND bibstem:(AAS)

    :return:
    """
    return {u'responseHeader':
                {u'status': 0,
                 u'QTime': 3,
                 u'params': {u'rows': u'100',
                             u'q': u'author:("Accomazzi, A") AND year:"2019" AND bibstem:(AAS)',
                             u'start': u'0',
                             u'wt': u'json',
                             u'fl': u'author_norm,first_author_norm,year,title,thesis,pub,volume,page,bibcode,identifier,author,pub_raw,doctype'
                             }
                 },
            u'response':
                {u'start': 0,
                 u'numFound': 2,
                 u'docs': [
                     {u'bibcode': u'2019AAS...23320704A',
                      u'author': [u'Accomazzi, Alberto'],
                      u'title': [u'The NASA Astrophysics Data System\xe2\u20ac\u2122s Decadal Plan for the 2020s'],
                      u'doctype': u'abstract',
                      u'pub': u'American Astronomical Society Meeting Abstracts #233',
                      u'pub_raw': u'American Astronomical Society, AAS Meeting #233, id.207.04',
                      u'volume': u'233',
                      u'author_norm': [u'Accomazzi, A'],
                      u'year': u'2019',
                      u'first_author_norm': u'Accomazzi, A',
                      u'identifier': [u'2019AAS...23320704A'],
                      u'page': [u'207.04']},
                     {u'bibcode': u'2019AAS...23338108A',
                      u'author': [u'Accomazzi, Alberto', u'Kurtz, Michael J.', u'Henneken, Edwin', u'Grant, Carolyn S.', u'Thompson, Donna M.', u'Chyla, Roman', u'McDonald, Stephen', u'Blanco-Cuaresma, Sergi', u'Shapurian, Golnaz', u'Hostetler, Timothy', u'Templeton, Matthew', u'Lockhart, Kelly'],
                      u'title': [u'Transitioning from ADS Classic to the new ADS search platform'],
                      u'doctype': u'abstract',
                      u'pub': u'American Astronomical Society Meeting Abstracts #233',
                      u'pub_raw': u'American Astronomical Society, AAS Meeting #233, id.381.08',
                      u'volume': u'233',
                      u'author_norm': [u'Accomazzi, A', u'Kurtz, M', u'Henneken, E', u'Grant, C', u'Thompson, D', u'Chyla, R', u'McDonald, S', u'Blanco-Cuaresma, S', u'Shapurian, G', u'Hostetler, T', u'Templeton, M', u'Lockhart, K'],
                      u'year': u'2019',
                      u'first_author_norm': u'Accomazzi, A',
                      u'identifier': [u'2019AAS...23338108A'],
                      u'page': [u'381.08']}
                 ]
                 }
            }