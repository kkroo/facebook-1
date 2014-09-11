from setuptools import setup

setup(name="facebooksms",
      version="0.0.2",
      description="Facebook for SMS",
      author="Omar Ramadan",
      author_email="omar.ramadan@berkeley.edu",
      license='bsd',
      packages=['facebooksms', 'facebooksms.bts'],
      install_requires=[
          'requests',
          'web.py',
          'pyyaml',
          'lxml',
          'cssselect',
          'pyyaml'
      ],
      dependency_links=['http://github.com/kkroo/SleekXMPP/tarball/master'],
      scripts=['facebooksms-bts-interactive', 'facebooksms/bts/web/facebooksms-client.py'],
      data_files=[
                      ('/var/log/facebooksms', []),
                      ('/etc/facebooksms/', ['conf/client.yaml']),
                      ('/etc/lighttpd/conf-enabled/', ['facebooksms/bts/web/10-facebooksms-client-fastcgi.conf']),
                      ('/etc/freeswitch/chatplan/default/', ['freeswitch/91_route_facebook.xml']),
                      ('/usr/share/freeswitch/scripts/', \
                      ['freeswitch/VBTS_FacebookSMS_Main.py', 'freeswitch/VBTS_FacebookSMS_Callback.py'])
                  ]
)
