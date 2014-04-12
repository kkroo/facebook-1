from facebooksms import *
from Queue import *
import sleekxmpp
import datetime
from lxml.html import fromstring, tostring
from lxml.cssselect import CSSSelector
import requests
import json
from urlparse import parse_qs, urlparse

""" NOTE: You can't use this with the base station client any more.
          You must provide the login method with a password. Not
          storing those on the base station for security reasons.
"""
class FacebookChatSession(FacebookSessionProvider):
  def __init__(self, app=None):
    self.profile = None
    self.jid = None
    xmpp_log = logging.getLogger("facebooksms.xmpp")
    self.log = logging.getLogger("facebooksms.xmpp")
    xmpp_log.setLevel("INFO")
    self.xmpp = None
    self.web_session = None
    self.auth_ok = None
    self.web_headers = {'User-Agent': 'Mozilla/5.0 (Symbian/3; Series60/5.2 NokiaN8-00/012.002; Profile/MIDP-2.1 Configuration/CLDC-1.1 ) AppleWebKit/533.4 (KHTML, like Gecko) NokiaBrowser/7.3.0 Mobile Safari/533.4 3gpp-gba'}


  @property
  def profile(self):
    return self.profile


  def logout(self):
    self.xmpp.disconnect(wait = True)
    self.web_session.get('https://m.facebook.com/logout.php', headers=self.web_headers)


  def login(self, email, password):
    if self.xmpp is not None:
      raise Exception("Session in progress!")

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

    self.web_session = requests.session()
    q = self.web_session.post('https://m.facebook.com/login.php', data={'email': email, 'pass': password}, headers=self.web_headers)

    if not self.auth_ok or 'login_form' in q.text:
      self.log.error("Auth exception")
      raise AuthError()

    h = fromstring(q.text.encode('utf-8'))
    sel = CSSSelector('input[name=privacy]')
    facebook_id = json.loads(sel(h)[0].attrib['value'])['owner']

    self.profile = FacebookUser(facebook_id, None)

  def find_friend(self, name_query):
    if not self.auth_ok:
      raise AuthError()

    # do the search
    q = self.web_session.get('https://m.facebook.com/search/', params={'search': 'people', 'query': name_query}, headers=self.web_headers)

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

    def add_message_handler(self, handler):
      self.add_event_handler("message", handler)

    def failed(self, event):
        self.auth_queue.put(False)

    def start(self, event):
        self.send_presence()
        self.auth_queue.put(True)

    def get_vcard(self, jid=None):
      # Doest allow us to retrieve much more than a name and a picture
      return self.plugin['xep_0054'].get_vcard(jid, local=False, cached=True, timeout=5)

