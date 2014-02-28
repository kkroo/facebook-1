import time
from facebooksms import * 
from email.utils import parseaddr

class FacebookNegativeOne:
  def __init__(self, conf):
    self.msg = None
    self.user = None
    self.conf = conf
    self.db = conf.db_conn
    self.session_handler
    self.cmd_handler = CommandHandler(self)
    self.msg_sender = self._init_sender(self.conf.sender_type)
    self._init_db()
    self.log = self.conf.log
    self.log.debug("Init done.")

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
      self.db.execute("CREATE TABLE IF NOT EXISTS %s (number TEXT, email TEXT, password TEXT, last_fetch REAL, auth_ok INTEGER, UNIQUE(number) ON CONFLICT IGNORE)" % self.conf.t_users)
      self.db.commit()

  def fetch_updates(self, n):
    """ Sort the users table by time of last fetch ASC
        and select the top n users. Fetch updates, and
        push to user
    """
    raise NotImplementedError

  def handle_incoming(self, message):
    self.log.info("Incoming: %s" % message)
    self.msg = message
    if not message.is_valid():
        log.debug("Ignoring invalid message")
        return
    if not User.is_registered(message.sender):
        self.register_user()
    self.user = User(self, message.sender)
    try:
        self.user.start_session()
    except AuthError:
        self.log.debug("Failed to auth login")
        self.reply("Failed to authenticate. Please send your credentials to %s " % \
                    self.conf.app_number)
        return
    except Exception as e:
        self.log.debug("Failed to login: %s" % e)
        return

    if self.cmd_handler.looks_like_command(message):
      self.parse_command(message, command, arguments)
    else:
      self.post(message)

  def parse_command(self, message, command, arguments):
    raise NotImplementedError

  def id_to_number(self, facebook_id):
    return self.conf.number_prefix + '' + facebook_id

  def number_to_id(self, number):
    if numnber == self.msg.sender:
      return self.user.profile.facebook_id
    else:
      return number[self.conf.number_prefix:]

  def post(self, message):
    post = Post(self.number_to_id(message.sender), self.number_to_id(message.recipient), message.body)

  def register_user(self):
    email, password = self.msg.body.split("\n")
    if not parseaddr(email)[1] or not password or password.contains("\n"):
        self.reply("Registration Failed, please enter a valid email address \
                    on one line and a valid password on the next line")
        return
    User.register(self.msg.sender, email, password)
    
  def reply(self, body):
     """ Convenience function to respond to the sender of the app's message.
     """
     m = Message(self.conf.app_number, self.msg.sender, None, body)

