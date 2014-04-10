from facebooksms import *
from Queue import *
import sleekxmpp
import datetime
from lxml.html import fromstring, tostring
from lxml.cssselect import CSSSelector
import requests
from urlparse import parse_qs, urlparse


class FacebookChatSession(FacebookSessionProvider):
  def __init__(self, app=None):
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

  def register(self, email, password):
    pass

  def logout(self):
    self.xmpp.disconnect(wait = True)

  def login(self, email, password):
    if self.xmpp is not None:
      raise Exception("Session in progress!")

    self.email = email
    self.password = password
    psuedo_id = abs(hash(email)) % 10000
    psuedo_name = email.split('@')[0]
    self.jid = "%s@chat.facebook.com" % email

    self.xmpp = ChatClient(self.jid, password)
    if not self.xmpp.connect(('chat.facebook.com', 5222), reattempt=False):
      raise Exception("Failed to connect to server")

    try:
      self.xmpp.process(block=False)
      self.auth_ok = self.xmpp.auth_queue.get(timeout=30)
      self.log.debug("Auth is: %s" % self.auth_ok)
    except Empty:
      raise Exception("Timeout while authorizing")

    if not self.auth_ok:
      self.log.error("Auth exception")
      raise AuthError()

    #print "Getting vcard"
    #print self.xmpp.get_vcard()
    self.profile = FacebookUser(psuedo_id, psuedo_name)

  def find_friend(self, name_query):
    if not self.auth_ok:
      raise AuthError()

    headers = {'User-Agent': 'Mozilla/5.0 (Symbian/3; Series60/5.2 NokiaN8-00/012.002; Profile/MIDP-2.1 Configuration/CLDC-1.1 ) AppleWebKit/533.4 (KHTML, like Gecko) NokiaBrowser/7.3.0 Mobile Safari/533.4 3gpp-gba'}

    # start session
    r = requests.session()
    q = r.post('https://m.facebook.com/login.php', data={'email': self.email, 'pass': self.password}, headers=headers)
    if 'login_form' in q.text:
        raise AuthError()

    # do the search
    q = r.get('https://m.facebook.com/search/', params={'search': 'people', 'query': name_query}, headers=headers)

    # end the session so we look more human?
    r.get('https://m.facebook.com/logout.php')

    h = fromstring(q.text.encode('utf-8'))
    sel = CSSSelector('div.listSelector tr td.name')
    sel_link = CSSSelector('a')

    results_raw = [sel_link(x) for x in sel(h)]
    results = []
    for result in results_raw:
        if len(result) < 2:
          continue
        name = result[0].text.strip()
        link = result[1].attrib['href']
        fb_id = None

        params = parse_qs(urlparse(link).query)
        if 'id' in params or 'ids' in params:
            fb_id = params['id'][0] if 'id' in params else params['ids'][0]
        if name and ord(name[-1]) == 8206:
            name = name[:-1].strip()
        if name and fb_id:
            results.append(FacebookUser(fb_id, name))

    return results

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
        self.auto_subscribe = False #will this stop precense spam? or auto_authorize
        self.auth_queue = Queue()
        self.add_event_handler("session_start", self.start)
        self.add_event_handler('no_auth', self.failed)

        self.registerPlugin('xep_0054')
        #self.add_event_handler('archive_result', self.handle_messages)
        #self.add_event_handler("message", self.message)

    def add_message_handler(self, handler):
      self.add_event_handler("message", handler)

    def message(self, event):
      print event

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

