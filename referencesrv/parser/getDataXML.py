import traceback
import re
from json import loads, dumps
import xmltodict
from BeautifulSoup import BeautifulStoneSoup
from collections import OrderedDict
from HTMLParser import HTMLParser


from flask import current_app


def get_dict_element(key, dict):
    if hasattr(dict,'iteritems'):
        for k, v in dict.iteritems():
            if k == key:
                yield v
            if isinstance(v, dict):
                for result in get_dict_element(key, v):
                    yield result
            elif isinstance(v, list):
                for d in v:
                    for result in get_dict_element(key, d):
                        yield result

def find_key(node, key):
    if isinstance(node, list):
        for i in node:
            for x in find_key(i, key):
                yield x
    elif isinstance(node, dict):
        if key in node:
            yield node[key]
        for j in node.values():
            for x in find_key(j, key):
                yield x


REGEX_AUTHORS = [re.compile(r'^(?P<last>[A-Za-z\'\-]+)(?P<init>[A-Z\.\s]+[\.\s])?$'),
                 re.compile(r'^(?P<init>[A-Z\.\s]+[\.\s])?(?P<last>[A-Za-z\'\-]+)$')]
def add_authors(author, first_name_tag, last_name_tag, tagged_reference):
    """

    :param author:
    :param first_name_tag:
    :param last_name_tag:
    :param tagged_reference:
    :return:
    """
    if isinstance(author, dict):
        tagged_reference.append(('AUTHOR_FIRST_NAME', author[first_name_tag].encode('ascii', 'ignore').decode('ascii')))
        tagged_reference.append(('AUTHOR_LAST_NAME', author[last_name_tag].encode('ascii', 'ignore').decode('ascii')))
    elif isinstance(author, list):
        for a in author:
            first = a.get(first_name_tag, None)
            last = a.get(last_name_tag, None)
            if first:
                tagged_reference.append(('AUTHOR_FIRST_NAME', first.encode('ascii', 'ignore').decode('ascii')))
            if last:
                tagged_reference.append(('AUTHOR_LAST_NAME', last.encode('ascii', 'ignore').decode('ascii')))
    elif isinstance(author, basestring):
        for regex in REGEX_AUTHORS:
            match = regex.match(author)
            if match:
                init = match.group('init')
                last = match.group('last')
                if last:
                    tagged_reference.append(('AUTHOR_LAST_NAME', last.encode('ascii', 'ignore').decode('ascii')))
                if init:
                    init = init.replace(' ','').replace('.','')
                    if len(init) == 2:
                        tagged_reference.append(('AUTHOR_FIRST_NAME', init[0].encode('ascii', 'ignore').decode('ascii')))
                        tagged_reference.append(('AUTHOR_MIDDLE_NAME', init[1].encode('ascii', 'ignore').decode('ascii')))
                    elif len(init) == 1:
                        tagged_reference.append(('AUTHOR_FIRST_NAME', init.encode('ascii', 'ignore').decode('ascii')))
                # if last:
                #     tagged_reference.append(('ET_AL', 'et al'))
                break


def add_collaboration(author, collaboration_tag, tagged_reference):
    """

    :param author:
    :param collaboration_tag:
    :param tagged_reference:
    :return:
    """
    if isinstance(author, dict):
        tagged_reference.append(('AUTHOR_COLLABORATION', author[collaboration_tag]))
    elif isinstance(author, list):
        for a in author:
            tagged_reference.append(('AUTHOR_COLLABORATION', a[collaboration_tag]))

def add_multi_word_fields(tag, field, tagged_reference):
    """

    :param tag:
    :param field:
    :param tagged_reference:
    :return:
    """
    # attached -/+ to the previous word and break the words
    for f in field.replace('-', '- ').replace('+', '+ ').split():
        tagged_reference.append((tag, f))

def add_title(title, sub_title, tagged_reference):
    """

    :param title:
    :param sub_title:
    :param tagged_reference:
    :return:
    """
    if title:
        title_str = ''.join(title)
        if sub_title:
            title_str = title_str + ': ' + ''.join(sub_title)
        add_multi_word_fields('TITLE', title_str.encode('ascii', 'ignore').decode('ascii'), tagged_reference)

def add_article(journal, year, volume, issue, tagged_reference):
    """

    :param journal:
    :param year:
    :param volume:
    :param issue:
    :param tagged_reference:
    :return:
    """
    if journal:
        value = ''.join(journal)
        if len(value) > 0:
            add_multi_word_fields('JOURNAL', value, tagged_reference)
    if volume:
        value = ''.join(volume)
        if len(value) > 0:
            tagged_reference.append(('VOLUME', value))
    if issue:
        value = ''.join(issue)
        if len(value) > 0:
            tagged_reference.append(('ISSUE', value))
    if year:
        value = ''.join(year)
        if len(value) > 0:
            tagged_reference.append(('YEAR', value))

