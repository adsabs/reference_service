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
Next run the script with one reference per line.

    $ python test_reference_service.py "Adler, I., et al. 1972, Science, 175, 436
    Anders, E. 1989, Nature, 342, 255"


## API


#### Make a GET request with a reference to score and resolved bibcode:

    curl -H "Authorization: Bearer <your API token>" -X GET https://dev.adsabs.harvard.edu/v1/reference/text/<reference>

For example to return resolved the reference `Giraud et al., 1986, A&A, 170, 1`, you would do   

    curl -H "Authorization: Bearer <your API token>" -X GET https://dev.adsabs.harvard.edu/v1/reference/text/Giraud%20et%20al.%2C%201986%2C%20A%26A%2C%20170%2C%201

which returns the confidence score, followed by resolved bibcode, also returns the requested reference:

    {"resolved": "0.9 1986A&A...170....1G -- Giraud et al., 1986, A&A, 170, 1"}
    
To return the results as fielded json, include `Accept: application/json` in the header. For example

    curl -H "Authorization: Bearer <your API token>" -H "Accept: application/json" -X GET https://dev.adsabs.harvard.edu/v1/reference/text/Giraud%20et%20al.%2C%201986%2C%20A%26A%2C%20170%2C%201

which returns

    {"resolved": {"score": "0.9", "bibcode": "1986A&A...170....1G", "reference": "Giraud et al., 1986, A&A, 170, 1"}}
       
### POST a request:
    

## Maintainers

Golnaz
