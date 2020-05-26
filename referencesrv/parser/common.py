"""
The module contains methods that are called from other modules

"""

import re

MATCH_A_WORD = re.compile(r'(\w+\-\w+|\w+)')
MATCH_WHOLE_WORD = r'\b(%s)\b'


def concatenate(token_1, token_2):
    """

    :param token_1:
    :param token_2:
    :return:
    """
    if not token_2 or len(token_2) == 0:
        return token_1
    return '%s%s%s' % (token_1, ' ' if len(token_1) > 0 else '', token_2)

def spot(token, str):
    """

    :param token:
    :param str:
    :return:
    """
    return any(token == t for t in MATCH_A_WORD.findall(str))


def strip(token, str):
    """
    strip the token from both the beginning and the end of str

    :param token:
    :param str:
    """
    if str.lower().strip() == token:
        return ''
    if str.lower().startswith(token+' '):
        str = str[len(token):]
    if str.lower().endswith(' ' + token):
        str = str[:-len(token)]
    return str.strip()


def replace(replace_token, str, with_token):
    """
    replace whole word using re

    :param replace_token:
    :param str:
    :param with_token:
    :return:
    """
    return re.sub(MATCH_WHOLE_WORD % replace_token, with_token, str)


def append_unique(the_list, new_item):
    """
    append the newe_item to the_list, only if it does not exist

    :param the_list:
    :param new_item:
    :return:
    """
    exist = any(new_item == item for item in the_list)
    if not exist:
        the_list.append(new_item)
    return the_list