def add_book(publisher, year, volume, tagged_reference):
    """

    :param publisher:
    :param year:
    :param volume:
    :param tagged_reference:
    :return:
    """
    if publisher:
        value = ''.join(publisher)
        if len(value) > 0:
            add_multi_word_fields('PUBLISHER', value, tagged_reference)
    if volume:
        value = ''.join(volume)
        if len(value) > 0:
            tagged_reference.append(('VOLUME', value))
    if year:
        value = ''.join(year)
        if len(value) > 0:
            tagged_reference.append(('YEAR', value))

def add_pages(first_page, last_page, tagged_reference):
    """

    :param first_page:
    :param last_page:
    :param tagged_reference:
    :return:
    """
    if first_page:
        value1 = ''.join(first_page)
        if len(value1) > 0:
            if last_page:
                value2 = ''.join(last_page)
                if len(value2) > 0:
                    tagged_reference.append(('PAGE', value1+'-'+value2))
                    return
            tagged_reference.append(('PAGE', value1))

def get_elsevier_tagged_data(buffer):
    """
    read elsevier type xml
    :param buffer:
    :return:
    """
    the_data = []
    doc = xmltodict.parse(buffer, encoding='utf-8')
    try:
        # go all the way to the bibliography section
        bibliography = doc['doc:document']['ja:article']['ja:tail']['ce:bibliography']['ce:bibliography-sec']
        # go through references
        for bib_reference in bibliography['ce:bib-reference']:
            tagged_reference = []
            if 'sb:reference' in bib_reference:
                if isinstance(bib_reference['sb:reference'], dict):
                    reference = bib_reference['sb:reference']
                elif isinstance(bib_reference['sb:reference'], list):
                    # consider only the first set of authors, the rest could be authors of comments, etc.
                    reference = bib_reference['sb:reference'][0]
                else:
                    reference = None

                if reference is not None:
                    # add in authors
                    if reference['sb:contribution'].get('sb:authors').get('sb:author'):
                        add_authors(reference['sb:contribution']['sb:authors']['sb:author'],
                                    'ce:given-name', 'ce:surname', tagged_reference)
                    elif reference['sb:contribution'].get('sb:authors').get('sb:collaboration'):
                        add_collaboration(reference['sb:contribution']['sb:authors'],
                                          'sb:collaboration', tagged_reference)
                    # add in title
                    if reference['sb:contribution'].get('sb:title'):
                        add_title(find_key(reference['sb:contribution']['sb:title'], 'sb:maintitle'),
                                  find_key(reference['sb:contribution']['sb:title'], 'sb:subtitle'),
                                  tagged_reference)
                    # decide if this reference is an article or book and add the fields
                    if reference['sb:host'].get('sb:issue', ''):
                        add_article(find_key(reference['sb:host']['sb:issue'], 'sb:maintitle'),
                                    find_key(reference['sb:host']['sb:issue'], 'sb:date'),
                                    find_key(reference['sb:host']['sb:issue'], 'sb:volume-nr'),
                                    find_key(reference['sb:host']['sb:issue'], 'sb:issue-nr'),
                                    tagged_reference)
                    elif reference['sb:host'].get('sb:book', ''):
                        add_book(find_key(reference['sb:host']['sb:book'], 'sb:name'),
                                 find_key(reference['sb:host']['sb:book'], 'sb:date'),
                                 find_key(reference['sb:host']['sb:book'], 'sb:volume-nr'),
                                 tagged_reference)
                    # add in page numbers
                    if reference['sb:host'].get('sb:pages', ''):
                        add_pages(find_key(reference['sb:host']['sb:pages'], 'sb:first-page'),
                                  find_key(reference['sb:host']['sb:pages'], 'sb:last-page'),
                                  tagged_reference)
                the_data.append(tagged_reference)
    except Exception as e:
        current_app.logger.error('Exception: %s' % (str(e)))
        current_app.logger.error('Unable to parse reference buffer %s' % (buffer[:250]))
        current_app.logger.error(traceback.format_exc())

    return the_data

