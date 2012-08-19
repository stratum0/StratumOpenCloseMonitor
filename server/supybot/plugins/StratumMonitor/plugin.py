###
# Copyright (c) 2012, Roland Hieber
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice,
#     this list of conditions, and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions, and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#   * Neither the name of the author of this software nor the name of
#     contributors to this software may be used to endorse or promote products
#     derived from this software without specific prior written consent.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

###

import os
from datetime import datetime
import time
import supybot.utils as utils
from supybot.commands import *
import supybot.plugins as plugins
import supybot.ircutils as ircutils
import supybot.callbacks as callbacks


class StratumMonitor(callbacks.Plugin):
  """Stratum 0 Open/Close Monitor"""
  pass

  NGINX_SITE_FILE = "/etc/nginx/sites-enabled/status.stratum0.org"
  NGINX_SITE_TEMPLATE = """server {
  root /srv/status.stratum0.org;
  index index.html index.htm;
  access_log off;

  location / {
    rewrite ^/status.png$ $scheme://$http_host/{{{STATUS}}}.png redirect;
    rewrite ^/favicon.ico$ $scheme://$http_host/{{{STATUS}}}.ico redirect;
    expires +5m;
  }
  location ~* /(open|closed)(_square)?\.(ico|png)$ {
    expires off;
  }
  location ~* /status.json {
    expires +5m;
    add_header Access-Control-Allow-Origin *;
  }
}
"""
  API_PATH  = "/srv/status.stratum0.org/%s"

  API_TEXT_FILE = API_PATH % "status.txt"
  API_TEXT_TEMPLATE ="""Version: {{{VERSION}}}\r
IsOpen: {{{ISOPEN}}}\r
Since: {{{SINCE}}}\r
"""
  # one file for Stratum 0 Open/Close Monitor API and Hackerspaces.nl Space API
  # see: https://stratum0.org/wiki/Open/Close-Monitor/API
  # see: http://hackerspaces.nl/spaceapi/
  API_JSON_FILE = API_PATH % "status.json"
  API_JSON_TEMPLATE = """{\r
  "version": "{{{VERSION}}}",\r
  "isOpen": {{{ISOPEN}}},\r
  "since": "{{{SINCE}}}",\r
  \r
  "api": "0.12",\r
  "space": "Stratum 0",\r
  "url": "https:\/\/stratum0.org",\r
  "logo": "https:\/\/stratum0.org\/mediawiki\/images\/thumb\/c\/c6\/Sanduhr-twitter-avatar-black.svg\/240px-Sanduhr-twitter-avatar-black.svg.png",\r
  "address": "Hamburger Strasse 273a, 38114 Braunschweig, Germany",\r
  "lat": 10.5211247,\r
  "lon": 52.2785658,\r
  "contact": {\r
    "phone": "+4953128769245",\r
    "twitter": "@stratum0",\r
    "ml": "normalverteiler@stratum0.org",\r
    "irc": "irc:\/\/irc.freenode.net\/#stratum0"\r
  },\r
  "open": {{{ISOPEN}}},\r
  "icon": {\r
    "open": "https:\/\/status.stratum0.org\/open_square.png",\r
    "closed": "https:\/\/status.stratum0.org\/closed_square.png"\r
  },\r
  "lastchange": {{{SINCE_EPOCH}}}\r
}\r
"""
  API_XML_FILE = API_PATH % "status.xml"
  API_XML_TEMPLATE = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\r
<status version="{{{VERSION}}}">\r
  <isOpen>{{{ISOPEN}}}</isOpen>\r
  <since>{{{SINCE}}}</since>\r
</status>\r
"""

  API_ARCHIVE_FILE = API_PATH % "archive.txt"
  API_ARCHIVE_TEMPLATE = "{{{ACTION}}}: {{{SINCE}}}\r\n"

  VERSION = "0.1"   ### Bump this for new Open/Close API versions

  WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

  def __init__(self, irc):
    self.__parent = super(StratumMonitor, self)
    self.__parent.__init__(irc)

    self.isOpen = False
    self.since = datetime.now()

  def topicTimeString(self, date):
    return "%s, %s" % (self.WEEKDAYS[date.weekday()], date.strftime("%H:%M"))

  def replaceVariables(self, text):
    text = text.replace("{{{VERSION}}}", self.VERSION)
    text = text.replace("{{{SINCE}}}", self.since.isoformat())
    text = text.replace("{{{SINCE_EPOCH}}}",
      str(int(time.mktime(self.since.timetuple()))))
    text = text.replace("{{{ISOPEN}}}", "true" if self.isOpen else "false")
    text = text.replace("{{{STATUS}}}", "open" if self.isOpen else "closed")
    text = text.replace("{{{ACTION}}}", "Opened" if self.isOpen else "Closed")
    return text

  def writeFile(self, filename, template, append=False):
    mode = "a" if append else "w"
    with open(filename, mode) as f:
      self.log.info("writing to file %s" % filename)
      t = self.replaceVariables(template)
      f.write(t)

  def writeFiles(self):
    self.writeFile(self.NGINX_SITE_FILE, self.NGINX_SITE_TEMPLATE)
    self.writeFile(self.API_TEXT_FILE, self.API_TEXT_TEMPLATE)
    self.writeFile(self.API_JSON_FILE, self.API_JSON_TEMPLATE)
    self.writeFile(self.API_XML_FILE, self.API_XML_TEMPLATE)
    self.writeFile(self.API_ARCHIVE_FILE, self.API_ARCHIVE_TEMPLATE, True)
    r = os.system("sudo killall -HUP nginx"); # NOTE: must be in sudoers to do that!

  def spaceopen(self, irc, msg, args, nick):
    """
    This command is for internal use only. Any unauthorized use is prohibited.
    If you use it anyhow, this command will eat your dog, fry it and quarter it
    (in exactly this order). If you have no dog, it will take the Nyan cat
    instead.
    """
    self.since = datetime.now()
    self.isOpen = True;
    self.writeFiles()
    n = nick if nick else msg.nick
    irc.reply("Space ist offen (%s, %s)" %
      (self.topicTimeString(self.since), n), prefixNick = False)

  spaceopen = wrap(spaceopen, [optional('text')])

  def spaceclosed(self, irc, msg, args):
    """
    This command is for internal use only. Any unauthorized use is prohibited.
    If you use it anyhow, this command will eat your dog, fry it and quarter it
    (in exactly this order). If you have no dog, it will take the Nyan cat
    instead.
    """
    self.since = datetime.now()
    self.isOpen = False;
    self.writeFiles()
    irc.reply("Space ist zu (%s)" % self.topicTimeString(self.since),
      prefixNick = False)

  spaceclosed = wrap(spaceclosed)

  def spacestatus(self, irc, msg, args):
    if(self.isOpen):
      irc.reply("Space ist offen (%s)" % self.topicTimeString(self.since))
    else:
      irc.reply("Space ist zu (%s)" % self.topicTimeString(self.since))

  spacestatus = wrap(spacestatus)

Class = StratumMonitor

# vim:set shiftwidth=2 softtabstop=2 expandtab textwidth=79:
