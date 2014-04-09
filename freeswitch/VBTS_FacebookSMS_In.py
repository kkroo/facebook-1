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
    to = args[1]
    fromm = args[2]
    text = args[3]
    if ((not to or to == '') or
        (not fromm or fromm == '')):
        consoleLog('err', 'Malformed Args\n')
        exit(1)


    logging.basicConfig(filename="/var/log/facebooksms.log", level="DEBUG")
    facebooksms_log = logging.getLogger("facebooksms.facebooksms")
    conf_file = open("/etc/facebooksms/facebooksms.yaml", "r")
    config_dict = yaml.load("".join(conf_file.readlines()))
    conf = facebooksms.Config(config_dict, facebooksms_log)

    app = facebooksms.FacebookSMS(conf)
    app.fs = FreeSwitchMessenger.FreeSwitchMessenger()
    fss = FreeSwitchSender(app)
    app.msg_sender = fss

    consoleLog('info', "Got '%s' from %s to %s(%s)\n" % (text, fromm, to, imsi))
    msg = facebooksms.Message(fromm, to, None, text, imsi)
    app.handle_incoming_msg(msg)

def fsapi(session, stream, env, args):
    #chat doesn't use message anyhow
    chat(None, args)
