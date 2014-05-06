#!/usr/bin/python
import threading
import traceback
import yaml
import web, requests
import logging
import uuid
import json
import sys, os
from facebooksms import Post, AuthError, Config
from facebooksms.WebCommon import WebCommonBase
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP
import base64

urls = ("/message_handler", "message_handler",
        "/reauth", "reauth",
        "/register", "register",
        "/unsubscribe", "unsubscribe",
        "/login", "login",
        "/send_message", "send_message",
        "/find_friend",  "find_friend",
        "/base_station", "base_station")


#
# Handle stuff coming from basestation
#

# Register a base station
class base_station:
    def __init__(self):
      self.config = web.fb_config

    def POST(self):
        if not web.fb_config.enable_registration:
          raise web.NotFound()

        data = web.input()
        needed_fields = ["callback_url", "cert"]
        web.log.debug("Request to register base station: %s" % data)
        if all(i in data for i in needed_fields):
            callback_url = str(data.callback_url)
            cert = str(data.cert)
            guid = uuid.uuid4()
            web.db.insert(self.config.t_base_stations, id=str(guid), callback_url=callback_url, cert=cert)
            web.log.info("Registered base station: guid=%s, callback_url=%s" % (guid, callback_url))
            resp = {'api_key' : str(guid), 'cert': open(self.config.cert_file).read()}
            raise web.Accepted(json.dumps(resp))
        web.log.debug("Failed to register base station, missing args")
        raise web.BadRequest()

class APICommonBase(WebCommonBase):
    def __init__(self):
      self.config = web.fb_config

    def _verify_channel(self, data):
        if "base_station" in data:
            base_station = str(data.base_station)
            mac = base64.b64decode(str(data.mac))
            results = web.db.select(self.config.t_base_stations, \
                where="id=$id", vars={'id': base_station})
            try:
                result = results[0]
            except Exception:
              web.log.info("Unauthorized basestation %s" % \
                            ( base_station))
              raise web.Forbidden()

            #Verify MAC
            params = dict(data)
            del params['mac']
            self._verify_signature(params, mac, result.cert)
        else:
          web.log.debug("Failed request, missing args")
          raise web.BadRequest()

    def xmpp_request(self, module, params):
      try:
          params['mac'] = WebCommonBase.compute_mac(params, self.key)
          request_url = "%s/%s" % (self.config.api_url, module)
          web.log.debug("Making request to %s with args %s" % (request_url, params))
          r = requests.post(request_url, data=params, verify=False) # XXX THIS IS INSECURE!!!
      except Exception as e:
          web.log.error("FB API server error %s" % e)
          raise web.InternalError(str(e))
      web.log.debug("Response: %s, %d" % (r, r.status_code))
      if r.status_code == 401:
          web.log.debug("FB XMPP server auth error for user")
          raise web.Unauthorized()
      elif r.status_code == 500:
          web.log.error("FB XMPP server internal error %s" % r.text)
          raise web.InternalError(r.text)
      elif r.status_code == 400:
          web.log.error("FB XMPP server bad request error %s" % r.text)
          raise web.BadRequest()

      return r

    @property
    def key(self):
      key_file = open(web.fb_config.key_file, 'r')
      key = RSA.importKey(key_file.read())
      key_file.close()
      return key


class login(APICommonBase):
    def POST(self):
        data = web.input()
        self.verify(data)
        imsi =  str(data.imsi)
        web.log.debug("Request to login: %s" % data)
        accounts = web.db.select(self.config.t_users, \
            where="imsi=$imsi", vars={"imsi": imsi})
        try:
           account = accounts[0]
           email = account.email
           password = account.password
        except Exception:
           raise web.Unauthorized()

        params = {'email': email, 'password': password, 'imsi': imsi}
        try:
            r = self.xmpp_request('login', params)
            raise web.Accepted(r.text)
        except web.Unauthorized as e:
            web.db.delete(web.fb_config.t_users, where="imsi=$imsi", vars={'imsi': imsi})
            raise e



class register(APICommonBase):
    def POST(self):
        data = web.input()
        web.log.debug("Trying to register %s" % data)
        self.verify(data, fields=["email", "password"])
        email = str(data.email)
        password =  str(data.password)
        imsi =  str(data.imsi)
        base_station =  str(data.base_station)

        accounts = web.db.select(self.config.t_users, where="imsi=$imsi", \
            vars={"imsi": imsi})

        if accounts:
            web.log.info("Registration failed for imsi %s with %s on basestation %s" % \
                          ( imsi, email, base_station))
            raise web.Forbidden()

        xmpp_cert = open(self.config.api_cert_file).read()
        if not self._verify_cert(xmpp_cert):
          web.log.error("XMPP Server cert is bad folks!")
          raise web.InternalError("Bad XMPP server cert!")

        xmpp_pubkey = self._cert_to_key(xmpp_cert)
        cipher = PKCS1_OAEP.new(xmpp_pubkey)
        password_ciphertext = base64.b64encode(cipher.encrypt(password))

        # Cleanup first unverified accounts for this IMSI
        web.db.delete(web.fb_config.t_users, where="imsi=$imsi", vars={'imsi': imsi})

        web.db.insert(web.fb_config.t_users, \
            email=email, password=password_ciphertext, imsi=imsi, base_station=base_station)

        web.log.info("Registration suceeded for imsi %s with %s on basestation %s" % \
                          ( imsi, email, base_station))
        raise web.Accepted()


