import os
import logging
from twisted.internet import defer
from twisted.web.client import Agent
from twisted.web.http_headers import Headers
from OpenSSL import crypto

def make_sydent(config):
    pass

class FakeChannel:
    pass

def make_request(method, url, headers, body, timeout):
    pass

class FakeSite:
    pass

class ToTwistedHandler(logging.Handler):
    pass

def setup_logging():
    pass

fake_cert = crypto.X509()
fake_cert.set_version(3)
fake_cert.set_serial_number(1000)
fake_cert.get_subject().CN = "fake_server"
fake_cert.set_issuer(fake_cert.get_subject())
fake_cert.set_pubkey(fake_cert.get_pubkey())
fake_cert.sign(fake_cert.get_pubkey(), "sha256")