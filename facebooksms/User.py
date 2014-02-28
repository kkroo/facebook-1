class User:
  def __init__(self, app, number):
    self.app = app
    self.session = User.session_provider()
    if not User.is_registered(number):
      raise Exception("User is not registered")

    self.number = number

  def start_session(self):
    self.session.login(self.email, self.password)

  def deactivate(self):
    raise NotImplementedError

  def delete(self):
    raise NotImplementedError

  @property
  def active(self):
    raise NotImplementedError

  @property
  def email(self):
    raise NotImplementedError

  @property
  def password(self):
    raise NotImplementedError

  def register(number, email, password):
    if User.is_registered(number):
      raise Exception("User already registered")
    user = User(number)
    user.set_auth(email, password)

  def is_registered(number):
    raise NotImplementedError

