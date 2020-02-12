# -*- coding: utf-8 -*-

from flask import current_app, request, Blueprint, Response
from flask_discoverer import advertise
from flask_redis import FlaskRedis
from redis import RedisError

import json
import urllib
import re
import time

from referencesrv.parser.crf import CRFClassifierText, CRFClassifierXML, create_text_model, load_text_model
from referencesrv.resolver.solve import solve_reference
from referencesrv.resolver.hypotheses import Hypotheses
from referencesrv.resolver.sourcematchers import create_source_matcher, load_source_matcher
from referencesrv.resolver.common import NoSolution


bp = Blueprint('reference_service', __name__)
redis_db = FlaskRedis()

RE_NUMERIC_VALUE = re.compile(r'\d')

# @bp.before_app_first_request
def text_model():
    """

    :return:
    """
    # load only if in production mode
    if current_app.config['REFERENCE_SERVICE_LIVE']:
        current_app.extensions['text_crf'] = load_text_model()
        current_app.extensions['source_matcher'] = load_source_matcher()


def text_parser(reference):
    """

    :return:
    """

    return current_app.extensions['text_crf'].parse(reference)


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

    current_app.logger.debug('response length={length} with content_type={content_type}'.format(length=len(response), content_type=content_type))
    r = Response(response=response, status=status)
    r.headers['content-type'] = content_type
    current_app.logger.info('sending response status={status}'.format(status=status))
    return r


def cache_resolved_set(reference, resolved):
    """

    :param reference:
    :param resolved
    :return:
    """
    try:
        # save it to cache
        redis_db.set(name=current_app.config['REDIS_NAME_PREFIX'] + reference, value=resolved,
                     ex=current_app.config['REDIS_EXPIRATION_TIME'])
    except RedisError as e:
        current_app.logger.error('exception on caching reference=%s: %s' % (reference, str(e)))

def cache_resolved_get(reference):
    """

    :param reference:
    :return:
    """
    try:
        resolved = redis_db.get(name=current_app.config['REDIS_NAME_PREFIX'] + reference)
    except RedisError:
        resolved = None

    return resolved

def format_resolved_reference(returned_format, resolved, reference, cache=True):
    """

    :param returned_format:
    :param resolved:
    :param reference:
    :param cache:
    :return:
    """
    if cache:
        cache_resolved_set(reference, resolved)
    if 'application/json' in returned_format:
        resolved = resolved.split()
        return {'score': resolved[0], 'bibcode': resolved[1], 'reference': reference}
    return '%s -- %s' % (resolved, reference)


def text_resolve(reference, returned_format):
    """

    :param reference:
    :param returned_format:
    :return:
    """
    try:
        resolved = cache_resolved_get(reference)
        if resolved:
            return format_resolved_reference(returned_format,
                                             resolved=resolved,
                                             reference=reference,
                                             cache=False)

        if bool(RE_NUMERIC_VALUE.search(reference)):
            parsed_ref = text_parser(reference)
            return format_resolved_reference(returned_format,
                                             resolved=str(solve_reference(Hypotheses(parsed_ref))),
                                             reference=reference,
                                             cache=True)
        else:
            raise ValueError('Reference with no year and volume cannot be resolved.')
    except NoSolution:
        return format_resolved_reference(returned_format, resolved='0.0 %s' % (19 * '.'), reference=reference)
    except Exception as e:
        current_app.logger.error('Exception: %s', str(e))
        raise


@advertise(scopes=[], rate_limit=[1000, 3600 * 24])
@bp.route('/text/<reference>', methods=['GET'])
def text_get(reference):
    """

    :param reference:
    :return:
    """
    returned_format = request.headers.get('Accept', 'text/plain')

    reference = urllib.unquote(reference)

    current_app.logger.info('received GET request with reference=`{reference}` to resolve in text mode'.format(reference=reference))

    start_time = time.time()
    result = text_resolve(reference, returned_format)
    current_app.logger.debug("GET request processed in %s ms" % ((time.time() - start_time) * 1000))

    return return_response({'resolved': result}, 200, 'application/json; charset=UTF8')


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

    current_app.logger.info('received POST request with references={references} to resolve in text mode'. format(references=','.join(references)))

    returned_format = request.headers.get('Accept', 'text/plain')

    start_time = time.time()
    results = []
    for reference in references:
        results.append(text_resolve(reference, returned_format))
    current_app.logger.debug("POST request with %d reference(s) processed in %s ms" % (len(references), (time.time() - start_time) * 1000))

    if returned_format == 'application/json':
        return return_response({'resolved': results}, 200, 'application/json; charset=UTF8')
    return return_response({'resolved':'\n'.join(results)}, 200, 'application/json; charset=UTF8')


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

    returned_format = request.headers.get('Accept', 'text/plain')

    results = []
    parsed_references = xml_parser(references)
    for parsed_reference in parsed_references:
        try:
            resolved = str(solve_reference(Hypotheses(parsed_reference)))
            if resolved.startswith('0.0'):
                raise
            result = format_resolved_reference(returned_format, resolved=resolved, reference=parsed_reference['refstr'])
        except Exception as e:
            current_app.logger.error('Exception: %s' %(str(e)))
            # lets attempt to resolve using the text model
            if 'refplaintext' in parsed_reference:
                reference = urllib.unquote(parsed_reference['refplaintext'])
                current_app.logger.info('attempting to resolve the reference=`{reference}` in text mode now'.format(reference=reference))
                try:
                    parsed_ref = text_parser(reference)
                    result = format_resolved_reference(returned_format,
                                                       resolved=str(solve_reference(Hypotheses(parsed_ref))),
                                                       reference=reference)
                except Exception as e:
                    current_app.logger.error('Exception: %s', str(e))
                    result = format_resolved_reference(returned_format, resolved='0.0 %s' % (19 * '.'), reference=reference)
                    continue
            else:
                result = format_resolved_reference(returned_format, resolved='0.0 %s' % (19 * '.'), reference=parsed_reference['refstr'])
                continue
        finally:
            results.append(result)

    if len(results) == len(references):
        if returned_format == 'application/json':
            return return_response({'resolved': results}, 200, 'application/json; charset=UTF8')
        return return_response({'resolved':'\n'.join(results)}, 200, 'application/json; charset=UTF8')
    return return_response({'error': 'unable to resolve any references'}, 400, 'text/plain; charset=UTF8')


@advertise(scopes=['ads:reference-service'], rate_limit=[1000, 3600 * 24])
@bp.route('/pickle_crf', methods=['PUT'])
def pickle_crf():
    """
    endpoint to be called locally only whenever the models (either text or xml) has been changed

    :return:
    """
    # to save a new text model
    create_text_model()

    return return_response({'OK': 'objects saved'}, 200, 'text/plain; charset=UTF8')


@advertise(scopes=['ads:reference-service'], rate_limit=[1000, 3600 * 24])
@bp.route('/pickle_source_matcher', methods=['PUT'])
def pickle_source_matcher():
    """
    endpoint to be called locally only whenever the files of source matcher has been updated

    :return:
    """
    # to save a new source matcher()
    create_source_matcher()

    return return_response({'OK': 'objects saved'}, 200, 'text/plain; charset=UTF8')
