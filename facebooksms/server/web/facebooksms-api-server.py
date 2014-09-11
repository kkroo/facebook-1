#!/usr/bin/env python
import threading
import traceback
import yaml
import web, requests
import logging
import uuid
import json
import sys, os
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP
import base64
import urllib, urlparse
from facebooksms.server import *

urls = ("/oauth", "oauth",
        "/oauth_callback", "oauth_callback",
        "/register", "register",
        "/unsubscribe", "unsubscribe",
        "/send_message", "send_message",
        "/find_friend",  "find_friend",
        "/profile",  "profile",
        "/bts", "bts")


#
# FB OAuth stuff
#

# This is the landing page a user is sent to acivate an account
class oauth:
  def __init__(self):
    self.config = web.fb_config

  def GET(self):
    body = """<form action="/oauth" method="POST">
                <label for="imsi">IMSI</label>
                <input type="text" name="imsi" />
                <input type="submit" value="Submit" />
              </form>
           """
    web.header('Content-Type', 'text/html')
    raise web.OK(body)

  def POST(self):
    data = web.input()
    if "imsi" not in data:
      web.log.debug("Failed request, missing args")
      raise web.BadRequest("Missing IMSI")
    else:
      imsi = str(data.imsi)
      params = { 'client_id' : self.config.fb_client_id,
                 'redirect_uri' : "%s/oauth_callback?imsi=%s" % (self.config.server_url, imsi),
                 'scope': 'xmpp_login,email'
                 }

      link = "https://www.facebook.com/dialog/oauth?" +  \
        urllib.urlencode(params)
      raise web.redirect(link)

""" This class is invoked as a redirect from FB after authorization. 
    It handles retrieving the access token, activating the user at the bts,
    and starting the XMPP session
"""
class oauth_callback:

  def __init__(self):
    self.config = web.fb_config

  def send_activation(self, imsi):
    accounts = web.db.select([self.config.t_users, self.config.t_base_stations], \
        where="imsi=$imsi " + \
          "AND %s.bts_key = %s.key" % (self.config.t_users, self.config.t_base_stations), \
        vars={"imsi": imsi})
    account = accounts[0]

    params = {'imsi': account.imsi}
    params['mac'] = WebCommonBase.compute_mac(params, self.config.key)
    r = requests.post(account.callback_url + "/activate", params, verify=False) # XXX THIS IS INSECURE!!!
    if r.status_code != 202:
      raise Exception("Failed to send activation with status code %s: %s" % (r.status_code, r.text))

  def GET(self):
    data = web.input()
    needed_fields = ["code", "imsi"]

    if not all(i in data for i in needed_fields):
      web.log.error("Failed to get auth token, missing args")
      raise web.BadRequest()
    else:
      code = str(data.code)
      imsi = str(data.imsi)

      try:
        # Get our short lived code. This will expire quickly.
        access_token = FBOAuthChatSession.get_access_token(self.config, code, imsi)

        # Trade in for the long lived access token
        access_token = FBOAuthChatSession.get_llat(self.config, access_token)

        # We need the email as well
        email = FBOAuthChatSession.get_email(self.config, access_token)
      except Exception as e:
        web.log.warning("Failed to get credentials from FB: %s" % e)
        raise web.Unauthorized()

      # Check if the account exists
      result =  web.db.select(self.config.t_users, where="imsi=$imsi AND oauth is null", vars={'imsi': imsi})
      if not len(list(result)):
        raise web.BadRequest("Invalid IMSI")

      # Now start the XMPP session and make sure we can get on
      try:
        web.xmpp.login(imsi, email, access_token)
      except AuthError:
        web.log.error("Failed to login even after getting the LLAT. Check FB API configs.")
        raise web.Unauthorized()
      except Exception as e:
        web.log.error("OAuth login failed with something bad: %s" % e)
        raise web.InternalError(e)

      # Let the bts know we have activated the user
      try:
        self.send_activation(imsi)
      except Exception as e:
        web.log.error("Couldn't reach base station: %s" % e)
        web.xmpp.logout(imsi) # Cleanup
        raise web.InternalError(e)

      # Save the LLAT and email
      web.db.update(self.config.t_users, where="imsi=$imsi", vars={'imsi': imsi}, oauth=access_token, email=email)

      # We did it!
      raise web.Accepted("Account activated")
#
# Handle stuff coming from basestation
#

""" This class is automatically invoked by the BTS the first time
    the app is run on it.
"""
class bts:
  def __init__(self):
    self.config = web.fb_config

  def POST(self):
    if not self.config.enable_registration:
      raise web.NotFound()

    data = web.input()
    needed_fields = ["callback_url", "cert"]
    web.log.debug("Request to register base station: %s" % data)
    if all(i in data for i in needed_fields):
      callback_url = str(data.callback_url)
      cert = str(data.cert)
      guid = uuid.uuid4()
      web.db.insert(self.config.t_base_stations, key=str(guid), callback_url=callback_url, cert=cert)
      web.log.info("Registered base station: guid=%s, callback_url=%s" % (guid, callback_url))
      resp = {'api_key' : str(guid), 'cert': open(self.config.cert_file).read()}
      raise web.Accepted(json.dumps(resp))
    web.log.debug("Failed to register base station, missing args")
    raise web.BadRequest()

