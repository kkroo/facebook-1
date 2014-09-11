#!/usr/bin/python
import threading
import traceback
import yaml
import web, requests
import logging
import json
import sys, os
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_OAEP
import base64
import urllib
from . import FBOAuthChatSession, Post, FacebookUser

class SessionManager:
  def __init__(self, sender, config):
    self.sessions = threading.local().__dict__
    self.sender = sender
    self.config = config

  """ Create a handler function for incoming chats """
  def _create_message_handler(self, imsi):
    def handler(msg):
      if msg['type'] in ('normal', 'chat'):
        sender_id = str(msg['from']).split('@')[0][1:]
        body = msg['body']
        web.log.debug("Incoming message to_imsi=%s: from=%s, body=%s" % (imsi, sender_id, body))
        vcard = self.sessions[imsi].xmpp.get_vcard(msg['from'])
        sender_name = vcard['vcard_temp']['FN']
        web.log.info("Sending incoming message to API: from=%s, body=%s, to=%s" % \
              (sender_id, body, imsi))
        sender = FacebookUser(sender_id, sender_name)
        self.sender.send_msg(imsi, sender, body)
    return handler

  """
  Public methods
  """
  """ Login to XMPP service. """
  def login(self, imsi, email, access_token):
    if imsi in self.sessions:
        return

    session = FBOAuthChatSession(self.config)
    session.login(email, access_token)
    session.xmpp.add_message_handler(self._create_message_handler(imsi))
    self.sessions[imsi] = session

  def logout(self, imsi):
    if imsi in self.sessions and self.sessions[imsi].logged_in:
      self.sessions[imsi].logout()
      del self.sessions[imsi]

  def send_message(self, imsi, to, body):
    if imsi not in self.sessions and not self.sessions[imsi].logged_in:
       raise AuthError()

    post = Post(None, to, body)
    self.sessions[imsi].post_message(post)

  def get_profile(self, imsi):
    if imsi not in self.sessions and not self.sessions[imsi].logged_in:
       raise AuthError()

    return self.sessions[imsi].profile

  def find_friend(self, imsi, query):
    if imsi not in self.sessions and not self.sessions[imsi].logged_in:
       raise AuthError()

    return [friend.__dict__ for friend in self.sessions[imsi].find_friend(query)]

  def shutdown(self):
    print "Terminating. Loging out of %d accounts." % len(self.sessions)
    web.log.info("Terminating. Loging out of %d accounts." % len(self.sessions))
    for imsi in self.sessions.keys():
      self.logout(imsi)
