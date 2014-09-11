from Queue import *
import sleekxmpp
import urllib, urlparse
import json
from . import *

""" NOTE: You can't use this with the base station client any more.
          You must provide the login method with a password. Not
          storing those on the base station for security reasons.
"""
class FBOAuthChatSession(FacebookSessionProvider):
  def __init__(self, config):
    self._profile = None
    self.log = logging.getLogger("facebooksms.api")
    self.log.setLevel("INFO")
    self.config = config
    self.xmpp = None
    self.logged_in = False
    self.access_token = None

  @staticmethod
  def _fb_graph_request(config, path, params):
      credentials = { 'client_id' : config.fb_client_id,
                 'client_secret': config.fb_client_secret,
             }
      r = requests.get("https://graph.facebook.com/%s" % path, params=dict(params.items() + credentials.items()))
      if r.status_code == 200:
        return r.text
      else:
        resp = json.loads(r.text)
        if 'error' in resp:
          if resp['error']['type'] == 'OAuthException':
            raise AuthError()
          else:
            raise Excpetion("Failed to perform FB Graph request (%s) : %s" % (resp['error']['type'], resp['error']['message']))
        else:
          raise Excpetion("Failed to perform FB Graph request (Unknown) : %s" % resp)

  @staticmethod
  def get_access_token(config, code, imsi):
      params = { 'redirect_uri' : config.server_url + "/oauth_callback?imsi=%s" % imsi,
                 'code': code
               }
      resp = FBOAuthChatSession._fb_graph_request(config, "oauth/access_token", params)
      resp = dict(urlparse.parse_qsl(resp))
      return resp['access_token']

  @staticmethod
  def get_llat(config, access_token):
      params = {'grant_type': 'fb_exchange_token',
                'fb_exchange_token': access_token }
      resp = FBOAuthChatSession._fb_graph_request(config, "oauth/access_token", params)
      resp = dict(urlparse.parse_qsl(resp))
      return resp['access_token']

  @staticmethod
  def get_email(config, access_token):
      params = {'access_token': access_token}
      resp = FBOAuthChatSession._fb_graph_request(config, "v2.1/me", params)
      resp = json.loads(resp)
      return resp['email']

  @property
  def logged_in(self):
    if not self.logged_in:
      pass # TODO Re-auth here somehow
    return self.logged_in

  @property
  def profile(self):
      if self._profile is None and self.access_token:
        params = {'access_token': self.access_token}
        resp = FBOAuthChatSession._fb_graph_request(self.config, "v2.1/me", params)
        resp = json.loads(resp)
        self._profile = FacebookUser(resp['id'], resp['name'])
      return self._profile


  def logout(self):
    self.xmpp.disconnect(wait = True)

  def login(self, email, access_token):
    if self.xmpp is not None:
      raise Exception("Session in progress!")

    self.jid = "%s@chat.facebook.com" % email # XXX What is the JID when using OAuth?
    self.access_token = access_token

    self.xmpp = ChatClient(self.jid, access_token, self.config.fb_client_id)
    if not self.xmpp.connect(('chat.facebook.com', 5222), reattempt=False):
      raise Exception("Failed to connect to server")

    try:
      self.xmpp.process(block=False)
      self.logged_in = self.xmpp.auth_queue.get(timeout=30)
    except Empty:
      raise Exception("Timeout while authorizing")

    if not self.logged_in:
      self.log.error("Auth exception")
      raise AuthError()

  def find_friend(self, name_query):
      query = "select uid, name, sex  from user  where uid in (SELECT uid2 FROM friend WHERE uid1 = me()) and (strpos(lower(name),'%s')>=0 OR strpos(name,'%s')>=0)" % (name_query, name_query)
      params = {'access_token': self.access_token,
                'q': query }
      resp = FBOAuthChatSession._fb_graph_request(self.config, "v1.0/fql", params) # XXX This is going to be deprecated soon! Find another way to search friends
      resp = json.loads(resp)

      friends = []
      for friend in resp['data']:
        friends += [FacebookUser(friend['uid'], friend['name'])]
      return friends

  def post_message(self, post):
    self.xmpp.send_message(mto="-%s@chat.facebook.com" % post.recipient, mbody=post.body)

class ChatClient(sleekxmpp.ClientXMPP):

    def __init__(self, jid, access_token, api_key):
        sleekxmpp.ClientXMPP.__init__(self, jid, 'ignorepass', sasl_mech="X-FACEBOOK-PLATFORM")
        self.credentials['api_key'] = api_key
        self.credentials['access_token'] = access_token
        self.auth_queue = Queue()
        self.add_event_handler("session_start", self.start)
        self.add_event_handler('no_auth', self.failed)
        self.registerPlugin('xep_0054')
        self.use_ipv6 = False

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

