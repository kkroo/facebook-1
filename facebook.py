import logging
import sqllite3
import yaml
import time

class Message:
  def __init__(self, sender, recipient, subject, body):
    self.sender = sender
    self.recipient = recipient
    self.subject
    self.body = body

  def is_valid(self):
    return self.sender and self.recipient and self.body

  def __str__(self):
    return "from='%s', to='%s', subject='%s', body='%s'" % (self.sender,
                                              self.recipient,
                                              self.subject,
                                              self.body)
class User:
  session_provider = FacebookSession
  def __init__(self, number):
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

class FacebookNegativeOne:
  def __init__(self, conf):
    self.msg = None
    self.user = None
    self.conf = conf
    self.log = self.conf.log
    self.log.debug("Init done.")

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
    self.user = User(message.sender)
    try:
        self.user.start_session()
    except AuthError:
        self.log.debug("Failed to auth login")
        self.reply("Failed to authenticate. Please \
                    resend your credentials to %s " %
                    self.conf.app_number)
        return
    except Exception as e:
        self.log.debug("Failed to login: %s" % e)
        return
    if message.recipient == self.conf.app_number:
      cmd, args = message.body.split(None, 1)
      self.parse_command(message, command, arguments)
    else:
      self.post(message)

  def parse_command(self, message, command, arguments):
    raise NotImplementedError

  def post(self, message):
    raise NotImplementedError

  def register_user(self):
    raise NotImplementedError

  def reply(self, body):
     """ Convenience function to respond to the sender of the app's message.
     """
     m = Message(self.conf.app_number, self.msg.sender, None, body)


class Config:
  def __init__(self, config_dict, logger):
    self.config_dict = config_dict
    self.log = logger
    self.db = sqllite3.connect(self.db_file)
    self.log.debug("Connnected to DB: %S" % self.db_file)

  @property
  def db_file(self):
    return self.config_dict['db_file']

  @property
  def app_number(self):
    return self.config_dict['app_number']

  @property
  def number_prefix(self):
    return self.config_dict['number_prefix']



if __name__ == "__main__":
  import argparse
  parser = argparse.ArgumentParser(description="Facebook Negative One, a SMS interface.")

  parser.add_argument('--from', '-f', action='store', dest='sender', \
      help="Sender of incoming message.")

  parser.add_argument('--to', '-t', action='store', dest='recipient', \
      help="Recipient of incoming message.")

  parser.add_argument('--message', '-m', action='store', dest='message', \
      help="Body of incoming message.")

  parser.add_argument('--config', '-c', action='store', dest='config', \
      help="Configuration file (default: facebooknegativeone.yaml)", \
      default="facebooknegativeone.yaml")

  parser.add_argument('--fetch', action='store_true', dest='fetch_mode', \
      help="Go into fetch mode.")

  parser.add_argument('--number', '-n', action='store', dest='fetch_number', \
      help="Number of users to fetch updates for (fetch mode only).", \
      type=int, default=10)

  parser.add_argument('--log', '-l', action='store', dest='logfile', \
      help="log file (default: facebooknegativeone.log)", \
      default="facebooknegativeone.log")

  parser.add_argument('--debug', action='store_true', dest='debug_mode', \
      help="enable debug logging.")
  args = parser.parse_args()


  conf_file = open(args.config, "r")
  config_dict = yaml.load("".join(conf_file.readlines()))


  log = logging.getLogger('facebooknegativeone')
  if args.debug_mode:
    logging.basicConfig(filename=args.logfile, level=logging.DEBUG)
  else:
    logging.basicConfig(filename=args.logfile)

  conf = Config(config_dict, log)
  app = FacebookNegativeOne(conf)

  if args.fetch_mode:
    if args.sender or args.recipient or args.message or args.subject:
      log.error("Sender, recipient, message, and subject args shouldn't be \
                 set for fetch mode")
    app.fetch_updates(args.fetch_number)
  else:
      msg = Message(args.sender, args.recipient, args.subject, args.message)
      app.handle_incoming(msg)
