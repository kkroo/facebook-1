#!/usr/bin/python
import threading
import traceback
import logging, yaml
import web, requests
import syslog
from vbts_interconnects import vbts_util
import re
from facebooksms import Config
from ESL import *
from Crypto.Hash import SHA
from Crypto.Signature import PKCS1_PSS
from Crypto.PublicKey import RSA
from Crypto.Util.asn1 import DerSequence
import base64


class api_request:
    def POST(self):
      raise NotImplementedError

    def verify(self, data, fields=list()):
        needed_fields = ["imsi", "mac"] + fields
        if all(i in data for i in needed_fields):
            mac = str(base64.b64decode(data.mac))

            #Verify MAC
            params = dict(data)
            del params['mac']
            cert = open(web.fb_config.api_cert_file).read()
            self._verify_signature(params, mac, cert)
        else:
          web.log.debug("Failed request, missing args")
          raise web.BadRequest()

    def _verify_signature(self, data, mac, cert):
        self._verify_cert(cert)
        key = self._cert_to_key(cert)
        h = SHA.new()
        for k,v in sorted(params.items(), key=lambda x: x[0]):
          h.update("%s=%s" % (k, v))
        verifier = PKCS1_PSS.new(key)
        if not verifier.verify(h, mac):
          raise web.Forbidden()

    def _verify_cert(self, cert):
        p1 = Popen(["openssl", "verify", "-CApath", web.fb_config.ca_path, "-crl_check_all"], \
                   stdin = PIPE, stdout = PIPE, stderr = PIPE)

        message, error = p1.communicate(cert)
        if p1.returncode != 0:
          raise web.Forbidden()

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



class callback(api_request):
    def POST(self):
        data = web.input()
        self.verify(data, fields=["sender_id", "sender_name", "body"])
        web.log.debug("Incoming callback %s" % data)
        imsi = str(data.imsi)
        sender_id = str(data.sender_id)
        sender_name = str(data.sender_name)
        body = str(data.body)
        web.log.info("Sending msg to freeswitch for sender=%s, recipient=%s" % (sender_name, imsi))
        self.send_to_fs(imsi, sender_id, sender_name, body)
        raise web.Accepted()

    def send_to_fs(self, imsi, sender_id, sender_name, body):
      conf = vbts_util.get_conf_dict()
      esl = ESLconnection(conf['fs_esl_ip'], conf['fs_esl_port'], conf['fs_esl_pass'])
      if esl.connected():
         e = esl.api("python VBTS_FacebookSMS_Callback %s|%s|%s|%s" %\
             (imsi, sender_id, sender_name, body))
      else:
         web.log.error("Freeswitch is not running")


if __name__ == "__main__":
    web.config.debug = True

    web.log = logging.getLogger("facebooksms.client")
    conf_file = open("/etc/facebooksms/client.yaml", "r")
    config_dict = yaml.load("".join(conf_file.readlines()))
    web.fb_config = Config(config_dict, web.log )
    logging.basicConfig(filename="%s/client.log" % web.fb_config.log_dir, level=web.fb_config.log_level)
    web.log.info("Starting up client.")
    app = web.application((web.fb_config.callback_path, "callback"), locals())
    app.run()
    web.log.info("Terminating client.")

