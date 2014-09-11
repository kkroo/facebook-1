import logging
import json
from time import time

class AuthError(Exception):
  pass

class ConnectionError(Exception):
  pass

class FacebookSessionProvider:
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
  def post_message(self, post):
    raise NotImplementedError
  @property
  def logged_in(self):
    raise NotImplementedError
  @property
  def profile(self):
    """ Returns an instance of type FacebookUser"""
    raise NotImplementedError

class FacebookUser(object):
  def __init__(self, facebook_id, name):
    self.facebook_id = str(facebook_id)
    self.name = name

  def __str__(self):
    return '%s (#%s)' % (self.name, self.facebook_id)

class Post:
  def __init__(self, sender, recipient, body, post_id=None, timestamp=None):
    self.post_id = post_id
    self.sender = sender
    self.recipient = recipient
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

