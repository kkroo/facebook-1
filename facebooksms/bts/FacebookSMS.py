from . import *
import time, datetime
import re
import requests
import yaml
import json

class FacebookSMS:
  def __init__(self, conf):
    self.msg = None
    self.user = None
    self.conf = conf
    self.db = conf.db_conn
    self.cmd_handler = CommandHandler(self)
    self.session_provider = self._init_session_provider(self.conf.provider_type)
    self.msg_sender = self._init_sender(self.conf.sender_type)
    self.log = self.conf.log
    self._init_db()
    self.log.debug("Init done.")

  def _init_session_provider(self, provider_type):
      if provider_type == "api":
          return FacebookAPIClient
      raise ValueError("No FB session provider of type '%s' exists." % provider_type)


  def _init_sender(self, sender_type):
      """ Returns a Sender object according to the specified sender type.
      Currently, we support two types of Sender:
          - "log": Write the sent SMS messages to a log file
          - "test": Write the sent SMS messages to an easy-to-parse log
      """
      if sender_type == "log":
          return LogSender()
      if sender_type == "test":
          return TestSender()
      if sender_type == "esl":
          return ESLSender()
      if sender_type == "freeswitch":
          return FreeSwitchSender()
      raise ValueError("No sender of type '%s' exists." % sender_type)

  def _init_db(self, purge=False):
      if purge:
          self.db.execute("BEGIN TRANSACTION")
          tables = [self.conf.t_users]
          for t in tables:
              self.db.execute("DROP TABLE %s" % t)
          self.db.commit()

      self.db.execute("CREATE TABLE IF NOT EXISTS %s " % self.conf.t_users + \
          "(number TEXT not NULL UNIQUE ON CONFLICT IGNORE, " + \
          "imsi TEXT not NULL UNIQUE ON CONFLICT IGNORE, " + \
          "registered INTEGER DEFAULT 0, active INTEGER DEFAULT 0 )" )
      self.db.commit()

  def handle_incoming_message(self, post):
    """ This handles incoming Facebook messages from the API callback and
        routes them accordingly
    """
    r = self.db.execute("SELECT number FROM %s " % (self.conf.t_users,) + \
          "WHERE imsi = ? AND registered = 1 LIMIT 1", (post.recipient,))

    res = r.fetchall()
    if len(res) == 1:
        m = Message(self.id_to_number(post.sender.facebook_id), res[0][0], post.sender.name, post.body)
        self.send(m)
    else:
        self.log.error("Message delivery failed, unregistered user")

  def handle_incoming_sms(self, message):
    """ This handles messages from the cellphone user which is either a:
        - Command (defined in CommandHandler)
        - Outgoing message
    """

    self.log.info("Incoming: %s" % message)
    self.msg = message
    if not message.is_valid():
        self.log.debug("Ignoring invalid message")
        return

    if not User.exists(self, message.imsi):
        self.register_user()
        return

    self.user = User(self, message.sender)

    if not self.user.active:
        self.reply("Your account is no connected to your Facebook. " \
                   "Please log in at %s/oauth to activate service" % self.conf.api_url)
        return

    if int(message.recipient) == int(self.conf.app_number):
      self.parse_command(message)
    else:
      self.post(message)

  def parse_command(self, message):
      """ Recognize command, parse arguments, and call appropriate handler.
      """
      if len(message.body.split()) > 1:
          cmd, args = message.body.split(None, 1)
          args = args.split()
      elif len(message.body.split()) == 1:
          cmd = message.body.split()[0]
          args = None
      else:
          cmd = None
          args = None

      try:
          self.cmd_handler.dispatch(message, cmd, args)
      except CommandError as e:
          self.reply(str(e).replace("\"", "")) # Send the failure message to the user.

  def register_user(self):
    """ Register here means put the user/IMSI in the table.
    Activation still needs to happen on the OAuth module
    """

    if not User.exists(self, self.msg.imsi):
      try:
        self.user = User.register(self, self.msg.sender)
        self.user.fb.register()
        self.reply("Welcome to the Facebook SMS service. " + \
                    "You are now registered. Please go to %s/oauth to activate" % self.conf.api_url)
      except Exception as e:
        self.log.error("Error while registering %s: %s" % (self.msg.sender, e))
        self.reply("The FB service is currently unavailable, please try again later.")
        if self.user is not None:
          self.user.delete() # Do some housekeeping


  def set_user_active(self, status):
    """ Handles activating/deactivating users and sends the appropriate notifications
    """
    if status == True:
      if not self.user.registered:
        self.user.set_registered(True)

        self.reply("Your account is now setup! " + \
                   "You can send messages to friends by sending an SMS to %s<friend FB id>. " % self.conf.number_prefix)
        self.reply( "Find your friend's number by invoking the \"friend\" command.")
        self.reply('Send "help" to %s to learn how to use the service.' % self.conf.app_number)
      else:
        self.reply("You're account is now active and service has been resumed")
    else:
      self.reply("Your account has lost connectivity with Facebook, please go to %s/oauth to activate again" % self.conf.api_url)

    self.user.set_active(status)


  def unsubscribe(self):
    """ Delete the user from the DB and the API server
    """
    try:
        self.user.delete()
        self.reply("You have been successfully unsubscribed from this service")
    except Exception as e:
        self.log.error("Error while unsubscribing %s: %s" % (self.user.number, e))
        self.reply("The FB service is currently unavailable, please try again later.")

  def find_friend(self, query):
    """ Processes a friend lookup request
    """
    try:
        matches = self.user.fb.find_friend(query)
    except AuthError:
        self.set_user_active(False)
    except Exception as e:
        self.log.error("Error while searching for friend %s: %s" % (self.user.number, e))
        self.reply("The FB service is currently unavailable, please try again later.")
        return

    if len(matches) == 0:
      result_msg = "There were no matches for your friend search for \"%s\"" % query
    else:
      result_msg = "%d Friend(s) matched your search for \"%s\":" % (len(matches), query)
      for friend in matches[:5]: # Return the top 5
        # TODO What FB fields should we send to best dissambiguate the results. No we can't ID with pictures :(
        result_msg += "\n %s - %s" % (friend.name, self.id_to_number(friend.facebook_id))
    self.reply(result_msg)

  def wall_info(self):
    """ Get the "phone number" of the FB user as represented in the BTS
    """
    try:
        self.reply("The number of your wall is %s." % self.id_to_number(self.user.fb.profile.facebook_id))
    except AuthError:
        self.set_user_active(False)
    except Exception as e:
        self.log.error("Error while getting profile for %s: %s" % (self.user.number, e))
        self.reply("The FB service is currently unavailable, please try again later.")
        return

  def reply(self, body):
     """ Convenience function to respond to the sender of the app's message.
     """
     m = Message(self.conf.app_number, self.msg.sender, None, body)
     self.send(m)

  def post(self, msg):
    """ Sends out a message to the API
    """
    try:
        sender = self.user.fb.profile.facebook_id
        recipient = self.number_to_id(msg.recipient)
        body = msg.body

        post = Post(sender, recipient, body)
        self.log.debug(" Sending FB message: %s" % post)
        self.user.fb.post_message(post)
    except AuthError:
        self.log.info("Auth failed on send message for user %s: %s" % (self.user.number, e))
        self.reply("Message not delivered.") # TODO Lets change this to the BTS delivery failed report
        self.set_user_active(False)
    except Exception as e:
        self.log.error("Failed to send message for user %s: %s" % (self.user.number, e))
        self.reply("Message not delivered. Service unavaialabe. Please try again later") # TODO This one too. There is more of them

  def send(self, msg):
    """ Convenience function to send a message via the handler
    """
    self.log.debug("Sending: %s" % msg)
    self.msg_sender.send_sms(msg.sender, msg.recipient, msg.subject, msg.body)

  def id_to_number(self, facebook_id):
    """ Convenience function to convert a FB id
        to internal number representation
    """
    return '%s%s' % (self.conf.number_prefix, facebook_id)

  def number_to_id(self, number):
    """ Convenience function to convert an internal number to
        the appropriate FB id
    """
    prefix_len = len(str(self.conf.number_prefix))
    if not number.startswith(str(self.conf.number_prefix)):
      raise ValueError("Invalid number %s. Missing prefix code %s" % (number, self.conf.number_prefix))
    return number[prefix_len:]


