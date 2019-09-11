import sys
import requests
import json

def resolve(references):
    """

    :param references:
    :return:
    """
    payload = {'reference': references}

    response = requests.post(
        url='https://dev.adsabs.harvard.edu/v1/reference/text',
        headers={'Authorization': 'Bearer ' + 'your token here'},
        data=payload
    )

    result = {}
    result['status_code'] = response.status_code
    if response.status_code == 200:
        result['resolved'] = json.loads(response.content)['resolved'].split('\n')
    else:
        result['resolved'] = None
    return result


if __name__ == "__main__":
    result = resolve(sys.argv[1].split('\n'))
    if result['status_code'] == 200:
        print '\n'
        for r in result['resolved']:
            print r
        print '\n'
    else:
        print 'error code: ', result['status_code']