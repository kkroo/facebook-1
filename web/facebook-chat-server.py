#!/usr/bin/python
import threading
import traceback

import web, requests
from web.wsgiserver import CherryPyWSGIServer

import syslog
import uuid
from facebooksms import Post, FacebookChatSession, AuthError

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
            web.db.insert('basestations', id=str(guid), callback_url=callback_url)
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
                web.db.update('accounts', where="email=$email", \
                    vars={"email" : email}, active=1)
                web.AccountManager.auth(email, imsi)
            except AuthError:
              web.AccountManager.remove(email)
              raise web.Unauthorized()
            except Exception as e:
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
            result = web.db.select('basestations', where="id=$id", vars={'id': base_station})
            if not (result and web.AccountManager.add(email, password, imsi, base_station)):
                raise web.Forbidden()
            raise web.Accepted()
        raise web.BadRequest()

class send_message:
    def __init__(self):
      pass

    def POST(self):
        data = web.input()
        needed_fields = ["from_email", "imsi", "to", "body"]
        if all(i in data for i in needed_fields):
            to = str(data.to)
            from_email = str(data.from_email)
            body = str(data.body)
            imsi = str(data.imsi)
            try:
                web.AccountManager.send_message(from_email, imsi, to, body)
            except AuthError:
                web.AccountManager.remove(from_email)
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
        accounts = web.db.select(['accounts', 'basestations'], \
            where="email=$email AND active=$active " + \
                  "AND accounts.base_station = basestations.id", \
            vars={"email": email, "active": 1})
        account = accounts[0]
        r = requests.post(account.callback_url, \
            {'imsi': account.imsi, 'sender': sender, 'body': body})

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
    accounts = web.db.select('accounts', where="active=$active", vars={"active":1})
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

    accounts = web.db.select('accounts', where="active=$active", vars={"active":0})
    for account in accounts:
        self.remove(account.email)

  """
  Public methods
  """
  def auth(self, email, imsi):
        accounts = web.db.select('accounts', \
            where="email=$email AND imsi=$imsi AND active=$active", \
            vars={"email": email, "imsi": imsi, "active": 1})
        try:
           password = accounts[0].password
        except Exception:
           raise AuthError()
        self.login(email, password)


  def add(self, email, password, imsi, base_station):
    accounts = web.db.select('accounts', where="email=$email AND active=1", \
        vars={"email": email})

    if accounts or email in self.accounts:
        return False
    self.remove(email)
    web.db.insert('accounts', \
        email=email, password=password, imsi=imsi, base_station=base_station)
    return True

  def remove(self, email):
    if email in self.accounts:
      self.accounts[email].logout()
      del self.accounts[email]

    web.db.delete('accounts', where="email=$email", vars={'email': email})

  def send_message(self, from_email, imsi, to, body):
      self.auth(from_email, imsi)
      post = Post(from_email, to, body)
      self.accounts[from_email].post_message(post)



if __name__ == "__main__":
    CherryPyWSGIServer.ssl_certificate = "/etc/facebooksms/ssl_certificate"
    CherryPyWSGIServer.ssl_private_key = "/etc/facebooksms/ssl_private_key"
    web.config.debug = True
    web.db = web.database(dbn='sqlite', db='web_api.sqlite3')
    web.db.query("CREATE TABLE IF NOT EXISTS accounts " \
             "(email TEXT not NULL UNIQUE, password TEXT, imsi TEXT not NULL UNIQUE, base_station TEXT not NULL, active INTEGER DEFAULT 0 )")
    web.db.query("CREATE TABLE IF NOT EXISTS basestations " \
             "(id TEXT not NULL UNIQUE, callback_url TEXT)")


    web.AccountManager = AccountManager()
    web.AccountManager.start()

    app = web.application(urls, locals())
    app.run()
    print web.AccountManager.accounts
    for email, session in web.AccountManager.accounts.items():
        session.logout()
