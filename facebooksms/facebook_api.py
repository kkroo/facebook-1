import logging
from time import time

class AuthError(Exception):
  pass

class FacebookSessionProvider:
  """ This class is in interface to the Facebook Graph for a particular user"""
  def login(self, email, password):
    """ Log the user in and cache the session
      This method can throw a whole bunch of exceptions, be ready to catch them """
    raise NotImplementedError
  def logout(self):
    raise NotImplementedError
  def get_friend_list(self):
    raise NotImplementedError
  def find_friend(self, name_query):
    raise NotImplementedError
  def get_home_feed_posts(self, earliest_timestamp):
    raise NotImplementedError
  def get_messages(self, earliest_timestamp):
    raise NotImplementedError
  def post_status(self, post):
    raise NotImplementedError
  def post_message(self, post):
    raise NotImplementedError
  @property
  def profile(self):
    """ Returns an instance of type FacebookUser"""
    raise NotImplementedError

class FacebookTestSession(FacebookSessionProvider):
  """ This is a slug test class for the Facebook Session Provider"""
  def __init__(self):
    self.profile = None
    self.logger = logging.getLogger("testsession")

  def login(self, email, password):
    """ Log the user in and cache the session
      This method can throw a whole bunch of exceptions, be ready to catch them """
    if password != "password":
      raise AuthError()

    psuedo_id = abs(hash(email)) % 10000
    psuedo_name = email.split('@')[0]
    self.profile = FacebookUser(psuedo_id, psuedo_name)
    self.friends = [FacebookUser(123, "Omar Ramadan"), FacebookUser(124, "John Doe") ]

  def get_friend_list(self):
    return self.friends

  def find_friend(self, name_query):
    query = name_query.lower().strip()
    results = filter(lambda user: query in user.name.lower(), self.get_friend_list())
    self.logger.info("Friends matching query %s: %d/%d" % \
        (query, len(results), len(self.get_friend_list())))
    return results

  def get_home_feed_posts(self, earliest_timestamp):
    return [Post(self.friends[1], self.friends[1].facebook_id, "It's a beautiful day.", 1234, time() - 1000),
            Post(self.friends[0], self.friends[0].facebook_id, "Here is a status update.", 567, time()) ]

  def get_messages(self, earliest_timestamp):
    return [Post(self.friends[1], self.profile.facebook_id, "Congrats you got a PM!", 3456, time())]

  def post_status(self, post):
    self.logger.info("Posting status %s" % post)

  def post_message(self, post):
    self.logger.info("Posting message %s" % post)

  @property
  def profile(self):
    return self.profile

class FacebookUser:
  def __init__(self, facebook_id, name):
    self.id = facebook_id
    self.name = name

  @property
  def facebook_id(self):
    return str(self.id)

  def __str__(self):
    return '%s (#%d)' % (self.name, self.facebook_id)

class Post:
  def __init__(self, sender, recipient_id, body, post_id=None, timestamp=None):
    self.post_id = post_id
    self.sender = sender
    self.recipient = recipient_id
    self.timestamp = timestamp if timestamp else time()
    self.body = body

  def is_valid(self):
    if not isinstance(self.sender, FacebookUser) or not isinstance(self.recipient, FacebookUser):
      raise ValueError("Expecting sender and recepient to be of type FacebookUser")

    return self.sender and self.recipient and self.timestamp and self.body

  def is_posted(self):
    return self.post_id != None

  def __str__(self):
    return "from='%s' to='%s' timestamp='%d' msg='%s'" % (self.sender,
                                                          self.recipient,
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
