[![Build Status](https://travis-ci.org/adsabs/reference_service.svg)](https://travis-ci.org/adsabs/reference_service)
[![Coverage Status](https://coveralls.io/repos/adsabs/reference_service/badge.svg)](https://coveralls.io/r/adsabs/reference_service?branch=master)


# ADS Reference Service

## Short Summary

This microservice .


## Setup (recommended)

    $ virtualenv python
    $ source python/bin/activate
    $ pip install -r requirements.txt
    $ pip install -r dev-requirements.txt
    $ vim local_config.py # edit, edit

    
## Testing

On your desktop run:

    $ py.test
    

To resolve references, edit `test_reference_service.py` and add authorization token. 
Next run the script with either one reference per line

    $ python test_reference_service.py "Adler, I., et al. 1972, Science, 175, 436
    Anders, E. 1989, Nature, 342, 255"

or have list of text refernces in a file, which shall send the maximum number of references that servcie accepts, 16, to servcie and the result to the console. 

    $ python test_reference_service.py -i <input filename>
    

## API


#### Make a GET request for a text reference:

To make a GET request with a reference string which returns the score and resolved bibcode do, 

    curl -H "Authorization: Bearer <your API token>" -X GET https://dev.adsabs.harvard.edu/v1/reference/text/<reference>

For example, to resolved the reference `Giraud et al., 1986, A&A, 170, 1`, you would do   

    curl -H "Authorization: Bearer <your API token>" -X GET https://dev.adsabs.harvard.edu/v1/reference/text/Giraud%20et%20al.%2C%201986%2C%20A%26A%2C%20170%2C%201

which returns the confidence score, followed by resolved bibcode, and the requested text reference:

    {"resolved": "0.9 1986A&A...170....1G -- Giraud et al., 1986, A&A, 170, 1"}
    
To return the result as fielded json, include `Accept: application/json` in the header. For example

    curl -H "Authorization: Bearer <your API token>" -H "Accept: application/json" -X GET https://dev.adsabs.harvard.edu/v1/reference/text/Giraud%20et%20al.%2C%201986%2C%20A%26A%2C%20170%2C%201

which returns,

    {"resolved": {"score": "0.9", "bibcode": "1986A&A...170....1G", "refstr": "Giraud et al., 1986, A&A, 170, 1"}}

       
### Make a POST request for a text reference:

To make a POST request, list text references in an array in the following format,

    {"reference":["<text_reference1>","<text_reference2>", ...]}
    
and call the end point    

    curl -H "Authorization: Bearer <your API token>" -H "Content-Type: application/json" -H "Accept: application/json" -X POST -d '{"reference":["Giraud et al., 1986, A&A, 170, 1"]}' https://api.adsabs.harvard.edu/v1/reference/text


### Make a POST request for a parsed xml reference:

To make a POST request, list parsed references in an array in the following format,

    {"parsed_reference":[{<parsed_reference1>},{<parsed_reference2>}, ...]}

and call the end point    

    curl -H "Authorization: Bearer <your API token>" -H "Content-Type: application/json" -H "Accept: application/json" -X POST -d {"parsed_reference":"[{'authors': 'nielsen', 'journal': 'Quantum Computation and Quantum Information', 'year': '2000', 'refplaintext': 'Quantum Computation and Quantum Information nielsen 2000'}]"} https://api.adsabs.harvard.edu/v1/reference/xml


## Maintainers

Golnaz

