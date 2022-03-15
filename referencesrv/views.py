# -*- coding: utf-8 -*-

from builtins import str
from flask import current_app, request, Blueprint, Response
from flask_discoverer import advertise
from flask_redis import FlaskRedis
from redis import RedisError
from hashlib import md5

import json
import urllib.request, urllib.parse, urllib.error
import regex as re
import time

from referencesrv.parser.crf import CRFClassifierText, create_text_model, load_text_model
from referencesrv.resolver.solve import solve_reference
from referencesrv.resolver.hypotheses import Hypotheses
from referencesrv.resolver.sourcematchers import create_source_matcher, load_source_matcher
from referencesrv.resolver.common import NoSolution, Incomplete


bp = Blueprint('reference_service', __name__)
redis_db = FlaskRedis()

RE_NUMERIC_VALUE = re.compile(r'\d')

# @bp.before_app_first_request
def text_model():
    """

    :return:
    """
    # start_time = time.time()
    # load only if in production mode
    if current_app.config['REFERENCE_SERVICE_LIVE']:
        current_app.extensions['text_crf'] = load_text_model()
        current_app.extensions['source_matcher'] = load_source_matcher()
    # current_app.logger.debug("Loading neccesary pickels in {duration} ms".format(duration=(time.time() - start_time) * 1000))


def text_parser(reference):
    """

    :return:
    """

    return current_app.extensions['text_crf'].parse(reference)


def return_response(results, status, content_type='application/json'):
    """

    :param results: results in a dict
    :param status: status code
    :return:
    """
    if 'application/json' in content_type:
        response = json.dumps(results)
    else:
        response = results['resolved']

    if status != 200:
        current_app.logger.error('sending response status={status}'.format(status=status))
        current_app.logger.error('sending response text={response}'.format(response=results))
        r = Response(response=response, status=status)
        r.headers['content-type'] = content_type
        return r

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
        # save it to cache in MD5 format
        reference_md5 = md5(reference.encode('utf-8')).hexdigest()
        redis_db.set(name=current_app.config['REDIS_NAME_PREFIX'] + reference_md5, value=resolved.encode('utf-8'),
                     ex=current_app.config['REDIS_EXPIRATION_TIME'])
    except RedisError as e:
        current_app.logger.error('exception on caching reference={reference}: {error}'.format(reference=reference, error=str(e)))
    except AttributeError as e:
        current_app.logger.error('exception on caching reference={reference}: {error}'.format(reference=reference, error=str(e)))

def cache_resolved_get(reference):
    """

    :param reference:
    :return:
    """
    try:
        reference_md5 = md5(reference.encode('utf-8')).hexdigest()
        resolved = redis_db.get(name=current_app.config['REDIS_NAME_PREFIX'] + reference_md5).decode('utf-8')
        current_app.logger.debug('fetched reference={reference} from cache'.format(reference=reference))
    except RedisError:
        resolved = None
    except AttributeError:
        # when redis server is not activated
        resolved = None
    return resolved

def format_resolved_reference(returned_format, resolved, reference, id, cache=True, comment=None):
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
        result = {'refstring': reference, 'score': resolved[0], 'bibcode': resolved[1]}
        if comment:
            result['comment'] = comment
        if id:
            result['id'] = id
        return result
    result = '%s -- %s' % (resolved, reference)
    if comment:
        result = '%s ;; %s'%(result, comment)
    if id:
        result = '%s ;; %s' % (result, id)
    return result


def check_number_references(references, reference_type):
    """
    truncate number of references if more than what is allowed for one processing call

    :param references:
    :param reference_type: reference string or parsed reference
    :return:
    """
    num_references = len(references)
    max_num_references = current_app.config['REFERENCE_SERVICE_MAX_REFERENCE']
    truncated_message = None
    if num_references > max_num_references:
        current_app.logger.error('received {num_references} {reference_type} to resolve, maximum number of references that can be resolved in one call is {max_num_references} which shall be resolved'.format(
            num_references=num_references,
            reference_type = reference_type,
            max_num_references=max_num_references))
        references = references[:max_num_references]
        truncated_message = 'Resolved maximum number of references allowed {max_num_references}.'.format(max_num_references=max_num_references)
    return references, truncated_message


def text_resolve(reference, returned_format, id):
    """

    :param reference:
    :param returned_format:
    :return:
    """
    not_resolved = '0.0 %s' % (19 * '.')
    try:
        resolved = cache_resolved_get(reference)
        if resolved:
            return format_resolved_reference(returned_format,
                                             resolved=resolved,
                                             reference=reference,
                                             id=id)

        if bool(RE_NUMERIC_VALUE.search(reference)):
            parsed_ref = text_parser(reference)
            if parsed_ref:
                return format_resolved_reference(returned_format,
                                                 resolved=str(solve_reference(Hypotheses(parsed_ref))),
                                                 reference=reference,
                                                 id=id)
            error_comment = 'NoSolution: unable to parse'
            current_app.logger.error('Exception: {error}'.format(error=error_comment))
            return format_resolved_reference(returned_format,
                                             resolved=not_resolved,
                                             reference=reference,
                                             id=id,
                                             comment=error_comment)
        else:
            error_comment = 'ValueError: reference with no year and volume cannot be resolved.'
            current_app.logger.error('Exception: {error}'.format(error=error_comment))
            return format_resolved_reference(returned_format,
                                             resolved=not_resolved,
                                             reference=reference,
                                             id=id,
                                             comment=error_comment)
    except (NoSolution, Incomplete, ValueError) as e:
        error_comment = 'Exception: {error}'.format(error=str(e))
        current_app.logger.error(error_comment)
        return format_resolved_reference(returned_format,
                                         resolved=not_resolved,
                                         reference=reference,
                                         id=id,
                                         comment=error_comment)
    except Exception as e:
        error_comment = 'Exception: {error}'.format(error=str(e))
        current_app.logger.error(error_comment)
        return format_resolved_reference(returned_format,
                                         resolved=not_resolved,
                                         reference=reference,
                                         id=id,
                                         comment=error_comment)

