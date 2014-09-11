from . import *
import requests
import datetime
import json
from Crypto.PublicKey import RSA
from Crypto.Hash import SHA
from Crypto.Signature import PKCS1_PSS
import base64
import urllib
import yaml
import re

class FacebookAPIClient(FacebookSessionProvider):
  def __init__(self, app):
    self.app = app
    self._profile = None
    self._init_api()

  def _init_api(self):
    """ This methods initializes the API client with the server the first time
        it is run.
    """
    if len(self.app.conf.api_key) == 0:

      # Get our external ip
      r = requests.get("http://checkip.dyndns.org/")
      ip = re.findall('\d{2,3}.\d{2,3}.\d{2,3}.\d{2,3}', r.text)[0]

      # Register with API
      callback_url = "%s://%s:%s" % (self.app.conf.callback_protocol, ip, self.app.conf.callback_port)
      cert = open(self.app.conf.cert_file).read()
      r = self._api_request("bts", {'callback_url': callback_url, 'cert': cert})
      resp = json.loads(r.text.encode('ascii', 'ignore'))

      # Set our API Key
      self.app.conf.config_dict['api_key'] = resp['api_key']
      conf_file = open("/etc/facebooksms/client.yaml", "w") # TODO Dont hard code path
      yaml.dump(self.app.conf.config_dict, conf_file)

      # Set API Server cert
      cert = resp['cert']
      cert_file = open(self.app.conf.api_cert_file, "w")
      cert_file.write(cert)

      self.app.log.debug("Registered BTS with API Service:\n" + \
                            "\tkey='%s', server cert='%s'" % (self.app.conf.api_key, cert))


  def register(self):
     r = self._api_request("register")

  def unsubscribe(self):
      self._api_request("unsubscribe")

  def post_message(self, post):
     self._api_request("send_message", \
         {"to": post.recipient, "body":post.body})

  def find_friend(self, name):
     r = self._api_request("find_friend", \
            {"query": name})
     result = json.loads(r.text)
     return [FacebookUser(x['facebook_id'], x['name']) for x in result]

  def _api_request(self, module, params={}):
    try:
        params['imsi'] = self.app.msg.imsi
        params['bts_key'] = self.app.conf.api_key
        params['mac'] = WebCommonBase.compute_mac(params, self.app.conf.key)
        request_url = "%s/%s" % (self.app.conf.api_url, module)
        self.app.log.debug("Making request to %s with args %s" % (request_url, params))
        r = requests.post(request_url, data=params, verify=False) # XXX THIS IS INSECURE!!!
    except Exception as e:
        self.app.log.error("FB Api client connection error: %s" % e)
        raise ConnectionError()
    self.app.log.debug("Response: %s, %d" % (r, r.status_code))

    if r.status_code == 401:
        self.app.log.debug("FB Api client auth error for user")
        raise AuthError()
    elif r.status_code == 500:
        self.app.log.error("FB Api server internal error: %s" % r.text)
        raise ConnectionError()
    elif r.status_code == 400:
        self.app.log.error("FB Api client bad request error: %s" % r.text)
        raise ConnectionError()
    elif r.status_code == 404:
        self.app.log.error("Service not found: %s" % r.text)
        raise ConnectionError()
    elif r.status_code != 202:
        self.app.log.error("Other error happened: %s" % r.text)
        raise ConnectionError()

    return r

  @property
  def profile(self):
    if self._profile == None:
      r = self._api_request("profile")
      resp = json.loads(r.text)
      self._profile = FacebookUser(resp['facebook_id'], resp['name'])
    return self._profile

