#!/usr/bin/python
import threading
import traceback
import yaml
import web, requests
import logging
import json
import sys, os
from facebooksms import Post, FacebookChatSession, AuthError, Config
from facebooksms.WebCommon import WebCommonBase
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP
import base64
import urllib

urls = ("/unsubscribe", "unsubscribe",
        "/login", "login",
        "/logout", "logout",
        "/send_message", "send_message",
        "/find_friend",  "find_friend")

class XMPPServerCommonBase(WebCommonBase):
    def __init__(self):
      self.config = web.fb_config
      self.api_cert = open(self.config.api_cert_file).read()

    def GET(self):
      self.POST()

    # If for some reason we lose Auth, reauth with API. Unless request is login..
    def POST(self):
      try:
        self.request()
      except web.Unauthorized:
        data = web.input()
        imsi = str(data.imsi)
        params = {'imsi': imsi}
        params['mac'] = WebCommonBase.compute_mac(params, self.key)
        #web.log.debug("%s?%s" % ("%s/reauth" % web.fb_config.api_url, "&".join(["%s=%s" % (k,urllib.quote(v)) for k,v in params.items()])))
        requests.post("%s/reauth" % web.fb_config.api_url, params, verify=False) # XXX THIS IS INSECURE!!!
        self.request()

    def request(self):
      raise NotImplementedError

    def _verify_channel(self, data):
        #Verify MAC
        params = dict(data)
        del params['mac']
        mac = base64.b64decode(str(data.mac))
        self._verify_signature(params, mac, self.api_cert)

    @property
    def key(self):
      key_file = open(web.fb_config.key_file, 'r')
      key = RSA.importKey(key_file.read())
      key_file.close()
      return key


class login(XMPPServerCommonBase):
    def POST(self):
        data = web.input()
        self.verify(data, ['email', 'password'])
        imsi =  str(data.imsi)
        email = str(data.email)
        password_ciphertext = str(data.password)


        cipher = PKCS1_OAEP.new(self.key)
        password = cipher.decrypt(base64.b64decode(password_ciphertext))
        web.log.debug("Request to login: %s" % data)
        try:
            web.AccountManager.login(email, password, imsi)
        except AuthError:
          web.log.info("Login failed for imsi: %s" % imsi)
          web.AccountManager.remove(imsi)
          raise web.Unauthorized()
        except Exception as e:
          exc_type, exc_obj, exc_tb = sys.exc_info()
          fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
          web.log.error("Exception raised with login: %s, type=%s, file=%s, line=%s" % (e, exc_type, fname, exc_tb.tb_lineno))
          web.AccountManager.remove(imsi)
          raise web.InternalError(str(e))
        web.log.info("Login succeeded for imsi: %s" % imsi)
        raise web.Accepted(json.dumps(web.AccountManager.accounts[imsi].profile.__dict__))

class logout(XMPPServerCommonBase):
    def request(self):
        data = web.input()
        web.log.debug("Trying to logout: %s" % data)
        self.verify(data)
        if not web.AccountManager.remove(imsi):
            web.log.info("Failed to logout imsi %s, doesn't exist" % imsi)
            raise web.BadRequest()
        web.log.info("Suceeded to logout imsi %s" % imsi)
        raise web.Accepted()

class find_friend(XMPPServerCommonBase):
    def request(self):
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
            web.AccountManager.remove(imsi)
            raise web.InternalError(str(e))
        web.log.info("Success with find_friend, imsi=%s, query=%s, num_results=%d" % \
                (imsi, query, len(result)))
        raise web.Accepted(json.dumps(result))

class send_message(XMPPServerCommonBase):
    def request(self):
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
            web.AccountManager.remove(imsi)
            raise web.InternalError(str(e))
        web.log.info("Success with send_message, imsi=%s, to=%s, msg=%s" % \
                (imsi, to, body))
        raise web.Accepted()

class AccountManager:

  def __init__(self):
    self.accounts = threading.local().__dict__

  """
  Private methods
  """

  """ Handle incoming chats """
  def create_message_handler(self, imsi):
    def handler(msg):
      if msg['type'] in ('normal', 'chat'):
        sender_id = str(msg['from']).split('@')[0][1:]
        body = msg['body']
        web.log.debug("Incoming message to_imsi=%s: from=%s, body=%s" % (imsi, sender_id, body))
        vcard = self.accounts[imsi].xmpp.get_vcard(msg['from'])
        sender_name = vcard['vcard_temp']['FN']
        web.log.info("Sending incoming message to API: from=%s, body=%s, to=%s" % \
              (sender_id, body, imsi))
        params = {'imsi': imsi, 'sender_id': sender_id, 'sender_name': sender_name, 'body': body}
        params['mac'] = XMPPServerCommonBase.compute_mac(params, self.key)
        requests.post("%s/message_handler" % web.fb_config.api_url, params, verify=False) # XXX THIS IS INSECURE!!!

    return handler

  def auth(self, imsi):
    if imsi in self.accounts:
      return True
      # TODO Need a better way to ensure XMPP connectivity
      # if self.accounts[imsi].xmpp.state.ensure('connected'):
      #   return True
    return False

  """
  Public methods
  """
  """ Login to XMPP service. """
  def login(self, email, password, imsi):
    if self.auth(imsi):
        return
    else:
        self.remove(imsi)

    session = FacebookChatSession()
    session.login(email, password)
    session.xmpp.add_message_handler(self.create_message_handler(imsi))
    self.accounts[imsi] = session

  def remove(self, imsi):
    if imsi in self.accounts:
      self.accounts[imsi].logout()
      del self.accounts[imsi]
      return True
    else:
      return False


  def send_message(self, imsi, to, body):
      if not self.auth(imsi):
         raise AuthError()

      post = Post(None, to, body)
      self.accounts[imsi].post_message(post)

  def find_friend(self, imsi, query):
      if not self.auth(imsi):
         raise AuthError()

      return [friend.__dict__ for friend in self.accounts[imsi].find_friend(query)]

  @property
  def key(self):
      key_file = open(web.fb_config.key_file, 'r')
      key = RSA.importKey(key_file.read())
      key_file.close()
      return key

if __name__ == "__main__":
    web.config.debug = True
    web.log = logging.getLogger("facebooksms.xmpp")
    conf_file = open("/etc/facebooksms/xmpp.yaml", "r")
    config_dict = yaml.load("".join(conf_file.readlines()))
    web.fb_config = Config(config_dict, web.log)
    logging.basicConfig(filename="%s/xmpp.log" % web.fb_config.log_dir, level=web.fb_config.log_level)

    web.AccountManager = AccountManager()

    app = web.application(urls, locals())
    app.run()
    web.log.info("Terminating. Loging out of %d accounts." % len(web.AccountManager.accounts))
    print web.AccountManager.accounts
    for imsi, session in web.AccountManager.accounts.items():
        session.logout()