def crossref_extract_volume_from_journal(journal):
    """
    if journal is compound string, attempt to extract volume out
    
    :param journal:
    :return:
    """
    volume = None
    parts = journal.split(',')
    if len(parts) == 2:
        match = re.search(r"(\d+)", parts[0])
        if match:
            volume = match.group()
            journal = parts[1]
        else:
            match = re.search(r"(\d+)", parts[1])
            if match:
                volume = match.group()
                journal = parts[0]
    return journal,volume

REGEX_REMOVE_HTML_TAG = re.compile("(&lt;i&gt;|&lt;/i&gt;|&lt;I&gt;|&lt;/I&gt;|&lt;b&gt;|&lt;/b&gt;|&lt;B&gt;|&lt;/B&gt;)", re.I)
def get_crossref_tagged_data(buffer, include_refstr):
    """
    read cross ref type xml
    :param buffer:
    :param include_refstr: during training do not need refstr
    :return:
    """
    the_data = []
    try:
        # some references have html tags, entities that xmltodict does not like
        clean_buffer = re.sub(r'&lt;(.+?)>', r'&lt;\1&gt;', buffer)
        clean_buffer = REGEX_REMOVE_HTML_TAG.sub("", clean_buffer).replace('--', '-')
        clean_buffer = unicode(BeautifulStoneSoup(clean_buffer, convertEntities=BeautifulStoneSoup.ALL_ENTITIES))
        # just in case beautifulsoup did not remove html entity
        clean_buffer = re.sub(r'&(.+?);', '', clean_buffer)

        # something goes wrong with parse if there is only one reference, so insert an empty citiation tag to have
        # at least two elements
        doc = xmltodict.parse(clean_buffer.replace("</citation_list>", "<citation></citation></citation_list>"))

        citation_list = doc['citation_list']
        for citation in citation_list['citation']:
            if citation is None:
                continue
            tagged_reference = []
            if 'author' in citation:
                add_authors(citation['author'], None, None, tagged_reference)
            if 'article_title' in citation:
                add_title(citation['article_title'], '', tagged_reference)
            journal = citation['journal_title'] if 'journal_title' in citation else \
                      citation['series_title'] if 'series_title' in citation else \
                      citation['volume_title'] if 'volume_title' in citation else None
            year = citation['cyear'] if 'cyear' in citation else None
            volume = citation['volume'] if 'volume' in citation else None
            issue = citation['issue'] if 'issue' in citation else None
            if journal and not volume:
                journal, volume = crossref_extract_volume_from_journal(journal)
            add_article(journal, year, volume, issue, tagged_reference)
            if 'first_page' in citation:
                add_pages(citation['first_page'], None, tagged_reference)
            if 'doi' in citation:
                if '#text' in citation['doi']:
                    doi = citation['doi']['#text']
                else:
                    doi = citation['doi']
                tagged_reference.append(('DOI', '%s'%doi))
            if 'issn' in citation:
                tagged_reference.append(('ISSN', citation['issn']))
            if include_refstr:
                if 'unstructured_citation' in citation:
                    tagged_reference.append(('REFPLAINTEXT', citation['unstructured_citation']))
                tagged_reference.append(('REFSTR', str(loads(dumps(citation)))))
            else:
                # we dont need these to be classified
                tagged_reference.append(('REFPLAINTEXT', '?!?!'))
                tagged_reference.append(('REFSTR', '?!?!'))
            the_data.append(tagged_reference)
    except Exception as e:
        current_app.logger.error('Exception: %s' % (str(e)))
        current_app.logger.error('Unable to parse reference buffer %s' % (buffer[:250]))
        current_app.logger.error(traceback.format_exc())

    return the_data

def get_springer_field_value(node, node_name, field_name=None):
    """

    :param node_name:
    :param field_name:
    :return:
    """
    try:
        if field_name:
            return next(field[field_name] for field in find_key(node, node_name))
        return next(find_key(node, node_name))
    except:
        return ''

def get_springer_doi(node):
    """

    :param node:
    :return:
    """
    for elem in find_key(node, 'occurrence'):
        if isinstance(elem, list):
            for sub_elem in elem:
                if isinstance(sub_elem, dict):
                    values = sub_elem.values()
                    if len(values) == 2 and values[0] == 'DOI':
                        return values[1]
    return ''

REGEX_ARXIV_ID = re.compile(r"arXiv[\s:](\d+)(\.)(\d+)|([a-z]+\-[a-z]+)(/)(\d+)|arxiv.org/abs/([a-z\-]+)(/)(\d+)|arxiv.org/abs/(\d+)(\.)(\d+)", re.IGNORECASE)
def get_springer_arxiv_id(node):
    """
    return arxiv id from the node which can have the following formats:
    arXiv:1406.1759
    hep-ph/0502047
    arxiv.org/abs/1406.1759
    arxiv.org/abs/hep-ph/0602144

    :param node:
    :return:
    """
    node_str = str(loads(dumps(node)).values())
    match = REGEX_ARXIV_ID.findall(node_str)
    if len(match) > 0:
        match = match[0]
        return ''.join(match)
    return ''

