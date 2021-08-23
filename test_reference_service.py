import sys, os, io
import requests
import argparse
import json

def resolve(references):
    """

    :param references:
    :return:
    """
    payload = {'reference': references}

    response = requests.post(
        url='https://api.adsabs.harvard.edu/v1/reference/text',
        headers={'Authorization': 'Bearer ' + 'your token here',
                 'Content-Type': 'application/json',
                 'Accept':'application/json'},
        data=json.dumps(payload)
    )

    if response.status_code == 200:
        return json.loads(response.content)['resolved'], 200
    return None, response.status_code


def output(results, status):
    """

    :param results:
    :param status:
    :return:
    """
    if results:
        print('\n')
        for result in results:
            print(result)
        print('\n')
    else:
        print('error code: ', status)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Test script for reference service')
    parser.add_argument('-r', '--references', help='list of text references separated by `\n`')
    parser.add_argument('-i', '--input', help='the path to input file containing list of text references, one per line.')
    args = parser.parse_args()
    if args.references:
        references = args.references.split('\\n')
        for i in range(0, len(references), 16):
            results, status = resolve(references[i:i + 16])
            output(results, status)
    elif args.input:
        with io.open(os.path.join(os.getcwd(), args.input), 'r', encoding="utf-8") as f:
            references = list(reference[:-1] for reference in f)
            for i in range(0, len(references), 16):
                results, status = resolve(references[i:i+16])
                output(results, status)
    sys.exit(0)

