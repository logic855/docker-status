from flask import Flask
from multiprocessing import Process, Value
from time import sleep

import datetime
import os
import re
import urllib2
import sys
import traceback

OK_STATUSES = [ 200, 301, 302 ]
HTTP_TIMEOUT = os.environ.get('HTTP_TIMEOUT', 30)
TEST_INTERVAL = os.environ.get('TEST_INTERVAL', 30)
DEBUG = os.environ.get('DEBUG', False) == "true"
LISTEN_HOST = os.environ.get('LISTEN_HOST', '0.0.0.0')
LISTEN_PORT = os.environ.get('LISTEN_PORT', '80')
DELAY_START = os.environ.get('DELAY_START', False) == "true"

app = Flask(__name__)

checks = {}

class NoRedirectHTTPErrorProcessor(urllib2.HTTPErrorProcessor):
    def http_response(self, request, response):
        return response

    https_response = http_response

url_opener = urllib2.build_opener(NoRedirectHTTPErrorProcessor)

@app.route("/")
def status():
    for (host, (status, timestamp, process)) in checks.items():
        if (status.value not in OK_STATUSES or
            timestamp.value < int(
                (datetime.datetime.now() - datetime.timedelta(
                    seconds=TEST_INTERVAL*2
                )).strftime("%s")
            )
           ):
            return "Fail", 500

    return "OK", 200

def checker(host, status, timestamp):
    get_path = os.environ.get("%s_GET_PATH" % host, "/")
    use_host_ip = os.environ.get("%s_CONNECT_IP" % host, False) == 'true'

    if use_host_ip:
        check_host = os.environ.get("%s_PORT_80_TCP_ADDR" % host)
    else:
        check_host = host

    while True:
        try:
            result = url_opener.open("http://%s%s" % (check_host, get_path),
                                     timeout=HTTP_TIMEOUT)
            status.value = result.getcode()
        except Exception as e:
            status.value = getattr(e, 'code', -1)
            traceback.print_exc()

        timestamp.value = int(datetime.datetime.now().strftime('%s'))
        print datetime.datetime.now(), host, status.value
        sys.stdout.flush()
        sleep(TEST_INTERVAL)

if __name__ == "__main__":
    hosts = [ var.split('_PORT_80_TCP')[0] for var in os.environ
              if re.match('[A-Z0-9_]+_PORT_80_TCP$', var) ]

    for host in hosts:
        status = Value('i', -1)
        timestamp = Value('i', -1)
        process = Process(target=checker, args=(host, status, timestamp))
        process.start()
        checks[host] = (status, timestamp, process)

        if DELAY_START:
            sleep(TEST_INTERVAL)

    app.run(host=LISTEN_HOST, port=LISTEN_PORT, debug=DEBUG)
