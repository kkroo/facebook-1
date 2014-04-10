#!/usr/bin/python
import threading
import traceback
import yaml
import web, requests
from web.wsgiserver import CherryPyWSGIServer
import logging
import syslog
import uuid
import json
from facebooksms import Post, FacebookChatSession, AuthError, Config

urls = ("/register", "register",
        "/login", "login",
        "/send_message", "send_message",
        "/base_station", "base_station")

class base_station:
    def GET(self):
        data = web.input()
        needed_fields = ["callback_url"]
        if all(i in data for i in needed_fields):
            callback_url = str(data.callback_url)
            guid = uuid.uuid4()
            web.db.insert(web.fb_config.t_base_stations, id=str(guid), callback_url=callback_url)
            raise web.Accepted(str(guid))
        raise web.BadRequest()


class login:
    def __init__(self):
        pass

    def POST(self):
        data = web.input()
        needed_fields = ["email", "imsi"]
        if all(i in data for i in needed_fields):
            email = str(data.email)
            imsi =  str(data.imsi)
            syslog.syslog("Trying to login with %s, %s" % ( email, imsi))
            try:
                web.db.update(web.fb_config.t_users, where="email=$email", \
                    vars={"email" : email}, active=1)
                web.AccountManager.auth(email, imsi)
            except AuthError:
              web.AccountManager.remove(email)
              raise web.Unauthorized()
            except Exception as e:
              print "Exception %s" % e
              raise web.InternalError(str(e))
            raise web.Accepted()

        raise web.BadRequest()

class register:
    def __init__(self):
        pass

    def POST(self):
        data = web.input()
        needed_fields = ["email", "password", "imsi", "base_station"]
        if all(i in data for i in needed_fields):
            email = str(data.email)
            password =  str(data.password)
            imsi =  str(data.imsi)
            base_station = str(data.base_station)
            syslog.syslog("Trying to register imsi %s with %s, %s on basestation %s" % \
                ( imsi, email, password, base_station))
            result = web.db.select(web.fb_config.t_base_stations, where="id=$id", vars={'id': base_station})
            if not (result and web.AccountManager.add(email, password, imsi, base_station)):
                raise web.Forbidden()
            raise web.Accepted()
        raise web.BadRequest()

class find_friend:
    def __init__(self):
      pass

    def POST(self):
        data = web.input()
        needed_fields = ["email", "imsi", "query"]
        if all(i in data for i in needed_fields):
            email = str(data.from_email)
            query = str(data.body)
            imsi = str(data.imsi)
            try:
                result = web.AccountManager.find_friend(email, imsi, to)
            except AuthError:
                web.AccountManager.remove(from_email)
                raise web.Unauthorized()
            except Exception as e:
                 raise web.InternalError("%s" % e)
            raise web.Accepted(json.dumps(result))

        raise web.BadRequest()

class send_message:
    def __init__(self):
      pass

    def POST(self):
        data = web.input()
        needed_fields = ["email", "imsi", "to", "body"]
        if all(i in data for i in needed_fields):
            to = str(data.to)
            email = str(data.email)
            body = str(data.body)
            imsi = str(data.imsi)
            try:
                web.AccountManager.send_message(email, imsi, to, body)
            except AuthError:
                web.AccountManager.remove(email)
                raise web.Unauthorized()
            except Exception as e:
                 raise web.InternalError("%s" % e)
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
        sender = str(msg['from']).split('@')[0][1:]
        body = msg['body']
        email = '@'.join(str(msg['to']).split('@')[:2])
        print "From: %s Body: %s, To: %s" % (sender, body, email)
        accounts = web.db.select([web.fb_config.t_users, web.fb_config.t_base_stations], \
            where="email=$email AND active=$active " + \
                  "AND %s.base_station = %s.id" % (web.fb_config.t_users, web.fb_config.t_base_stations), \
            vars={"email": email, "active": 1})
        account = accounts[0]
        r = requests.post(account.callback_url, \
            {'imsi': account.imsi, 'recipient': email, 'sender': sender, 'body': body})

  """ Login to XMPP service. """
  def login(self, email, password):
    if email in self.accounts:
        return

    session = FacebookChatSession()
    session.login(email, password)
    session.xmpp.add_message_handler(self.message_handler)
    self.accounts[email] = session

  """ Login all users in the event of a restart """
  def start(self):
    accounts = web.db.select(web.fb_config.t_users, where="active=$active", vars={"active":1})
    for account in accounts:
        try:
            email = account.email
            password = account.password
            self.login(email, password)
        except AuthError:
            self.remove(email)
        except Exception as e:
            if email in self.accounts:
              self.accounts[email].logout()
              syslog.syslog("Exception raised with %s: %s" % (email, e))

    accounts = web.db.select(web.fb_config.t_users, where="active=$active", vars={"active":0})
    for account in accounts:
        self.remove(account.email)

  """
  Public methods
  """
  def auth(self, email, imsi):
        accounts = web.db.select(web.fb_config.t_users, \
            where="email=$email AND imsi=$imsi AND active=$active", \
            vars={"email": email, "imsi": imsi, "active": 1})
        try:
           password = accounts[0].password
        except Exception:
           raise AuthError()
        self.login(email, password)


  def add(self, email, password, imsi, base_station):
    accounts = web.db.select(web.fb_config.t_users, where="email=$email AND active=1", \
        vars={"email": email})

    if accounts or email in self.accounts:
        return False
    self.remove(email)
    web.db.insert(web.fb_config.t_users, \
        email=email, password=password, imsi=imsi, base_station=base_station)
    return True

  def remove(self, email):
    if email in self.accounts:
      self.accounts[email].logout()
      del self.accounts[email]

    web.db.delete(web.fb_config.t_users, where="email=$email", vars={'email': email})

  def send_message(self, email, imsi, to, body):
      self.auth(email, imsi)
      post = Post(email, to, body)
      self.accounts[email].post_message(post)

  def find_friend(self, email, imsi, query):
      self.auth(email, imsi)
      return [friend.__dict__ for friend in self.accounts[email].find_friend(query)]

if __name__ == "__main__":
    web.config.debug = True
    logging.basicConfig(filename="/var/log/facebooksms.log", level="DEBUG")
    facebooksms_log = logging.getLogger("facebooksms.facebooksms")
    conf_file = open("/etc/facebooksms/facebooksms.yaml", "r")
    config_dict = yaml.load("".join(conf_file.readlines()))
    web.fb_config = Config(config_dict, facebooksms_log)
    web.db = web.database(dbn='sqlite', db='/etc/facebooksms/web_api.sqlite3')
    web.db.query("CREATE TABLE IF NOT EXISTS %s " % web.fb_config.t_users  + \
             "(email TEXT not NULL UNIQUE, password TEXT, imsi TEXT not NULL UNIQUE, base_station TEXT not NULL, active INTEGER DEFAULT 0 )")
    web.db.query("CREATE TABLE IF NOT EXISTS %s " % web.fb_config.t_base_stations + \
             "(id TEXT not NULL UNIQUE, callback_url TEXT)")


    web.AccountManager = AccountManager()
    web.AccountManager.start()

    CherryPyWSGIServer.ssl_certificate = "/etc/facebooksms/ssl_certificate"
    CherryPyWSGIServer.ssl_private_key = "/etc/facebooksms/ssl_private_key"

    app = web.application(urls, locals())
    app.run()
    print web.AccountManager.accounts
    for email, session in web.AccountManager.accounts.items():
        session.logout()
