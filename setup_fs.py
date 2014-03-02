from distutils.core import setup, Extension

setup(name="facebooksms",
      version="0.0.1",
      description="Facebook for SMS",
      author="Omar Ramadan",
      author_email="omar.ramadan@berkeley.edu",
      license='bsd',
      packages=['facebooksms'],
      scripts=['facebooksms-interactive'],
      data_files=[('/etc/', ['conf/facebooksms.yaml']),
                  ('/usr/local/freeswitch/scripts/', ['freeswitch/VBTS_FacebookSMS.py'])
                  ]
)
