import re
import unidecode


def get_arxiv_tagged_data(filename):
    """

    :param filename:
    :return:
    """
    the_data = []
    tagged_reference = []
    with open(filename) as f:
        reader = f.readlines()
        for line in reader:
            if line.startswith('%'):
                if len(tagged_reference) > 0:
                    the_data.append(tagged_reference)
                    tagged_reference = []
            else:
                fields = line.strip('\r\n').split('\t')
                if len(fields) == 2:
                    tagged_reference.append((fields[0], fields[1]))
    if len(tagged_reference) > 0:
        the_data.append(tagged_reference)
    return the_data
