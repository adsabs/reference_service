"""
The module contains methods that are called from other modules

"""

import re
from collections import OrderedDict

MATCH_A_WORD = re.compile(r'(\w+\-\w+\-\w+|\w+\-\w+|\w+\&\w+|\w+)')
MATCH_WHOLE_WORD = r'\b(%s)\b'

PUNCTUATION_TOKEN = OrderedDict(
    [('PUNCTUATION_BRACKETS', ['[', ']']), ('PUNCTUATION_COLON', [':']), ('PUNCTUATION_COMMA', [',']),
     ('PUNCTUATION_DOT', ['.']), ('PUNCTUATION_PARENTHESIS', ['(', ')']), ('PUNCTUATION_QUOTES', ['"', '\'']),
     ('PUNCTUATION_NUM', ['#']), ('PUNCTUATION_HYPEN', ['-']), ('PUNCTUATION_FORWARD_SLASH', ['/']),
     ('PUNCTUATION_SEMICOLON', [';'])])


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
    if any(token == t for t in MATCH_A_WORD.findall(str)):
        return True
    hypenated = token.split('-')
    count = 0
    for word in hypenated:
        count += int(any(word == w for w in MATCH_A_WORD.findall(str)))
    return count == len(hypenated)


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


def is_punctuation(ref_word):
    """

    :param ref_word:
    :return: 0 if not a punctuation
             1 if brackets, 2 if colon, 3 if comma, 4 if dot, 5 if parenthesis,
             6 if quotes (both single and double), 7 if num sign, 8 if hypen, 9 if forward slash,
             10 if semicolon
    """
    found = [i for i, p in enumerate(PUNCTUATION_TOKEN.values()) if ref_word in p]
    return found[0]+1 if len(found) > 0 else 0


def which_punctuation(ref_word, ref_label):
    """
    verify if ref_word is a punctuation, and determine which one

    :param ref_word:
    :param ref_label:
    :return:
    """
    if ref_label:
        return list(PUNCTUATION_TOKEN.keys()).index(ref_label)+1 if ref_label in PUNCTUATION_TOKEN.keys() else 0

    return is_punctuation(ref_word)

