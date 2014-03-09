import time, datetime
import re
from facebooksms import * 

class FacebookSMS:
  def __init__(self, conf):
    self.msg = None
    self.user = None
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
          "email TEXT, password TEXT, last_fetch TIMESTAMP )" )
      self.db.commit()

  def _cleanup(self):
    if not self.user is None:
      self.user.close_session()

  def fetch_updates(self, n):
    """ Sort the users table by time of last fetch ASC
        and select the top n users. Fetch updates, and
        push to user
    """
    r = self.db.execute("SELECT number, last_fetch FROM %s " % (self.conf.t_users,) + \
          "WHERE email is not NULL and password is not NULL " + \
          "ORDER BY last_fetch ASC LIMIT 0, %u" % (int(n),))
    result = r.fetchall()
    self.log.debug("Fetching updates for %u users" % len(result))
    for user_row in result:
      user = User(self, user_row[0])
      last_fetch = datetime.datetime.strptime(user_row[1].split('.')[0], "%Y-%m-%d %H:%M:%S")
      try:
        user.start_session()
      except AuthError:
        self.log.debug("Auth failed for user %s with email %s" % user.number, user.email)
        m = Message(self.conf.app_number, user.number, None, \
              "The Facebook SMS service failed to verify your credentials. " + \
              "Please send your email address to %s to resume service" % self.conf.app_number)
        user.set_auth()
        self.send(m)
      except Exception as e:
        self.log.error("Something bad happened while starting session for user %s: %s" % (user.number, e))

      private_messages = user.fb.get_messages(last_fetch)
      self.log.debug("Forwarding %d private messages for user %s" % (len(private_messages), user.number))
      for pm in private_messages:
        # Freeswitch freaks when I use strftime! TODO
        #timestamp = time.strftime("%b %e at %I:%M%r", time.localtime(int(pm.timestamp)))
        timestamp = "Dec 01, 12:00am"
        m = Message(self.id_to_number(pm.sender.facebook_id), user.number, "%s at %s" % (pm.sender.name, timestamp), pm.body)
        self.send(m)

      home_feed_posts = user.fb.get_home_feed_posts(last_fetch)
      self.log.debug("Forwarding %d home feed posts for user %s" % (len(home_feed_posts), user.number))
      for post in home_feed_posts:
        # Freeswitch freaks when I use strftime! TODO
        #timestamp = time.strftime("%b %e at %I:%M%r", time.localtime(int(post.timestamp)))
        timestamp = "Dec 01, 12:00am"
        m = Message(self.id_to_number(user.fb.profile.facebook_id), user.number, "%s at %s" % (post.sender.name, timestamp), post.body)
        self.send(m)

      user.close_session()
      user.update_last_fetch()

  def handle_incoming(self, message):
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
        self.reply("Facebook SMS failed to authenticate. Please re-send your credentials to %s." % \
                    self.conf.app_number)
        self.user.set_auth() #reset credentials
        return
    except Exception as e:
        self.reply("Facebook SMS service is currently unavailable. Please try again later.")
        self.log.error("Failed to login user %s: %s" % (message.sender,e))
        return

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

  def post(self, message):
    post = Post(self.user.fb.profile, FacebookUser(self.number_to_id(message.recipient)), message.body)
    self.user.fb.post_status(post)
    #TODO how do we handle delivery failures?

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
    if self.user.is_active:
      try:
        self.user.start_session()
        self.send_registered()
        return
      except AuthError:
        self.log.debug("Auth failed for user %s with email %s" % (self.user.number, self.user.email))
        self.reply("Authentication failed. Please enter your email address.")
        self.user.set_auth() # reset registration to retry process
      except Exception as e:
        self.log.error("Something bad happened while starting session for user %s: %s" % (self.user.number, e))
        self.reply("Registration failed. Please try again later.")
        self.user.delete()



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
    # Messages to self are posted as status updates
    if post.recipient == self.user.fb.profile.facebook_id:
      self.log.debug("Posting status update: %s" % post)
      self.user.fb.post_status(post)
    # Messages to others are private messages
    else:
      self.log.debug("Posting private message: %s" % post)
      self.user.fb.post_message(post)

  def send(self, msg):
    self.log.debug("Sending: %s" % msg)
    self.msg_sender.send_sms(msg.sender, msg.recipient, msg.subject, msg.body)
