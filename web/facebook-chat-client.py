#!/usr/bin/python
import threading
import traceback

import web, requests
import syslog

urls = ("/callback", "callback")

class callback:
    def POST(self):
        data = web.input()
        needed_fields = ["imsi", "sender", "body"]
        if all(i in data for i in needed_fields):
            imsi = str(data.imsi)
            sender = str(data.sender)
            body = str(data.body)
            print data
            raise web.Accepted()
        raise web.BadRequest()


if __name__ == "__main__":
    web.config.debug = True
    app = web.application(urls, locals())
    app.run()
