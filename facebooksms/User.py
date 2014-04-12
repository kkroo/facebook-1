from time import time
from datetime import datetime
from facebooksms import AuthError
class User:
  def __init__(self, app, number):
    self.app = app
    self.fb = app.session_provider(app)

    self.number = None
    self.email = None
    self.registered = None

    self.app.log.debug("Fetching user %s" % number)
    r = self.app.db.execute("SELECT number, email, registered FROM %s WHERE number=?" % self.app.conf.t_users, (number,))
    res = r.fetchall()

    if len(res) == 0:
      self.app.log.error("Tried to init a nonexistent user: %s" % number)

    self.number, self.email, self.registered = res[0]

  def start_session(self):
      self.fb.login()

  def close_session(self):
    if not self.fb.profile is None:
      self.fb.logout()

  """ return True/False"""
  def set_email(self, email=None):
    self.app.log.debug("Setting email for user: %s" % self.number)
    if self.number is None:
      return False

    self.email = email

    try:
      self.app.db.execute("UPDATE %s SET email=? WHERE number=?" % \
            self.app.conf.t_users, (email, self.number))
      self.app.db.commit()
    except Exception as e:
        self.app.log.error("Something bad happened while updating email for user %s: %s" % \
            self.number, e)
        return False

    return True
  """ return True/False"""
  def set_registered(self, registered):
    self.app.log.debug("Setting registered for user: %s" % self.number)
    if self.number is None:
      return False

    self.registered = registered

    try:
      self.app.db.execute("UPDATE %s SET registered=? WHERE number=?" % \
            self.app.conf.t_users, ( 1 if registered else 0, self.number))
      self.app.db.commit()
    except Exception as e:
        self.app.log.error("Something bad happened while updating registered for user %s: %s" % \
            self.number, e)
        return False

    return True

  def delete(self):
    self.app.log.debug("Deleting user: %s" % self.number)
    if self.number is None:
      return

    # if this fails, it will raise an exception but at least will be synced with basestation
    self.fb.unsubscribe()

    self.app.db.execute("DELETE FROM %s WHERE number=?" % self.app.conf.t_users, (self.number, ))
    self.app.db.commit()

  @property
  def number(self):
    return self.number

  @property
  def email(self):
    return self.email

  @property
  def registered(self):
    return self.registered

  @staticmethod
  def register(app, number, email=None):
    if User.is_registered(app, number):
      app.log.error("Trying to register user %s twice." % number)
      return False

    try:
      app.db.execute("INSERT INTO %s(number, email, imsi) VALUES (?,?,?)" % app.conf.t_users, (number, email, app.msg.imsi))
      app.db.commit()
    except Exception as e:
      app.log.error("Error occured while registering user, user already registered %s: %s" % (number, e))
      return False

    return True

  @staticmethod
  def exists(app, number):
    app.log.debug("Checking if user %s exists" % number)
    r = app.db.execute("SELECT number FROM %s WHERE number=?" % app.conf.t_users, (number,))
    res = r.fetchall()
    if len(res) == 0:
      return False
    return True

  @staticmethod
  def is_registered(app, number):
    if User.exists(app, number):
      u = User(app, number)
      return u.registered
    return False

