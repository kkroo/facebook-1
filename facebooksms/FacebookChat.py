from facebooksms import *
from Queue import *
import sleekxmpp
import datetime


class FacebookChatSession(FacebookSessionProvider):
  def __init__(self):
    self.profile = None
    self.jid = None
    xmpp_log = logging.getLogger("sleekxmpp")
    self.log = logging.getLogger("facebooksms")
    xmpp_log.setLevel("INFO")
    self.xmpp = None
    self.auth_ok = None

  @property
  def profile(self):
    return self.profile

  def logout(self):
    self.xmpp.disconnect(wait = True)

  def login(self, email, password):
    if self.xmpp is not None:
      raise Exception("Session in progress!")

    psuedo_id = abs(hash(email)) % 10000
    psuedo_name = email.split('@')[0]
    self.jid = "%s@chat.facebook.com" % email

    self.xmpp = ChatClient(self.jid, password)
    if not self.xmpp.connect(('chat.facebook.com', 5222), reattempt=False):
      raise Exception("Failed to connect to server")

    try:
      self.xmpp.process(block=False)
      self.auth_ok = self.xmpp.auth_queue.get(timeout=5)
      self.log.debug("Auth is: %s" % self.auth_ok)
    except Empty:
      raise Exception("Timeout while authorizing")

    if not self.auth_ok:
      self.log.error("Auth exception")
      raise AuthError()

    #print "Getting vcard"
    #print self.xmpp.get_vcard()
    self.profile = FacebookUser(psuedo_id, psuedo_name)

  def get_messages(self, earliest_timestamp):
    #print self.xmpp.get_messages(self.jid, earliest_timestamp - datetime.timedelta(days=5))
    return []

  def get_home_feed_posts(self, earliest_timestamp):
    return []

  def post_message(self, post):
    self.xmpp.send_message(mto="-%s@chat.facebook.com" % post.recipient, mbody=post.body)


class ChatClient(sleekxmpp.ClientXMPP):

    def __init__(self, jid, password):
        sleekxmpp.ClientXMPP.__init__(self, jid, password)
        self.use_ipv6 = False
        self.auth_queue = Queue()
        self.add_event_handler("session_start", self.start)
        self.add_event_handler('no_auth', self.failed)

        self.registerPlugin('xep_0054')
        #self.add_event_handler('archive_result', self.handle_messages)
        #self.add_event_handler("message", self.message)

    def failed(self, event):
        self.auth_queue.put(False)

    def start(self, event):
        self.send_presence()
        # self.get_roster()
        self.auth_queue.put(True)

    def get_messages(self, login, start):
      # Not compatible with Facebook..
      return self.plugin['xep_0313'].retrieve(jid=login, start=start, timeout=5)

    def get_vcard(self, jid=None, ifrom=None):
      # Doest allow us to retrieve much more than a name and a picture
      return self.plugin['xep_0054'].get_vcard(jid, local=False, timeout=5)

