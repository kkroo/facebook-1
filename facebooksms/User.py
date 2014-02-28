class User:
  def __init__(self, app, number):
    self.app = app
    self.session = User.session_provider()

    self.number = None
    self.email = None
    self.password = None

    self.log.debug("Fetching user %s" % number)
    r = self.db.execute("SELECT number, email, password FROM %s WHERE number=?" % self.conf.t_users, (number,))
    res = r.fetchall()

    if len(res) == 0:
      self.app.log.error("Tried to init a nonexistent user: %s" % number)

    self.number, self.email, self.password = res[0]


  def start_session(self):
    self.session.login(self.email, self.password)

  """ return True/False"""
  def set_auth(self, email=None, password=None):
    self.app.log.debug("Setting auth for user: %s" % self.number)
    if self.number is None:
      return
    self.app.db.execute("UPDATE OR IGNORE %s SET email=?, password=? WHERE number=?" % self.conf.t_name, (number, email, password, number))
    self.app.db.commit()

  def delete(self):
    raise NotImplementedError

  @property
  def is_active(self):
    if self.email != None and self.password != None:
      try:
        self.start_session()
        return True
      except AuthError:
        return False
    return False

  @property
  def number(self):
    return self.number

  @property
  def email(self):
    return self.email

  @property
  def password(self):
    return self.password

  def register(app, number, email=None, password=None):
    if User.is_registered(number):
      app.log.error("Trying to register user %s twice." % number)
      return False

    try:
      app.db.execute("INSERT INTO %s(number, email, password) VALUES (?,?,?)" % self.conf.t_users, (number, email. password))
      app.db.commit()
    except sqlite3.Error as e:
      app.log.error("Error occured while registering user %s: %s" % (number, e.args[0]))
      return False

    return True

  def exists(app, number):
    app.log.debug("Checking if user %s exists" % number)
    r = app.db.execute("SELECT number FROM %s WHERE number=?" % self.conf.t_users, (number,))
    res = r.fetchall()
    if len(res) == 0:
      return False
    return True

  def is_registered(app, number):
    if User.exists(app, number):
      u = User(app, number)
      return u.is_active
    return False

