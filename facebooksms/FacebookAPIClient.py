from facebooksms import *
import requests
import datetime


class FacebookAPIClient(FacebookSessionProvider):
  error_codes = { 0: "Auth Error", 1: "Server Error" }
  status_codes = {}

  def __init__(self, app):
    self.app = app
    self.profile = None
    self.email = None
    self.auth_ok = None

  def api_request(self, module, params):
    try:
        params['imsi'] = self.app.imsi
        request_url = "%s/%s" % (self.app.conf.api_url, module)
        self.app.log.debug("Making request to %s with args %s" % (request_url, params))
        r = requests.post(request_url, data=params)
    except Exception as e:
        self.app.log.error("FB Api client connection error %s" % e)
        raise ConnectionError()
    self.app.log.debug("Response: %s, %d" % (r, r.status_code))
    if r.status_code == 401:
        self.app.log.debug("FB Api client auth error for user")
        raise AuthError()
    elif r.status_code == 500:
        self.app.log.error("FB Api server connection error %s" % r.text)
        raise ConnectionError()
    elif r.status_code == 400:
        self.app.log.error("FB Api server bad request error %s" % r.text)
        raise ConnectionError()

    return r

  @property
  def profile(self):
    return self.profile

  def logout(self):
    pass

  def register(self, email, password):
     r = self.api_request("register", \
         {"email": email, "password": password, "base_station": self.app.conf.api_key})
     if r.status_code == 403:
        self.app.log.debug("FB api client account exists already %s" % email)
        raise AccountExistsError()

  def login(self, email, password):
     self.api_request("login", {"email": email})

     self.email = email
     psuedo_id = abs(hash(email)) % 10000
     psuedo_name = email.split('@')[0]
     self.profile = FacebookUser(psuedo_id, psuedo_name)

  def post_message(self, post):
     self.api_request("send_message", \
         {"from_email": self.email, "to": post.recipient, "body":post.body})


