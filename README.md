[![Build Status](https://travis-ci.org/adsabs/reference_service.svg)](https://travis-ci.org/adsabs/export_service)
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


### GET a request:


### POST a request:
    

## Maintainers

Golnaz
