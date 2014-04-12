from distutils.core import setup, Extension

setup(name="facebooksms",
      version="0.0.1",
      description="Facebook for SMS",
      author="Omar Ramadan",
      author_email="omar.ramadan@berkeley.edu",
      license='bsd',
      packages=['facebooksms'],
      scripts=['facebooksms-interactive', 'web/facebooksms-server.py', 'web/facebooksms-client.py'],
      data_files=[
                      ('/var/log/facebooksms', []),
                      ('/etc/facebooksms/', ['conf/facebooksms.yaml']),
                      ('/usr/local/freeswitch/scripts/', \
                          ['freeswitch/VBTS_FacebookSMS_Main.py', 'freeswitch/VBTS_FacebookSMS_Callback.py'])
                  ]
)
