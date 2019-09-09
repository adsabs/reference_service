# -*- coding: utf-8 -*-

from flask import current_app, request, Blueprint, Response
from flask_discoverer import advertise

import json
import urllib
import re

from referencesrv.parser.crf import CRFClassifierText, CRFClassifierXML
from referencesrv.resolver.solve import solve_reference
from referencesrv.resolver.hypotheses import Hypotheses


bp = Blueprint('reference_service', __name__)


def text_parser(reference):
    """

    :return:
    """
    if not hasattr(text_parser, "crf"):
        text_parser.status = False
        text_parser.crf = CRFClassifierText()
    if not text_parser.status:
        text_parser.status = text_parser.crf.get_ready()
    if text_parser.status:
        return text_parser.crf.parse(reference)
    raise Exception


def xml_parser(reference_buffer):
    """

    :return:
    """
    if not hasattr(xml_parser, "crf"):
        xml_parser.status = False
        xml_parser.crf = CRFClassifierXML()
    if not xml_parser.status:
        xml_parser.status = xml_parser.crf.get_ready()
    if xml_parser.status:
        return xml_parser.crf.parse(reference_buffer)
    raise Exception

def return_response(results, status, content_type='application/json'):
    """

    :param results: results in a dict
    :param status: status code
    :return:
    """

    if 'application/json' in content_type:
        response = json.dumps(results)
    else:
        response = results

    if status != 200:
        current_app.logger.error('sending response status={status}'.format(status=status))
        current_app.logger.error('sending response text={response}'.format(response=results))
        r = Response(response=response, status=status)
        r.headers['content-type'] = content_type
        return r

    current_app.logger.info('sending response status={status}'.format(status=status))
    r = Response(response=response, status=status)
    r.headers['content-type'] = content_type
    return r


@advertise(scopes=[], rate_limit=[1000, 3600 * 24])
@bp.route('/text', methods=['POST'])
def text_post():
    """

    :return:
    """
    try:
        payload = request.get_json(force=True)  # post data in json
    except:
        payload = dict(request.form)  # post data in form encoding

    if not payload:
        return {'error': 'no information received'}, 400
    if 'reference' not in payload:
        return {'error': 'no reference found in payload (parameter name is `reference`)'}, 400

    references = payload['reference']

    current_app.logger.info('received POST request with references={references} to resolve in text mode'.
        format(references=','.join(references)))

    results = []
    for reference in references:
        try:
            if bool(re.search(r'\d', reference)):
                parsed_ref = text_parser(reference)
                bibcode = str(solve_reference(Hypotheses(parsed_ref)))
                result = '%s -- %s'%(bibcode, reference)
            else:
                raise ValueError('Reference with no year and volume cannot be resolved.')
        except Exception as e:
            current_app.logger.error('Exception: %s' %(str(e)))
            result = '0.0 %s -- %s'%(19*'.', reference)
            continue
        finally:
            results.append(result)

    if len(results) == len(results):
        return return_response({'resolved':'\n'.join(results)}, 200, 'application/json; charset=UTF8')
    return return_response({'error': 'none of the references got resolved'}, 400, 'text/plain; charset=UTF8')


@advertise(scopes=[], rate_limit=[1000, 3600 * 24])
@bp.route('/text/<reference>', methods=['GET'])
def text_get(reference):
    """

    :param reference:
    :return:
    """
    reference = urllib.unquote(reference)
    current_app.logger.info('received GET request with reference=`{reference}` to resolve in text mode'.format(reference=reference))
    try:
        if bool(re.search(r'\d', reference)):
            parsed_ref = text_parser(reference)
            bibcode = str(solve_reference(Hypotheses(parsed_ref)))
            result = '%s -- %s'%(bibcode, reference)
            return return_response(result, 200, 'text/plain; charset=UTF8')
        raise ValueError('Reference with no year and volume cannot be resolved.')
    except Exception as e:
        current_app.logger.error('Exception: %s', str(e))
        result = '%s -- %s'%(19*'.', reference)
        return return_response(result, 400, 'text/plain; charset=UTF8')


@advertise(scopes=[], rate_limit=[1000, 3600 * 24])
@bp.route('/xml', methods=['POST'])
def xml_post():
    """

    :return:
    """
    try:
        payload = request.get_json(force=True)  # post data in json
    except:
        payload = dict(request.form)  # post data in form encoding

    if not payload:
        return {'error': 'no information received'}, 400
    if 'reference' not in payload:
        return {'error': 'no reference found in payload (parameter name is `reference`)'}, 400

    references = payload['reference']

    current_app.logger.debug('received POST request with references={references} to resolve in xml mode'.
        format(references=' '.join(references)[:250]))

    results = []
    parsed_references = xml_parser(references)
    for parsed_reference in parsed_references:
        try:
            bibcode = str(solve_reference(Hypotheses(parsed_reference)))
            if bibcode.startswith('0.0'):
                raise
            result = '%s -- %s'%(bibcode, parsed_reference['refstr'])
        except Exception as e:
            current_app.logger.error('Exception: %s' %(str(e)))
            # lets attempt to resolve using the text model
            if 'refplaintext' in parsed_reference:
                reference = urllib.unquote(parsed_reference['refplaintext'])
                current_app.logger.info('attempting to resolve the reference=`{reference}` in text mode now'.format(reference=reference))
                try:
                    parsed_ref = text_parser(reference)
                    bibcode = str(solve_reference(Hypotheses(parsed_ref)))
                    result = '%s -- %s' % (bibcode, reference)
                except Exception as e:
                    current_app.logger.error('Exception: %s', str(e))
                    result = '0.0 %s -- %s' % (19 * '.', reference)
                    continue
            else:
                result = '0.0 %s -- %s'%(19*'.', parsed_reference['refstr'])
            continue
        finally:
            results.append(result)

    if len(results) == len(results):
        return return_response({'resolved':'\n'.join(results)}, 200, 'application/json; charset=UTF8')
    return return_response({'error': 'none of the references got resolved'}, 400, 'text/plain; charset=UTF8')
