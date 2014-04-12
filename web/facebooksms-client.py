#!/usr/bin/python
import threading
import traceback

import web, requests
import syslog
from vbts_interconnects import vbts_util
from ESL import *

urls = ("/callback", "callback")

class callback:
    def POST(self):
        data = web.input()
        needed_fields = ["imsi", "sender_id", "sender_name", "recipient", "body"]
        web.log.debug("Incoming callback %s" % data)
        if all(i in data for i in needed_fields):
            imsi = str(data.imsi)
            sender_id = str(data.sender_id)
            sender_name = str(data.sender_name)
            recipient = str(data.recipient)
            body = str(data.body)
            web.log.info("Sending msg to freeswitch for sender=%s, recipient=%s" % (sender_name, recipient))
            self.send_to_fs(imsi, recipient, sender_id, sender_name, body)
            raise web.Accepted()
        web.log.info("Callback failed. Missing args %s" % data)
        raise web.BadRequest()

    def send_to_fs(self, imsi, recipient, sender_id, sender_name, body):
      conf = vbts_util.get_conf_dict()
      esl = ESLconnection(conf['fs_esl_ip'], conf['fs_esl_port'], conf['fs_esl_pass'])
      if esl.connected():
         e = esl.api("python VBTS_FacebookSMS_In %s|%s|%s|%s|%s" %\
             (imsi, recipient, sender_id, sender_name, body))
      else:
         web.log.error("Freeswitch is not running")


if __name__ == "__main__":
    web.config.debug = True

    web.log = logging.getLogger("facebooksms.client")
    conf_file = open("/etc/facebooksms/facebooksms.yaml", "r")
    config_dict = yaml.load("".join(conf_file.readlines()))
    web.fb_config = Config(config_dict, web.log )
    logging.basicConfig(filename="%s/client.log" % web.fb_config.log_dir, level=web.fb_config.log_level)


    web.log.info("Starting up client.")
    app = web.application(urls, locals())
    app.run()
    web.log.info("Terminating client.")