class unsubscribe(APICommonBase):
    def POST(self):
        data = web.input()
        web.log.debug("Trying to unsubscribe: %s" % data)
        self.verify(data)
        imsi = str(data.imsi)

        result = web.db.select(self.config.t_users, where="imsi=$imsi", vars={'imsi': imsi})
        if not result:
            web.log.info("Failed to unsubscribe imsi %s, doesn't exist" % imsi)
            raise web.BadRequest()
        web.db.delete(web.fb_config.t_users, where="imsi=$imsi", vars={'imsi': imsi})
        self.xmpp_request('logout', {'imsi': imsi})
        web.log.info("Suceeded to unsubscribe imsi %s" % imsi)
        raise web.Accepted()

class find_friend(APICommonBase):
    def POST(self):
        data = web.input()
        web.log.debug("Trying to find_friend %s" % data)
        self.verify(data, fields=["query"])
        query = str(data.query)
        imsi = str(data.imsi)

        r = self.xmpp_request('find_friend', {'query': query, 'imsi': imsi})
        web.log.info("Success with find_friend, imsi=%s, query=%s" % (imsi, query))
        raise web.Accepted(r.text)

class send_message(APICommonBase):
    def POST(self):
        data = web.input()
        web.log.debug("Trying to send_message %s" % data)
        self.verify(data, fields=["to", "body"])
        to = str(data.to)
        body = str(data.body)
        imsi = str(data.imsi)

        self.xmpp_request('send_message', {'to': to, 'body': body, 'imsi': imsi})
        web.log.info("Success with send_message, imsi=%s, to=%s, msg=%s" % \
                (imsi, to, body))
        raise web.Accepted()



""" Login all users in the event of a restart """
def start():
  web.log.info("Starting up and logging in accounts.")
  accounts = web.db.select(web.fb_config.t_users)
  request_obj = APICommonBase()
  for account in accounts:
      imsi = account.imsi
      email = account.email
      password = account.password
      try:
          params = {'email': email, 'password': password, 'imsi': imsi}
          r = request_obj.xmpp_request('login', params)
      except web.Unauthorized as e:
          web.db.delete(web.fb_config.t_users, where="imsi=$imsi", vars={'imsi': imsi})
      except Exception as e:
          web.log.error("Error while starting: %s" % e)

#
# Handle stuff coming from XMPP server
#

class reauth(APICommonBase):
    def _verify_channel(self, data):
      return WebCommonBase._verify_channel(self, data)

    def POST(self):
        data = web.input()
        web.log.debug("Incoming XMPP reauth request %s" % data)
        self.verify(data)

        imsi = str(data.imsi)
        web.log.debug("Reauth for login: %s" % data)
        accounts = web.db.select(self.config.t_users, \
            where="imsi=$imsi", vars={"imsi": imsi})
        try:
           account = accounts[0]
           email = account.email
           password = account.password
        except Exception:
           raise web.Unauthorized()

        params = {'email': email, 'password': password, 'imsi': imsi}
        try:
            r = self.xmpp_request('login', params)
            raise web.Accepted(r.text)
        except web.Unauthorized as e:
            web.db.delete(web.fb_config.t_users, where="imsi=$imsi", vars={'imsi': imsi})
            raise e

class message_handler(APICommonBase):
    def _verify_channel(self, data):
      return WebCommonBase._verify_channel(self, data)

    def POST(self):
        data = web.input()
        web.log.debug("Incoming XMPP messsage %s" % data)
        self.verify(data, fields=["sender_id", "sender_name", "body"])

        sender_id = str(data.sender_id)
        sender_name = str(data.sender_name)
        body = str(data.body)
        imsi = str(data.imsi)

        accounts = web.db.select([self.config.t_users, self.config.t_base_stations], \
            where="imsi=$imsi " + \
              "AND %s.base_station = %s.id" % (self.config.t_users, self.config.t_base_stations), \
            vars={"imsi": imsi})
        account = accounts[0]
        if account:
          web.log.info("Sending incoming message to base station: from=%s, body=%s, to=%s, base_station=%s, url=%s" % \
              (sender_id, body, imsi, account.base_station, account.callback_url))
          params = {'imsi': account.imsi, 'sender_id': sender_id, 'sender_name': sender_name, 'body': body}
          params['mac'] = WebCommonBase.compute_mac(params, self.key)
          r = requests.post(account.callback_url, params, verify=False) # XXX THIS IS INSECURE!!!
          raise web.Accepted()
        raise web.Unauthorized()

if __name__ == "__main__":
    web.config.debug = True
    web.log = logging.getLogger("facebooksms.api")
    conf_file = open("/etc/facebooksms/api.yaml", "r")
    config_dict = yaml.load("".join(conf_file.readlines()))
    web.fb_config = Config(config_dict, web.log)
    logging.basicConfig(filename="%s/api.log" % web.fb_config.log_dir, level=web.fb_config.log_level)

    web.db = web.database(dbn='sqlite', db=web.fb_config.db_file)
    web.db.query("CREATE TABLE IF NOT EXISTS %s " % web.fb_config.t_users  + \
             "(email TEXT not NULL, password TEXT not NULL, imsi TEXT not NULL UNIQUE, base_station TEXT not NULL)")
    web.db.query("CREATE TABLE IF NOT EXISTS %s " % web.fb_config.t_base_stations + \
             "(id TEXT not NULL UNIQUE, callback_url TEXT, cert TEXT)")

    app = web.application(urls, locals())
    start()
    app.run()
