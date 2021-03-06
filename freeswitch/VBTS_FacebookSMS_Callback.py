#!/usr/bin/python
from libvbts import FreeSwitchMessenger
from freeswitch import *
import logging
import sys
import re
import time
import facebooksms
import yaml

class FreeSwitchSender(facebooksms.Sender):

    def __init__(self, fbsms):
        self.fbsms = fbsms

    def send_sms(self, sender, recipient, subject, data):
        sender = str(sender)
        subject = '' if subject is None else "%s: " % subject
        consoleLog('info', str("sending '%s' to %s from %s\n" % (data, recipient, sender)))
        self.fbsms.fs.send_smqueue_sms("", recipient, sender, subject + data)

def chat(message, args):
    args = args.split('|')
    if (len(args) < 4):
        consoleLog('err', 'Missing Args\n')
        exit(1)
    imsi = args[0]
    sender_id = args[1]
    sender_name = args[2]
    text = args[3]

    facebooksms_log = logging.getLogger("facebooksms.callback")
    conf_file = open("/etc/facebooksms/client.yaml", "r")
    config_dict = yaml.load("".join(conf_file.readlines()))
    conf = facebooksms.Config(config_dict, facebooksms_log)
    logging.basicConfig(filename="%s/callback.log" % conf.log_dir, level=conf.log_level)

    app = facebooksms.FacebookSMS(conf)
    app.fs = FreeSwitchMessenger.FreeSwitchMessenger()
    fss = FreeSwitchSender(app)
    app.msg_sender = fss

    sender = facebooksms.FacebookUser(sender_id, sender_name)
    consoleLog('info', "Got '%s' from %s to %s\n" % (text, sender, imsi))
    msg = facebooksms.Post(sender, imsi, text)
    app.handle_incoming_post(msg)

def fsapi(session, stream, env, args):
    #chat doesn't use message anyhow
    chat(None, args)