def get_springer_ref_plain_text(node):
    """

    :param node:
    :return:
    """
    plain_text = get_springer_field_value(node, 'bibunstructured')
    if isinstance(plain_text, unicode):
        return plain_text
    if isinstance(plain_text, OrderedDict):
        plain_text = get_springer_field_value(plain_text, '#text')
        return plain_text
    return ''


def get_springer_tagged_data(buffer, include_refstr):
    """

    :param buffer:
    :param include_refstr: during training do not need refstr
    :return:
    """
    html_parser = HTMLParser()
    the_data = []
    try:
        clean_buffer = unicode(BeautifulStoneSoup(html_parser.unescape(buffer), convertEntities=BeautifulStoneSoup.ALL_ENTITIES))
        doc = xmltodict.parse(clean_buffer, encoding='utf-8')
        citation_list = doc['citationlist']
        for i, citation in enumerate(citation_list['citation']):
            if citation is None:
                continue
            tagged_reference = []
            for authors in find_key(citation, 'bibauthorname'):
                add_authors(authors, 'initials', 'familyname', tagged_reference)
            add_title(get_springer_field_value(citation, 'articletitle', '#text'), None, tagged_reference)
            journal = get_springer_field_value(citation, 'journaltitle')
            year = get_springer_field_value(citation, 'year')
            volume = get_springer_field_value(citation, 'volumeid')
            issue = get_springer_field_value(citation, 'issueid')
            add_article(journal, year, volume, issue, tagged_reference)
            add_pages(get_springer_field_value(citation, 'firstpage'), None, tagged_reference)
            doi = get_springer_doi(citation)
            if len(doi) > 0:
                tagged_reference.append(('DOI', '%s'%doi))
            book = get_springer_field_value(citation, 'booktitle')
            if len(book) > 0:
                add_book(book, None, get_springer_field_value(citation, 'editionnumber'), tagged_reference)
            arxiv = get_springer_arxiv_id(citation)
            if len(arxiv) > 0:
                tagged_reference.append(('ARXIV', '%s'%arxiv))
            if include_refstr:
                unstructured = get_springer_ref_plain_text(citation)
                if len(unstructured) > 0:
                    tagged_reference.append(('REFPLAINTEXT', unstructured.replace('[]', '')))
                tagged_reference.append(('REFSTR', str(loads(dumps(citation)))))
            else:
                tagged_reference.append(('REFPLAINTEXT', '?!?!'))
                tagged_reference.append(('REFSTR', '?!?!'))
            the_data.append(tagged_reference)
    except Exception as e:
        current_app.logger.error('Exception: %s' % (str(e)))
        current_app.logger.error('Unable to parse reference buffer %s' % (buffer[:250]))
        current_app.logger.error(traceback.format_exc())

    return the_data

REGEX_XML_TAG_FORMAT = re.compile(r'<ce:italic>|</ce:italic>')
def get_xml_tagged_data(buffer, include_refstr=True):
    """
    figure out what format file it is and call the
    respective function to return data for training

    :param buffer:
    :param include_refstr: during training do not need refstr
    :return:
    """
    if len(buffer) > 1 and 'http://www.elsevier.com/xml/document' in buffer[1]:
        return get_elsevier_tagged_data(REGEX_XML_TAG_FORMAT.sub('', ' '.join(buffer)))
    if len(buffer) > 1 and 'ADSBIBCODE' in buffer[0] and 'citation_list' in buffer[1]:
        buffer = '<?xml version="1.0"?>' + ' '.join(buffer[1:])
        return get_crossref_tagged_data(buffer, include_refstr)
    if len(buffer) > 1 and 'ADSBIBCODE' in buffer[0] and 'Citation ID' in buffer[1]:
        selected_buffer = ['<?xml version="1.0"?>', '<CitationList>']
        for line in buffer:
            line = line.strip()
            if line.startswith('<Citation ID='):
                selected_buffer.append(line)
        selected_buffer.append('</CitationList>')
        return get_springer_tagged_data('\n'.join(selected_buffer), include_refstr)
    return None

def get_xml_tagged_data_training(filename):
    """

    :param filename:
    :return:
    """
    with open(filename) as f:
        reader = f.read().splitlines()
        return get_xml_tagged_data(reader, False)
