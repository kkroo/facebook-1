from time import time
from datetime import datetime
from facebooksms import AuthError
class User:
  def __init__(self, app, number):
    self.app = app
    self.fb = app.session_provider()

    self.number = None
    self.email = None
    self.password = None

    self.app.log.debug("Fetching user %s" % number)
    r = self.app.db.execute("SELECT number, email, password FROM %s WHERE number=?" % self.app.conf.t_users, (number,))
    res = r.fetchall()

    if len(res) == 0:
      self.app.log.error("Tried to init a nonexistent user: %s" % number)

    self.number, self.email, self.password = res[0]

  def start_session(self):
      self.fb.login(self.email, self.password)

  def close_session(self):
    if not self.fb.profile is None:
      self.fb.logout()

  """ return True/False"""
  def set_auth(self, email=None, password=None):
    self.app.log.debug("Setting auth for user: %s" % self.number)
    if self.number is None:
      return False

    self.email = email
    self.password = password

    try:
      self.app.db.execute("UPDATE %s SET email=?, password=? WHERE number=?" % \
            self.app.conf.t_users, (email, password, self.number))
      self.app.db.commit()
    except Exception as e:
        self.app.log.error("Something bad happened while updating auth for user %s: %s" % \
            self.number, e)
        return False

    return True

  def update_last_fetch(self):
    self.app.log.debug("Setting last fetch for user: %s" % self.number)
    if self.number is None:
      return
    self.app.db.execute("UPDATE OR IGNORE %s SET last_fetch =? WHERE number=?" % self.app.conf.t_users, (datetime.utcnow(), self.number))
    self.app.db.commit()



  def delete(self):
    self.app.log.debug("Deleting user: %s" % self.number)
    if self.number is None:
      return
    self.app.db.execute("DELETE FROM %s WHERE number=?" % self.app.conf.t_users, (self.number, ))
    self.app.db.commit()

  @property
  def is_active(self):
    return self.email != None and self.password != None

  @property
  def number(self):
    return self.number

  @property
  def email(self):
    return self.email

  @property
  def password(self):
    return self.password

  @staticmethod
  def register(app, number, email=None, password=None):
    if User.is_registered(app, number):
      app.log.error("Trying to register user %s twice." % number)
      return False

    try:
      app.db.execute("INSERT INTO %s(number, email, password, last_fetch) VALUES (?,?,?,?)" % app.conf.t_users, (number, email, password, datetime.utcnow()))
      app.db.commit()
    except Exception as e:
      app.log.error("Error occured while registering user %s: %s" % (number, e))
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
      return u.is_active
    return False

