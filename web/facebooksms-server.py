#!/usr/bin/python
import threading
import traceback
import yaml
import web, requests
import logging
import uuid
import json
import sys, os
from facebooksms import Post, FacebookChatSession, AuthError, Config
from Crypto.Cipher import AES
from Crypto import Random
from Crypto.Hash import SHA
from Crypto.Signature import PKCS1_PSS
from Crypto.PublicKey import RSA
from Crypto.Util.asn1 import DerSequence
import base64

urls = ("/register", "register",
        "/unsubscribe", "unsubscribe",
        "/login", "login",
        "/send_message", "send_message",
        "/base_station", "base_station",
        "/find_friend",  "find_friend")

class base_station:
    def POST(self):
        data = web.input()
        needed_fields = ["callback_url", "cert"]
        web.log.debug("Request to register base station: %s" % data)
        if all(i in data for i in needed_fields):
            callback_url = str(data.callback_url)
            cert = str(data.cert)
            guid = uuid.uuid4()
            web.db.insert(web.fb_config.t_base_stations, id=str(guid), callback_url=callback_url, cert=cert)
            web.log.info("Registered base station: guid=%s, callback_url=%s" % (guid, callback_url))
            raise web.Accepted(str(guid))
        web.log.debug("Failed to register base station, missing args")
        raise web.BadRequest()

