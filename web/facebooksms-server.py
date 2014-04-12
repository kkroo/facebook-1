#!/usr/bin/python
import threading
import traceback
import yaml
import web, requests
from web.wsgiserver import CherryPyWSGIServer
import logging
import uuid
import json
import sys, os
from facebooksms import Post, FacebookChatSession, AuthError, Config

urls = ("/register", "register",
        "/unsubscribe", "unsubscribe",
        "/login", "login",
        "/send_message", "send_message",
        "/base_station", "base_station",
        "/find_friend",  "find_friend")

class base_station:
    def GET(self):
        data = web.input()
        needed_fields = ["callback_url"]
        web.log.debug("Request to register base station: %s" % data)
        if all(i in data for i in needed_fields):
            callback_url = str(data.callback_url)
            guid = uuid.uuid4()
            web.db.insert(web.fb_config.t_base_stations, id=str(guid), callback_url=callback_url)
            web.log.info("Registered base station: guid=%s, callback_url=%s" % (guid, callback_url))
            raise web.Accepted(str(guid))
        web.log.debug("Failed to register base station, missing args")
        raise web.BadRequest()


class login:
    def __init__(self):
        pass

    def POST(self):
        data = web.input()
        needed_fields = ["imsi"]
        if all(i in data for i in needed_fields):
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
            raise web.Accepted(json.dumps(web.AccountManager[imsi].profile.__dict__))
        web.log.debug("Failed to login, missing args")
        raise web.BadRequest()

class register:
    def __init__(self):
        pass

    def POST(self):
        data = web.input()
        needed_fields = ["email", "password", "imsi", "base_station"]
        web.log.debug("Trying to register %s" % data)
        if all(i in data for i in needed_fields):
            email = str(data.email)
            password =  str(data.password)
            imsi =  str(data.imsi)
            base_station = str(data.base_station)
            result = web.db.select(web.fb_config.t_base_stations, where="id=$id", vars={'id': base_station})
            if not (result and web.AccountManager.add(email, password, imsi, base_station)):
                web.log.info("Registration failed for imsi %s with %s on basestation %s" % \
                              ( imsi, email, base_station))
                raise web.Forbidden()
            web.log.info("Registration suceeded for imsi %s with %s on basestation %s" % \
                              ( imsi, email, base_station))
            raise web.Accepted()
        web.log.debug("Failed to login, missing args")
        raise web.BadRequest()

class unsubscribe:
    def __init__(self):
        pass

    def POST(self):
        data = web.input()
        needed_fields = ["imsi"]
        web.log.debug("Trying to unsubscribe: %s" % data)
        if all(i in data for i in needed_fields):
            imsi =  str(data.imsi)
            result = web.db.select(self.web.fb_config.t_users, where="imsi=$imsi", vars={'imsi': imsi})
            if not (result and web.AccountManager.remove(imsi)):
                web.log.info("Failed to unsubscribe imsi %s, doesn't exist" % imsi)
                raise web.BadRequest()
            web.log.info("Suceeded to unsubscribe imsi %" % imsi)
            raise web.Accepted()
        web.log.debug("Failed to unsubscribe, missing args")
        raise web.BadRequest()

class find_friend:
    def __init__(self):
      pass

    def POST(self):
        data = web.input()
        needed_fields = ["imsi", "query"]
        web.log.debug("Trying to find_friend %s" % data)
        if all(i in data for i in needed_fields):
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

        raise web.BadRequest()

class send_message:
    def __init__(self):
      pass

    def POST(self):
        data = web.input()
        needed_fields = ["imsi", "to", "body"]
        web.log.debug("Trying to send_message %s" % data)
        if all(i in data for i in needed_fields):
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

        raise web.BadRequest()


class AccountManager:

  def __init__(self):
    self.accounts = threading.local().__dict__

  """
  Private methods
  """

  """ Handle incoming chats """
  def message_handler(self, msg):
    if msg['type'] in ('normal', 'chat'):
        sender_id = str(msg['from']).split('@')[0][1:]
        body = msg['body']
        email = '@'.join(str(msg['to']).split('@')[:2])
        web.log.debug("Incoming message: from=%s, body=%s, to=%s" % (sender_id, body, email))
        accounts = web.db.select([web.fb_config.t_users, web.fb_config.t_base_stations], \
            where="email=$email AND active=$active " + \
                  "AND %s.base_station = %s.id" % (web.fb_config.t_users, web.fb_config.t_base_stations), \
            vars={"email": email, "active": 1})
        for account in accounts:
          sender_name = self.accounts[imsi].xmpp.get_vcard(msg['from'])['vcard_temp']['FN']
          web.log.info("Sending incoming message to base station: from=%s, body=%s, to=%s, base_station=%s" % \
              (sender_id, body, email, accounts.base_station))
          r = requests.post(account.callback_url, \
              {'imsi': account.imsi, 'sender_id': sender_id, 'sender_name': sender_name, 'body': body})

  """ Login to XMPP service. """
  def login(self, email, password, imsi):
    if imsi in self.accounts:
        return

    session = FacebookChatSession()
    session.login(email, password)
    session.xmpp.add_message_handler(self.message_handler)
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
           email = accounts[0].email
           password = accounts[0].password
        except Exception:
           raise AuthError()
        self.login(email, password, imsi)


  def add(self, email, password, imsi, base_station):
    accounts = web.db.select(web.fb_config.t_users, where="imsi=$imsi AND active=1", \
        vars={"imsi": imsi})

    if accounts or imsi in self.accounts:
        return False
    self.remove(imsi)
    web.db.insert(web.fb_config.t_users, \
        email=email, password=password, imsi=imsi, base_station=base_station)
    return True

  def remove(self, imsi):
    if imsi in self.accounts:
      self.accounts[imsi].logout()
      del self.accounts[imsi]

    web.db.delete(web.fb_config.t_users, where="imsi=$imsi", vars={'imsi': imsi})

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
    conf_file = open("/etc/facebooksms/facebooksms.yaml", "r")
    config_dict = yaml.load("".join(conf_file.readlines()))
    web.fb_config = Config(config_dict, web.log)
    logging.basicConfig(filename="%s/server.log" % web.fb_config.log_dir, level=web.fb_config.log_level)

    web.db = web.database(dbn='sqlite', db=web.fb_config.api_db_file)
    web.db.query("CREATE TABLE IF NOT EXISTS %s " % web.fb_config.t_users  + \
             "(email TEXT not NULL, password TEXT, imsi TEXT not NULL UNIQUE, base_station TEXT not NULL, active INTEGER DEFAULT 0 )")
    web.db.query("CREATE TABLE IF NOT EXISTS %s " % web.fb_config.t_base_stations + \
             "(id TEXT not NULL UNIQUE, callback_url TEXT)")


    web.AccountManager = AccountManager()
    web.AccountManager.start()

    CherryPyWSGIServer.ssl_certificate = web.fb_config.api_ssl_cert
    CherryPyWSGIServer.ssl_private_key = web.fb_config.api_ssl_key
    app = web.application(urls, locals())
    app.run()
    web.log.info("Terminating. Loging out of %d accounts." % len(web.AccountManager.accounts))
    print web.AccountManager.accounts
    for imsi, session in web.AccountManager.accounts.items():
        session.logout()
