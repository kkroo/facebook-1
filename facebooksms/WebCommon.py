import web, requests
from Crypto.Hash import SHA
from Crypto.Signature import PKCS1_PSS
from Crypto.PublicKey import RSA
from Crypto.Util.asn1 import DerSequence
from subprocess import Popen, PIPE
import base64

class WebCommonBase:
    def POST(self):
      raise NotImplementedError

    def verify(self, data, fields=list()):
        needed_fields = ["imsi", "mac"] + fields
        if all(i in data for i in needed_fields):
            self._verify_channel(data)
        else:
          raise web.BadRequest()

    def _verify_channel(self, data):
        mac = base64.b64decode(str(data.mac))
        cert = open(self.config.api_cert_file).read()
        #Verify MAC
        params = dict(data)
        del params['mac']
        self._verify_signature(params, mac, cert)

    def _verify_signature(self, data, mac, cert):
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