class api_request:
    def POST(self):
      raise NotImplementedError

    def verify(self, data, fields=list()):
        needed_fields = ["imsi", "base_station", "mac"] + fields
        if all(i in data for i in needed_fields):
            base_station = str(data.base_station)
            imsi =  str(data.imsi)
            mac = str(base64.b64decode(data.mac))
            results = web.db.select(web.fb_config.t_base_stations, \
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

    def _verify_signature(self, data, mac, cert):
        self._verify_cert(cert)
        key = self._cert_to_key(cert)
        h = SHA.new()
        for k,v in sorted(params.items(), key=lambda x: x[0]):
          h.update("%s=%s" % (k, v))
        verifier = PKCS1_PSS.new(key)
        if not verifier.verify(h, mac):
          raise web.Forbidden()

    def _verify_cert(self, cert):
        p1 = Popen(["openssl", "verify", "-CApath", web.fb_config.ca_path, "-crl_check_all"], \
                   stdin = PIPE, stdout = PIPE, stderr = PIPE)

        message, error = p1.communicate(cert)
        if p1.returncode != 0:
          raise web.Forbidden()

    def _cert_to_key(self, cert):
        # Convert from PEM to DER
        lines = cert.replace(" ",'').split()
        der = base64.b64decode(''.join(lines[1:-1]))

        # Extract subjectPublicKeyInfo field from X.509 certificate (see RFC3280)
        cert = DerSequence()
        cert.decode(der)
        tbsCertificate = DerSequence()
        tbsCertificate.decode(cert[0])
        subjectPublicKeyInfo = tbsCertificate[6]

        # Initialize RSA key
        return RSA.importKey(subjectPublicKeyInfo)


class login(api_request):
    def POST(self):
        data = web.input()
        self.verify(data)
        imsi =  str(data.imsi)
        web.log.debug("Request to login: %s" % data)
        try:
            web.db.update(web.fb_config.t_users, where="imsi=$imsi", \
                vars={"imsi" : imsi}, active=1)
            web.AccountManager.auth(imsi)
        except AuthError:
          web.log.info("Login failed for imsi: %s" % imsi)
          web.AccountManager.remove(imsi)
          raise web.Unauthorized()
        except Exception as e:
          exc_type, exc_obj, exc_tb = sys.exc_info()
          fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
          web.log.error("Exception raised with login: %s, type=%s, file=%s, line=%s" % (e, exc_type, fname, exc_tb.tb_lineno))
          raise web.InternalError(str(e))
        web.log.info("Login succeeded for imsi: %s" % imsi)
        raise web.Accepted(json.dumps(web.AccountManager.accounts[imsi].profile.__dict__))

class register(api_request):
    def POST(self):
        data = web.input()
        web.log.debug("Trying to register %s" % data)
        self.verify(data, fields=["email", "password"])
        email = str(data.email)
        password =  str(data.password)
        imsi =  str(data.imsi)
        if not web.AccountManager.add(email, password, imsi, base_station):
            web.log.info("Registration failed for imsi %s with %s on basestation %s" % \
                          ( imsi, email, base_station))
            raise web.Forbidden()
        web.log.info("Registration suceeded for imsi %s with %s on basestation %s" % \
                          ( imsi, email, base_station))
        raise web.Accepted()


class unsubscribe(api_request):
    def POST(self):
        data = web.input()
        web.log.debug("Trying to unsubscribe: %s" % data)
        self.verify(data, fields=["imsi", "base_station"])
        result = web.db.select(web.fb_config.t_users, where="imsi=$imsi", vars={'imsi': imsi})
        if not (result and web.AccountManager.remove(imsi)):
            web.log.info("Failed to unsubscribe imsi %s, doesn't exist" % imsi)
            raise web.BadRequest()
        web.log.info("Suceeded to unsubscribe imsi %s" % imsi)
        raise web.Accepted()

class find_friend(api_request):
    def POST(self):
        data = web.input()
        web.log.debug("Trying to find_friend %s" % data)
        self.verify(data, fields=["query"])
        query = str(data.query)
        imsi = str(data.imsi)

        try:
            result = web.AccountManager.find_friend(imsi, query)
        except AuthError:
            web.log.info("Failed to find_friend for %s, auth failed" % imsi)
            web.AccountManager.remove(imsi)
            raise web.Unauthorized()
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            web.log.error("Exception raised with find_friend: %s, type=%s, file=%s, line=%s" % \
                (e, exc_type, fname, exc_tb.tb_lineno))
            raise web.InternalError(str(e))
        web.log.info("Success with find_friend, imsi=%s, query=%s, num_results=%d" % \
                (imsi, query, len(result)))
        raise web.Accepted(json.dumps(result))

class send_message(api_request):
    def POST(self):
        data = web.input()
        web.log.debug("Trying to send_message %s" % data)
        self.verify(data, fields=["to", "body"])
        to = str(data.to)
        body = str(data.body)
        imsi = str(data.imsi)

        try:
            web.AccountManager.send_message(imsi, to, body)
        except AuthError:
            web.log.info("Failed to send_message for %s, auth failed" % imsi)
            web.AccountManager.remove(imsi)
            raise web.Unauthorized()
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            web.log.error("Exception raised with find_friend: %s, type=%s, file=%s, line=%s" % \
                (e, exc_type, fname, exc_tb.tb_lineno))
            raise web.InternalError(str(e))
        web.log.info("Success with send_message, imsi=%s, to=%s, msg=%s" % \
                (imsi, to, body))
        raise web.Accepted()


class AccountManager:

  def __init__(self):
    self.accounts = threading.local().__dict__
    key_file = open(self.app.config.key_file, 'r')
    self.key = RSA.importKey(key_file.read())

  """
  Private methods
  """

  def _compute_mac(self, params):
    h = SHA.new()
    for k,v in sorted(params.items(), key=lambda x: x[0]):
      h.update("%s=%s" % (k, v))
    signer = PKCS1_PSS.new(self.key)
    return base64.b64encode(signer.sign(h))

  """ Handle incoming chats """
  def create_message_handler(self, imsi):
    def handler(msg):
      if msg['type'] in ('normal', 'chat'):
        sender_id = str(msg['from']).split('@')[0][1:]
        body = msg['body']
        web.log.debug("Incoming message to_imsi=%s: from=%s, body=%s" % (imsi, sender_id, body))
        accounts = web.db.select([web.fb_config.t_users, web.fb_config.t_base_stations], \
            where="active=$active AND imsi=$imsi " + \
              "AND %s.base_station = %s.id" % (web.fb_config.t_users, web.fb_config.t_base_stations), \
            vars={"imsi": imsi, "active": 1})
        account = accounts[0]
        if account:
          vcard = self.accounts[account.imsi].xmpp.get_vcard(msg['from'])
          sender_name = vcard['vcard_temp']['FN']
          web.log.info("Sending incoming message to base station: from=%s, body=%s, to=%s, base_station=%s" % \
              (sender_id, body, imsi, account.base_station))
          params = {'imsi': account.imsi, 'sender_id': sender_id, 'sender_name': sender_name, 'body': body}
          mac = self._compute_mac(params)
          params['mac'] = mac
          r = requests.post(account.callback_url, params)
    return handler

  """ Login to XMPP service. """
  def login(self, email, password, imsi):
    if imsi in self.accounts:
        return

    session = FacebookChatSession()
    session.login(email, password)
    session.xmpp.add_message_handler(self.create_message_handler(imsi))
    self.accounts[imsi] = session

  """ Login all users in the event of a restart """
  def start(self):
    web.log.info("Starting up and logging in accounts.")
    accounts = web.db.select(web.fb_config.t_users, where="active=$active", vars={"active":1})
    for account in accounts:
        try:
            email = account.email
            password = account.password
            imsi = account.imsi
            self.login(email, password, imsi)
        except AuthError:
            web.log.info("AuthError on start for imsi=%s, email=%s. Removing..." % (imsi, email))
            self.remove(imsi)
        except Exception as e:
            if imsi in self.accounts:
              self.accounts[imsi].logout()
              exc_type, exc_obj, exc_tb = sys.exc_info()
              fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
              web.log.error("Exception raised with start: %s, type=%s, file=%s, line=%s" % \
                  (e, exc_type, fname, exc_tb.tb_lineno))


    accounts = web.db.select(web.fb_config.t_users, where="active=$active", vars={"active":0})
    for account in accounts:
        web.log.info("Removing inactive account imsi=%s, email=%s." % (account.imsi, account.email))
        self.remove(account.imsi)

  """
  Public methods
  """
  def auth(self, imsi):
        accounts = web.db.select(web.fb_config.t_users, \
            where="imsi=$imsi AND active=$active", \
            vars={"imsi": imsi, "active": 1})
        try:
           account = accounts[0]
           email = account.email
           password = account.password
           iv = base64.b64decode(account.iv)
        except Exception:
           raise AuthError()

        aes = AES.new(web.fb_config.key, AES.MODE_CBC, iv)
        PADDING = chr(0)
        password = aes.decrypt(base64.b64decode(password)).rstrip(PADDING)

        self.login(email, password, imsi)


  def add(self, email, password, imsi, base_station):
    accounts = web.db.select(web.fb_config.t_users, where="imsi=$imsi AND active=1", \
        vars={"imsi": imsi})

    if accounts or imsi in self.accounts:
        return False

    rand = Random.new()
    iv = rand.read(16)
    aes = AES.new(web.fb_config.key, AES.MODE_CBC, iv)
    BLOCK_SIZE = 32
    PADDING = chr(0)
    password = password + (BLOCK_SIZE - len(password) % BLOCK_SIZE) * PADDING
    password = base64.b64encode(aes.encrypt(password))
    iv = base64.b64encode(iv)

    self.remove(imsi)
    web.db.insert(web.fb_config.t_users, \
        email=email, password=password, imsi=imsi, iv=iv, base_station=base_station)
    return True

  def remove(self, imsi):
    if imsi in self.accounts:
      self.accounts[imsi].logout()
      del self.accounts[imsi]

    return web.db.delete(web.fb_config.t_users, where="imsi=$imsi", vars={'imsi': imsi})


  def send_message(self, imsi, to, body):
      accounts = web.db.select(web.fb_config.t_users, \
            where="imsi=$imsi AND active=$active", \
            vars={"imsi": imsi, "active": 1})

      try:
         email = accounts[0].email
      except Exception:
         raise AuthError()
      self.auth(imsi)
      post = Post(email, to, body)
      self.accounts[imsi].post_message(post)

  def find_friend(self, imsi, query):
      self.auth(imsi)
      return [friend.__dict__ for friend in self.accounts[imsi].find_friend(query)]

if __name__ == "__main__":
    web.config.debug = True
    web.log = logging.getLogger("facebooksms.server")
    conf_file = open("/etc/facebooksms/server.yaml", "r")
    config_dict = yaml.load("".join(conf_file.readlines()))
    web.fb_config = Config(config_dict, web.log)
    logging.basicConfig(filename="%s/server.log" % web.fb_config.log_dir, level=web.fb_config.log_level)

    web.db = web.database(dbn='sqlite', db=web.fb_config.db_file)
    web.db.query("CREATE TABLE IF NOT EXISTS %s " % web.fb_config.t_users  + \
             "(email TEXT not NULL, password TEXT not NULL, iv TEXT not NULL, imsi TEXT not NULL UNIQUE, base_station TEXT not NULL, active INTEGER DEFAULT 0 )")
    web.db.query("CREATE TABLE IF NOT EXISTS %s " % web.fb_config.t_base_stations + \
             "(id TEXT not NULL UNIQUE, callback_url TEXT, cert TEXT)")


    web.AccountManager = AccountManager()
    web.AccountManager.start()

    app = web.application(urls, locals())
    app.run()
    web.log.info("Terminating. Loging out of %d accounts." % len(web.AccountManager.accounts))
    print web.AccountManager.accounts
    for imsi, session in web.AccountManager.accounts.items():
        session.logout()