def xml_resolve(parsed_reference, returned_format):
    """

    :param parsed_reference:
    :param returned_format:
    :return:
    """
    not_resolved = '0.0 %s' % (19 * '.')
    try:
        resolved = str(solve_reference(Hypotheses(parsed_reference)))
        if resolved.startswith('0.0'):
            raise "Not Resolved"
        reference_str = parsed_reference.get('refstr', None) or parsed_reference.get('refplaintext', None)
        return format_resolved_reference(returned_format,
                                         resolved=resolved,
                                         reference=reference_str,
                                         id=parsed_reference.get('id', None))
    except Exception as e:
        current_app.logger.error('Exception: {error}'.format(error=str(e)))
        # lets attempt to resolve using the text model
        reference_str = parsed_reference.get('refplaintext', None)
        if reference_str:
            current_app.logger.info('attempting to resolve the reference=`{reference_str}` in text mode now'.format(reference_str=reference_str))
            if bool(RE_NUMERIC_VALUE.search(reference_str)):
                try:
                    parsed_ref = text_parser(reference_str)
                    if parsed_ref:
                        return format_resolved_reference(returned_format,
                                                         resolved=str(solve_reference(Hypotheses(parsed_ref))),
                                                         reference=reference_str,
                                                         id=parsed_reference.get('id', None),
                                                         cache=True)
                    error_comment = 'NoSolution: unable to parse'
                    current_app.logger.error('Exception: {error}'.format(error=error_comment))
                    return format_resolved_reference(returned_format,
                                                     resolved=not_resolved,
                                                     reference=reference_str,
                                                     id=parsed_reference.get('id', None),
                                                     comment=error_comment)

                except (NoSolution, Incomplete, ValueError) as e:
                    error_comment = 'Exception: {error}'.format(error=str(e))
                    current_app.logger.error(error_comment)
                    return format_resolved_reference(returned_format,
                                                     resolved=not_resolved,
                                                     reference=reference_str,
                                                     id=parsed_reference.get('id', None),
                                                     comment=error_comment)
            else:
                error_comment = 'ValueError: reference with no year and volume cannot be resolved.'
                current_app.logger.error('Exception: {error}'.format(error=error_comment))
                return format_resolved_reference(returned_format,
                                                 resolved=not_resolved,
                                                 reference=reference_str,
                                                 id=parsed_reference.get('id', None),
                                                 comment=error_comment)
        else:
            return format_resolved_reference(returned_format,
                                             resolved=not_resolved,
                                             reference=parsed_reference.get('refstr', None),
                                             id=parsed_reference.get('id', None))


@advertise(scopes=[], rate_limit=[1000, 3600 * 24])
@bp.route('/text/<reference>', methods=['GET'])
def text_get(reference):
    """

    :param reference:
    :return:
    """
    returned_format = request.headers.get('Accept', 'text/plain')

    reference = urllib.parse.unquote(reference)

    current_app.logger.info('received GET request with reference=`{reference}` to resolve in text mode'.format(reference=reference))

    # start_time = time.time()
    result = text_resolve(reference, returned_format, None)
    # current_app.logger.debug("GET request processed in {duration} ms".format(duration=(time.time() - start_time) * 1000))

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
    references, truncated_message = check_number_references(references, reference_type="references")

    current_app.logger.info('received POST request with references={references} to resolve in text mode'.format(references=','.join(references)[:250]))

    returned_format = request.headers.get('Accept', 'text/plain')

    if 'id' in payload:
        ids = payload['id']
    else:
        ids = [None]*len(references)

    # start_time = time.time()
    results = []
    for reference, id in zip(references, ids):
        results.append(text_resolve(reference, returned_format, id))
    # current_app.logger.debug("POST request with {num} reference(s) processed in {duration} ms".format(num=len(references), duration=(time.time() - start_time) * 1000))

    if returned_format == 'application/json':
        response = {'resolved': results}
        if truncated_message:
            response['message'] = truncated_message
        return return_response(response, 200, 'application/json; charset=UTF8')

    response = {'resolved':'\n'.join([str(result) for result in results])}
    if truncated_message:
        response['message'] = truncated_message
    return return_response(response, 200, 'text/plain; charset=UTF8')


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
    if 'parsed_reference' not in payload:
        return {'error': 'no reference found in payload (parameter name is `parsed_reference`)'}, 400

    parsed_references = payload['parsed_reference']
    references, truncated_message = check_number_references(parsed_references, reference_type="parsed references")

    current_app.logger.debug('received POST request with {count} references to resolve in xml mode.'.format(count=len(parsed_references)))

    returned_format = request.headers.get('Accept', 'text/plain')

    results = []
    for parsed_reference in parsed_references:
        results.append(xml_resolve(parsed_reference, returned_format))

    if returned_format == 'application/json':
        response = {'resolved': results}
        if truncated_message:
            response['message'] = truncated_message
        return return_response(response, 200, 'application/json; charset=UTF8')

    response = {'resolved': '\n'.join(results)}
    if truncated_message:
        response['message'] = truncated_message
    return return_response(response, 200, 'application/text; charset=UTF8')


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
    try:
        # to save a new source matcher()
        create_source_matcher()
        return return_response({'OK': 'objects saved'}, 200, 'text/plain; charset=UTF8')
    except Exception as e:
        return return_response({'Error: %s'%str(e)}, 400, 'text/plain; charset=UTF8')
