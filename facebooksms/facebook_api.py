class AuthError(Exception):
  pass

class FacebookSession:
  """ This class is in interface to the Facebook Graph for a particular user"""
  def __init__(self):
    self.authenticated = False
#    self.profile = FacebookUser()

  def login(self, email, password):
    """ Log the user in and cache the session
      This method can throw a whole bunch of exceptions, be ready to catch them """
    raise NotImplementedError
  def get_friend_list(self):
    raise NotImplementedError
  def find_friend(self, name):
    raise NotImplementedError
  def get_home_feed_posts(self):
    raise NotImplementedError
  def get_timeline_posts(self):
    raise NotImplementedError
  def get_private_messages(self):
    raise NotImplementedError
  def get_post(self, post_id):
    raise NotImplementedError
  def push_post(self, post):
    raise NotImplementedError

class FacebookUser:
  def __init__(self, facebook_id, name):
    self.facebook_id = facebook_id
    self.name = name

  def get_number(self):
    raise NotImplementedError

  def __str__(self):
    return '%s (#%d)' % (self.name, self.facebook_id)

class Post:
  def __init__(self, sender, recepient, body, post_id=None, timestamp=None):
    self.post_id = post_id
    self.sender = sender
    self.recepient = recepient
    self.timestamp = timestamp if timestamp else time.gmtime(0)
    self.body = body

  def is_valid(self):
    return self.sender and self.recepient and self.timestamp and self.body

  def is_posted(self):
    return self.post_id != None

  def __str__(self):
    return "from='%s' to='%s' timestamp='%d' msg='%s'" % (self.sender,
                                                          self.recepient,
                                                          self.timestamp,
                                                          self.body)

"""import mechanize

class ScaperSession(FacebookSession):
    def __init__(self):
      mechanize.UserAgent = 'Nokia0/2.0 (3.10) Profile/MIDP-2.0 Configuration/CLDC-1.1'
      self.br = mechanize.Browser()

    def login(self, email, password):
      self.br.open('https://facebook.com')
      self.br.select_form(name="login_form")
      self.br["email"] = email
      self.br["pass"] = password
      response = self.br.submit()
      print response


    def getAccessToken(self):
      pass

fb = FacebookSession()
fb.login("email@domain.edu", "pass") """
