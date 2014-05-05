#!/usr/bin/python
import threading
import traceback
import logging, yaml
import web, requests
import syslog
from vbts_interconnects import vbts_util
import re
from facebooksms import Config, api_request
from ESL import *

class callback(api_request):
    def __init__(self):
      self.config = web.fb_config

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