""" This class is invoked the first time a user sends a
    message to the service on the BTS. The entry is stored
    so we know which BTS it came from, and then the user
    must also get the FB OAuth token.
"""
class register(APICommonBase):
  def POST(self):
    web.log.debug("Trying to register %s" % self.data)

    accounts = web.db.select(self.config.t_users, where="imsi=$imsi", \
        vars={"imsi": self.data.imsi})

    # Only one account per IMSI, please.
    if len(list(accounts)):
      web.log.info("Duplicate account for imsi %s on base station %s" % \
                    ( self.data.imsi, self.data.bts_key))
      raise web.Forbidden()

    web.db.insert(self.config.t_users, \
        imsi=self.data.imsi, bts_key=self.data.bts_key)

    web.log.info("Registration suceeded for imsi %s on base station %s" % \
                      ( self.data.imsi, self.data.bts_key))
    raise web.Accepted()


class unsubscribe(APICommonBase):
  def POST(self):
    web.log.debug("Trying to unsubscribe: %s" % self.data)
    web.xmpp.logout(self.data.imsi)
    web.db.delete(self.config.t_users, where="imsi=$imsi", vars={'imsi': self.data.imsi})
    web.log.info("Suceeded to unsubscribe imsi %s" % self.data.imsi)
    raise web.Accepted()

class profile(APICommonBase):
  def POST(self):
    web.log.debug("Trying to get profile: %s" % self.data)
    try:
      result = web.xmpp.get_profile(self.data.imsi)
    except AuthError:
      web.log.info("Failed to get profile. It doesn't look like we are logged on.")
      web.db.update(self.config.t_users, where="imsi=$imsi", vars={'imsi': self.data.imsi}, oauth=None, email=None)
      raise web.Unauthorized()
    except Exception as e:
      web.log.error("Getting profile failed with something bad: %s" % e)
      raise web.InternalError(e)

    raise web.Accepted(json.dumps(result.__dict__))

class find_friend(APICommonBase):
  def POST(self):
    self.fields_to_verify += ["query"]
    web.log.debug("Trying to find_friend %s" % self.data)

    try:
      results = web.xmpp.find_friend(self.data.imsi, self.data.query)
    except AuthError:
      web.log.info("Failed to get user list. It doesn't look like we are logged on.")
      web.db.update(self.config.t_users, where="imsi=$imsi", vars={'imsi': self.data.imsi}, oauth=None, email=None)
      raise web.Unauthorized()
    except Exception as e:
      web.log.error("Finding friend failed with something bad: %s" % e)
      raise web.InternalError(e)

    web.log.debug("Found friends %s" % results)
    raise web.Accepted(json.dumps(results))

class send_message(APICommonBase):
  def POST(self):
    self.fields_to_verify += ["to", "body"]
    web.log.debug("Trying to send_message %s" % self.data)
    try:
      web.xmpp.send_message(self.data.imsi, self.data.to, self.data.body)
    except AuthError:
      web.log.info("Failed to send message. It doesn't look like we are logged on.")
      web.db.update(self.config.t_users, where="imsi=$imsi", vars={'imsi': self.data.imsi}, oauth=None, email=None)
      raise web.Unauthorized()
    except Exception as e:
      web.log.error("Sending message failed with something bad: %s" % e)
      raise web.InternalError(e)
    web.log.info("Success with send_message, imsi=%s, to=%s, msg=%s" % \
            (self.data.imsi, self.data.to, self.data.body))
    raise web.Accepted()



""" Login all users in the event of a restart """
def start():
  web.log.info("Starting up and logging in accounts.")
  accounts = web.db.select(web.fb_config.t_users, where="oauth NOT NULL")
  for account in accounts:
      imsi = account.imsi
      access_token = account.oauth
      email = account.email
      try:
          web.xmpp.login(imsi, email, access_token)
      except AuthError:
          web.db.update(self.config.t_users, where="imsi=$imsi", vars={'imsi': self.data.imsi}, oauth=None, email=None)
      except Exception as e:
          web.log.error("Error while starting: %s" % e)

def stop():
  web.xmpp.shutdown()

if __name__ == "__main__":
    web.config.debug = True
    web.log = logging.getLogger("facebooksms.api")
    conf_file = open("/etc/facebooksms/api.yaml", "r")
    config_dict = yaml.load("".join(conf_file.readlines()))
    web.fb_config = APIConfig(config_dict, web.log)

    logging.basicConfig(filename="%s/api.log" % web.fb_config.log_dir, level=web.fb_config.log_level)

    web.db = web.database(dbn='sqlite', db=web.fb_config.db_file)
    web.db.query("CREATE TABLE IF NOT EXISTS %s " % web.fb_config.t_users  + \
             "(oauth TEXT NULL, email TEXT NULL, imsi TEXT not NULL UNIQUE, bts_key TEXT not NULL)")
    web.db.query("CREATE TABLE IF NOT EXISTS %s " % web.fb_config.t_base_stations + \
             "(key TEXT not NULL UNIQUE, callback_url TEXT, cert TEXT)")

    app = web.application(urls, locals())
    web.sender = APISender(web.db, web.fb_config, web.log)
    web.xmpp = SessionManager(web.sender, web.fb_config)
    start()
    app.run() # Blocking
    stop()
