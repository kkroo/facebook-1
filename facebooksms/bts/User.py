from time import time
from datetime import datetime
from facebooksms import AuthError
class User:
  def __init__(self, app, number):
    self.app = app
    self.fb = app.session_provider(app)

    self.number = number
    self.registered = None
    self.active = None

    self.app.log.debug("Fetching user %s" % number)
    r = self.app.db.execute("SELECT registered, active FROM %s WHERE number=?" % self.app.conf.t_users, (number,))
    res = r.fetchall()

    if len(res) == 0:
      self.app.log.error("Tried to init a nonexistent user: %s" % number)
      raise Exception("User %s does not exist" % number)

    self.registered, self.active = res[0]

  @staticmethod
  def register(app, number):
    app.log.debug("Trying to register user %s" % number)
    try:
      app.db.execute("INSERT INTO %s(number, imsi) VALUES (?,?)" % app.conf.t_users, (number, app.msg.imsi))
      app.db.commit()
    except Exception as e:
      app.log.error("Error occured in DB while registering user %s: %s" % (number, e))
      raise Exception("Error occured while saving user to DB: %s" % e)

    user = User(app, number)
    return user


  @staticmethod
  def exists(app, imsi):
    app.log.debug("Checking if user %s exists" % imsi)
    r = app.db.execute("SELECT number FROM %s WHERE imsi=?" % app.conf.t_users, (imsi,))
    res = r.fetchall()
    if len(res) == 0:
      return False
    return True

  def delete(self):
    self.app.log.debug("Deleting user: %s" % self.number)

    # if this fails, it will raise an exception so it won't proceed and will be synced with the BTS tables
    self.fb.unsubscribe()

    self.app.db.execute("DELETE FROM %s WHERE number=?" % self.app.conf.t_users, (self.number, ))
    self.app.db.commit()

  @property
  def number(self):
    return self.number

  @property
  def registered(self):
    return self.registered

  @property
  def active(self):
    return self.active

  def _db_set_bool(self, name, value):
    """ Set a boolean in the user's row
    """
    try:
      self.app.db.execute("UPDATE %s SET %s=? WHERE number=?" % \
            (self.app.conf.t_users, name), ( 1 if value else 0, self.number))
      self.app.db.commit()
    except Exception as e:
        self.app.log.error("Something bad happened while updating %s for user %s: %s" % \
            name, self.number, e)
        raise Exception("Error occured while updating bool to DB")

  def set_active(self, status):
    self.app.log.debug("Setting active for user: %s" % self.number)
    self.active = status
    self._db_set_bool("active", status)

  def set_registered(self, status):
    self.app.log.debug("Setting registered for user: %s" % self.number)
    self.registered = status
    self._db_set_bool("registered", status)
