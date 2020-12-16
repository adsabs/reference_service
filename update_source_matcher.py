#!/usr/bin/python
# -*- coding: utf-8 -*-

import requests

"""
source matcher files and locations

this file gets updated often
-rw-r--r--  1 gshapurian  staff 1981132 Sep 10 16:01 /proj/ads/abstracts/links/bibstems.dat

-rw-rw-r--  1 gshapurian  staff  172308 Jul 21 14:29 /proj/ads_references/etc/conferences.dat
-rw-rw-r--  1 gshapurian  staff   24615 Feb 28  2008 /proj/ads_references/etc/conferences_abbrev.dat
-rw-rw-r--  1 gshapurian  staff  173463 Jul 30 21:58 /proj/ads_references/etc/journals.dat
-rw-rw-r--  1 gshapurian  staff   97528 Aug  4 16:22 /proj/ads_references/etc/journals_abbrev.dat
-rw-rw-r--  1 gshapurian  staff     364 Nov 29  2006 /proj/ads_references/etc/preprints.dat


this file got deprecated in August 2020
-rw-rw-r--  1 gshapurian  staff   13540 Apr 27  2005 /proj/ads_references/etc/aps_abbrev.dat

this file is not being used in source matcher
the three entries have been added to journals_not_ADS.dat included in source matcher here
-rw-r--r--  1 gshapurian  staff      64 Jan 18  2011 /proj/ads_references/etc/notinADS.dat
"""


url = "http://localhost:5000/pickle_source_matcher"
r = requests.put(url)
print 'code=',r.status_code,'reason=',r.reason
print r.text
