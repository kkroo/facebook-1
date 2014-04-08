import time, datetime
import re
from facebooksms import *

class FacebookSMS:
  def __init__(self, imsi, conf):
    self.msg = None
    self.user = None
    self.imsi = imsi
    self.conf = conf
    self.db = conf.db_conn
    self.session_provider = self._init_session_provider(self.conf.provider_type)
    self.cmd_handler = CommandHandler(self)
    self.msg_sender = self._init_sender(self.conf.sender_type)
    self._init_db()
    self.log = self.conf.log
    self.log.debug("Init done.")

  def _init_session_provider(self, provider_type):
      if provider_type == "test":
          return FacebookTestSession
      if provider_type == "chat":
          return FacebookChatSession
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
      raise ValueError("No sender of type '%s' exists." % sender_type)

  def _init_db(self, purge=False):
      # XXX: Should use a separate connection for IMMEDIATE transactions?
      if purge:
          self.db.execute("BEGIN TRANSACTION")
          tables = [self.conf.t_users]
          for t in tables:
              self.db.execute("DROP TABLE %s" % t)
          self.db.commit()

      # Parameter substitution doesn't work for table names, but we scrub
      # unsafe names in the accessors for the table name properties so these
      # should be fine.
      self.db.execute("CREATE TABLE IF NOT EXISTS %s " % self.conf.t_users + \
          "(number TEXT not NULL UNIQUE ON CONFLICT IGNORE, " + \
          "email TEXT, password TEXT )" )
      self.db.commit()

  def _cleanup(self):
    if not self.user is None:
      self.user.close_session()

  def handle_incoming_msg(self, msg):
    r = self.db.execute("SELECT number FROM %s " % (self.conf.t_users,) + \
          "WHERE email = ? AND password IS NOT NULL LIMIT 1", (msg.recipient,))

    res = r.fetchall()
    if len(res) == 1:
        m = Message(self.id_to_number(msg.sender), res[0][0], "", msg.body)
        self.send(m)



  def handle_incoming_sms(self, message):
    self.log.info("Incoming: %s" % message)
    self.msg = message
    if not message.is_valid():
        self.log.debug("Ignoring invalid message")
        return

    if not User.is_registered(self, message.sender):
        self.register_user()
        return

    self.user = User(self, message.sender)
    try:
        self.user.start_session()
    except AuthError:
        self.log.debug("Failed to auth login for user %s" % message.sender)
        self.reply("Facebook SMS failed to authenticate. " + \
                   "Please re-send your credentials to %s." % self.conf.app_number)
        self.user.set_auth() #reset credentials
        return
    # except Exception as e:
    #     self.reply("Facebook SMS service is currently unavailable. Please try again later.")
    #     self.log.error("Failed to login user %s: %s" % (message.sender,e))
    #     return

    if self.cmd_handler.looks_like_command(message):
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

  def id_to_number(self, facebook_id):
    return '%s%s' % (self.conf.number_prefix, facebook_id)

  def number_to_id(self, number):
    prefix_len = len(str(self.conf.number_prefix))
    if not number.startswith(str(self.conf.number_prefix)):
      raise ValueError("Invalid number %s. Missing prefix code %s" % (number, self.conf.number_prefix))
    return number[prefix_len:]

  def register_user(self):
    # Put user in table if doesnt exist
    if not User.exists(self, self.msg.sender):
      if not User.register(self, self.msg.sender):
        self.reply("This number is already associated with an account.")
        return

      self.reply("Welcome to the Facebook SMS service. " + \
                  "To begin please enter your email address.")
      return

    # sanity check user is registered
    self.user = User(self, self.msg.sender)
    if not self.user.number == self.msg.sender:
      return

    # state machine to collect user email
    if not self.user.email:
      if self.collect_email():
        self.reply("Please enter your password.")
      return

    # state machine to collect user password
    if not self.user.password and not self.collect_password():
      return

    # TODO how do we want to handle Internet connectivity issues for registration auth?
    try:
      self.user.fb.register(self.user.email, self.user.password)
    except AccountExistsError:
      self.reply("This FB account is already registered to another user")
      self.user.delete()
      return
    except Exception as e:
      self.log.error("Error registering user with exception %s" % e)
      self.reply("The FB service is currently unavailable, please try again later")
      self.user.delete()
      return


    # TODO how do we want to handle Internet connectivity issues for registration auth?
    if self.user.is_active:
      try:
        self.user.start_session()
        self.send_registered()
        return
      except AuthError:
        self.log.debug("Auth failed for user %s with email %s" % (self.user.number, self.user.email))
        self.reply("Authentication failed. Please enter your email address.")
        self.user.set_auth() # reset registration to retry process
        return
      except Exception as e:
        self.log.error("Something bad happened while starting session for user %s: %s" % (self.user.number, e))
        self.reply("The FB service is currently unavailable, please try again later")
        self.user.delete()
        return



  def send_registered(self):
    self.reply("Your account is now setup! " + \
        "News feed updates will arrive from the number %s. " % self.id_to_number(self.user.fb.profile.facebook_id) + \
        "Sending an SMS to that number will post a status update")
    self.reply("You can send messages to friends by sending an SMS to %s<friend FB id>. " % self.conf.number_prefix + \
        "Find your friend's number by invoking the \"friend\" command.")
    self.reply('Send "help" to %s to learn how to use the service.' % self.conf.app_number)

  def collect_email(self):
    self.log.debug("Collecting email for user %s" % self.user.number)
    if self.user.email is None:
      email = self.msg.body.strip().lower()
      # does this pattern encompass all emails?
      if not re.match('^[_.0-9a-z-+]+@([0-9a-z][0-9a-z-]+.)+[a-z]{2,6}$', email):
          self.reply("Please enter a valid email address.")
          return False
      return self.user.set_auth(email=email)
    return True

  def collect_password(self):
    self.log.debug("Collecting password for user %s" % self.user.number)
    if self.user.password is None:
      password = self.msg.body # TODO Should we strip passwords?
      if not len(password) > 3:
        self.reply("Please enter a valid password.")
        return False
      return self.user.set_auth(email=self.user.email, password=password)
    return True

  def find_friend(self, query):
    matches = self.user.fb.find_friend(query)
    if len(matches) == 0:
      result_msg = "There were no matches for your friend search for \"%s\"" % query
    else:
      result_msg = "%d Friend(s) matched your search for \"%s\":" % (len(matches), query)
      for friend in matches[:5]:
        result_msg += "\n %s - %s" % (friend.name, self.id_to_number(friend.facebook_id))
    self.reply(result_msg)
  
  def wall_info(self):
    self.reply("The number of your wall is %s." % self.id_to_number(self.user.fb.profile.facebook_id))

  def reply(self, body):
     """ Convenience function to respond to the sender of the app's message.
     """
     m = Message(self.conf.app_number, self.msg.sender, None, body)
     self.send(m)

  def post(self, msg):
    sender = self.user.fb.profile.facebook_id
    recipient = self.number_to_id(msg.recipient)
    body = msg.body

    post = Post(sender, recipient, body)
    try:
      # Messages to self are posted as status updates
        if post.recipient == self.user.fb.profile.facebook_id:
          self.log.debug("Posting status update: %s" % post)
          self.user.fb.post_status(post)
        # Messages to others are private messages
        else:
          self.log.debug("Posting private message: %s" % post)
          self.user.fb.post_message(post) #TODO handle failures
    except AuthError:
        self.reply("Message not delivered. Authentication failed. Please enter your email address.")
        self.user.set_auth()
    except Exception:
        self.reply("Message not delivered. Service unavaialabe. Please try again later")

  def send(self, msg):
    self.log.debug("Sending: %s" % msg)
    self.msg_sender.send_sms(msg.sender, msg.recipient, msg.subject, msg.body)
