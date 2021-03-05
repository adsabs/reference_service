#!/usr/bin/python
# -*- coding: utf-8 -*-

import requests

url = "http://localhost:5000/pickle_crf"
#for i in range(16):
for i in range(1):
    r = requests.put(url)
    print('i=%d, code=%d, reason=%s'%(i,r.status_code,r.reason))
    print(r.text)
