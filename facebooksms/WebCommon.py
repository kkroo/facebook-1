import requests
from Crypto.Hash import SHA
from Crypto.Signature import PKCS1_PSS
from Crypto.PublicKey import RSA
from Crypto.Util.asn1 import DerSequence
from subprocess import Popen, PIPE
import base64
import web

""" This class serves as a wrapper to load data from webpy
    requests, and be able to verify the integrity and authenticity
    of the requestor.
"""
class WebCommonBase(object):
    def __init__(self):
      self.config = web.fb_config
      self._data = None
      self.fields_to_verify = ["imsi", "mac"]

    def POST(self):
      raise NotImplementedError

    def GET(self):
      raise web.NotFound()

    @property
    def data(self):
      if self._data == None:
        self._data = web.input()
        self.verify(self._data)
      return self._data

    def verify(self, data, fields=list()):
        self.fields_to_verify += fields
        if all(i in data for i in self.fields_to_verify):
            self._verify_channel(data)
        else:
          raise web.BadRequest()

    def _verify_channel(self, data):
        """ General channel verification for data coming in
            from an API request
        """
        mac = base64.b64decode(str(data.mac))
        cert = open(self.config.api_cert_file).read()
        #Verify MAC
        params = dict(data)
        del params['mac']
        self._verify_signature(params, mac, cert)

    def _verify_signature(self, data, mac, cert):
        """ Verify the signature on incoming data """
        if not self._verify_cert(cert):
          raise web.Forbidden()
        key = self._cert_to_key(cert)
        h = SHA.new()
        for k,v in sorted(data.items(), key=lambda x: x[0]):
          h.update("%s=%s" % (k, v))
        verifier = PKCS1_PSS.new(key)
        if not verifier.verify(h, mac):
          raise web.Forbidden()

    def _verify_cert(self, cert):
        """ Make sure that the cert is from a CA we trust """
        p1 = Popen(["openssl", "verify", "-CApath", self.config.ca_path], \
                   stdin = PIPE, stdout = PIPE, stderr = PIPE)

        message, error = p1.communicate(cert)
        return p1.returncode == 0

    def _cert_to_key(self, cert):
        # Convert from PEM to DER
        lines = cert.replace(" ",'').split()
        der = base64.b64decode(''.join(lines[1:-1]))

        # Extract subjectPublicKeyInfo field from X.509 certificate (see RFC3280)
        cert = DerSequence()
        cert.decode(der)
        tbsCertificate = DerSequence()
        tbsCertificate.decode(cert[0])
        subjectPublicKeyInfo = tbsCertificate[6]

        # Initialize RSA key
        return RSA.importKey(subjectPublicKeyInfo)

    @staticmethod
    def compute_mac(params, key):
        h = SHA.new()
        for k,v in sorted(params.items(), key=lambda x: x[0]):
          h.update("%s=%s" % (k, v))
        signer = PKCS1_PSS.new(key)
        return base64.b64encode(signer.sign(h))


""" This is the common base class for all classes
    that handle incoming API requests from a BTS
"""
class APICommonBase(WebCommonBase):
  def __init__(self):
    WebCommonBase.__init__(self)
    self._key = None

  def _verify_channel(self, data):
    """ So the way this method differs from its parent's
        is we know that data is coming from a BTS. So verify it.
    """
    # These requests must be from a BTS, so verify it's valid
    needed_fields = ["bts_key", "mac"]
    if all(i in data for i in needed_fields):
      # Verify the BTS key is valid
      bts_key = str(data.bts_key)
      results = web.db.select(self.config.t_base_stations, \
          where="key=$key", vars={'key': bts_key})
      try:
        bts = results[0]
      except Exception:
        web.log.info("Unauthorized base station %s" % \
                      ( bts_key ))
        raise web.Forbidden()

      #Verify that this BTS is who it says it is with its cert
      mac = base64.b64decode(data.mac)
      params = dict(data)
      del params['mac']
      self._verify_signature(params, mac, bts.cert)
    else:
      web.log.debug("Failed request, missing args")
      raise web.BadRequest()


