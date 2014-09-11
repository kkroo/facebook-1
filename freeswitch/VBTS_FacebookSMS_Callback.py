#!/usr/bin/python
import logging
import sys
import re
import time
from facebooksms.bts import *
import yaml

def chat(message, args):
    args = args.split('|')
    if (len(args) < 4):
        consoleLog('err', 'Missing Args\n')
        exit(1)
    sender = args[0]
    recipient = args[1]
    subject = args[2]
    body = args[3]

    facebooksms_log = logging.getLogger("facebooksms.callback")
    conf_file = open("/etc/facebooksms/client.yaml", "r")
    config_dict = yaml.load("".join(conf_file.readlines()))
    conf = BTSConfig(config_dict, facebooksms_log)
    logging.basicConfig(filename="%s/callback.log" % conf.log_dir, level=conf.log_level)

    app = FacebookSMS(conf)
    msg = Message(sender, recipient, subject, body)
    app.send(msg)

def fsapi(session, stream, env, args):
    #chat doesn't use message anyhow
    chat(None, args)
