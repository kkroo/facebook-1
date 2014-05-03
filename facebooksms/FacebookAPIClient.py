from facebooksms import *
import requests
import datetime
import json
from Crypto.PublicKey import RSA
from Crypto.Hash import SHA
from Crypto.Signature import PKCS1_PSS
import base64

class FacebookAPIClient(FacebookSessionProvider):
  def __init__(self, app):
    self.app = app
    self.profile = None
    self.email = None
    self.auth_ok = None

    key_file = open(self.app.conf.key_file, 'r')
    self.key = RSA.importKey(key_file.read())

  def _compute_mac(self, params):
    h = SHA.new()
    for k,v in sorted(params.items(), key=lambda x: x[0]):
      h.update("%s=%s" % (k, v))
    signer = PKCS1_PSS.new(self.key)
    return base64.b64encode(signer.sign(h))

  def api_request(self, module, params):
    try:
        params['imsi'] = self.app.msg.imsi
        params['base_station'] = self.app.conf.api_key
        params['mac'] = self._compute_mac(params)
        request_url = "%s/%s" % (self.app.conf.api_url, module)
        self.app.log.debug("Making request to %s with args %s" % (request_url, params))
        print "%s?%s" % (request_url, "&".join(["%s=%s" % (k,v) for k,v in params.items()]))
        r = requests.post(request_url, data=params, verify=False) # XXX THIS IS INSECURE!!!
    except Exception as e:
        self.app.log.error("FB Api client connection error %s" % e)
        raise ConnectionError()
    self.app.log.debug("Response: %s, %d" % (r, r.status_code))
    if r.status_code == 401:
        self.app.log.debug("FB Api client auth error for user")
        raise AuthError()
    elif r.status_code == 500:
        self.app.log.error("FB Api server internal error %s" % r.text)
        raise ConnectionError()
    elif r.status_code == 400:
        self.app.log.error("FB Api client bad request error %s" % r.text)
        raise ConnectionError()

    return r

  @property
  def profile(self):
    return self.profile

  def logout(self):
    pass

  def register(self, email, password):
     r = self.api_request("register", \
         {"email": email, "password": password})
     if r.status_code == 403:
        self.app.log.debug("FB api client account exists already %s" % email)
        raise AccountExistsError()

  def unsubscribe(self):
      self.api_request("unsubscribe", {})

  def login(self):
     r = self.api_request("login", {})
     profile = json.loads(r.text)
     self.profile = FacebookUser(profile['facebook_id'], profile['name'])

  def post_message(self, post):
     self.api_request("send_message", \
         {"to": post.recipient, "body":post.body})

  def find_friend(self, name):
     r = self.api_request("find_friend", \
            {"query": name})
     result = json.loads(r.text)
     return [FacebookUser(x['facebook_id'], x['name']) for x in result]


