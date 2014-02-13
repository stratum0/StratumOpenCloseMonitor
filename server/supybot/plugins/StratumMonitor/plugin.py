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
import supybot.ircmsgs as ircmsgs
import supybot.ircutils as ircutils
import supybot.callbacks as callbacks
import socket as sock

class StratumMonitor(callbacks.Plugin):
  """Stratum 0 Open/Close Monitor"""
  pass

  NGINX_SITE_FILE = "/etc/nginx/sites-enabled/status.stratum0.org"
  NGINX_SITE_TEMPLATE = """server {
  root /srv/status.stratum0.org;
  index index.html index.htm;
  access_log off;

  location / {
    rewrite ^/status.png$ https://$http_host/{{{STATUS}}}.png redirect;
    rewrite ^/favicon.ico$ https://$http_host/{{{STATUS}}}.ico redirect;
    #rewrite ^/status.png$ $scheme://$http_host/{{{STATUS}}}.png redirect;
    #rewrite ^/favicon.ico$ $scheme://$http_host/{{{STATUS}}}.ico redirect;
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
OpenedBy: {{{OPENER}}}\r
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
  "openedBy": "{{{OPENER}}}",\r
  \r
  "api": "0.13",\r
  "space": "Stratum 0",\r
  "url": "https://stratum0.org",\r
  "logo": "https://stratum0.org/mediawiki/images/thumb/c/c6/Sanduhr-twitter-avatar-black.svg/240px-Sanduhr-twitter-avatar-black.svg.png",\r
  "location": {\r
    "address": "Hamburger Strasse 273a, Haus A2, 38114 Braunschweig, Germany",\r
    "lon": 10.5211247,\r
    "lat": 52.2785658\r
  },\r
  "contact": {\r
    "phone": "+49 531 287 69 245",\r
    "twitter": "@stratum0",\r
    "email": "kontakt@stratum0.org",\r
    "ml": "normalverteiler@stratum0.org",\r
    "issue_mail": "cm9oaWViK3NwYWNlYXBpLWlzc3Vlc0Byb2hpZWIubmFtZQ==",\r
    "irc": "irc://chat.freenode.net/#stratum0",\r
    "foursquare": "4f243fd0e4b0b653a35e3ae4"\r
  },\r
  "issue_report_channels": [\r
    "issue_mail"\r
  ],\r
  "state": {\r
    "open": {{{ISOPEN}}},\r
    "icon": {\r
      "open": "http://status.stratum0.org/open_square.png",\r
      "closed": "http://status.stratum0.org/closed_square.png"\r
    },\r
    "trigger_person": "{{{OPENER}}}",
    "lastchange": {{{SINCE_EPOCH}}}\r
  },\r
  "feeds": {\r
    "blog": {\r
      "type": "atom",\r
      "url": "https://stratum0.org/blog/atom.xml"\r
    },\r
    "wiki": {\r
      "type": "atom",\r
      "url": "https://stratum0.org/mediawiki/index.php?title=Spezial:Letzte_%C3%84nderungen&feed=atom"\r
    },\r
    "calendar": {\r
      "type": "ical",\r
      "url": "https://stratum0.org/calendar/events.ics"\r
    }\r
  }\r
}\r
"""
  API_XML_FILE = API_PATH % "status.xml"
  API_XML_TEMPLATE = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\r
<status version="{{{VERSION}}}">\r
  <isOpen>{{{ISOPEN}}}</isOpen>\r
  <openedBy>{{{OPENER}}}</openedBy>\r
  <since>{{{SINCE}}}</since>\r
</status>\r
"""

  API_HTML_FILE = API_PATH % "status.html"
  API_HTML_TEMPLATE = """<?xml version="1.0" ?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>Stratum 0 Space Status</title></head>
<body>
  <h1>Stratum 0 Space Status</h1>
  <img src="//status.stratum0.org/status.png" alt="{{{STATUS}}}" />
  <p>{{{ACTION}}} since {{{SINCE}}}</p>
  <p><a href="https://stratum0.org/wiki/Open/Close-Monitor">More information</a>
  </p>
</body></html>"""

  API_ARCHIVE_FILE = API_PATH % "archive.txt"
  API_ARCHIVE_TEMPLATE = "{{{ACTION}}}: {{{SINCE}}}\r\n"

  LOCAL_HTML_FILE = API_PATH % "status-local.html"
  LOCAL_HTML_OPEN_FILE = API_PATH % "open-local.html"
  LOCAL_HTML_CLOSED_FILE = API_PATH % "closed-local.html"

  VERSION = "0.1"   ### Bump this for new Open/Close API versions

  WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

  def __init__(self, irc):
    self.__parent = super(StratumMonitor, self)
    self.__parent.__init__(irc)

    self.isOpen = False
    self.openedBy = ""
    self.since = datetime.now()
    self.presentEntities = None
    self.lastCalled = int(time.time())
    self.lastBroadcast = 0

    self.readMACs()

  def readMACs(self):
    knownMDNSs = {};
    knownMACs = {};
    self.presentEntities = ircutils.IrcSet()

    f = open("/etc/stratummonitor/known-mdns", "r")
    for line in f.readlines():
      parts = line.split("=>")
      if(len(parts) == 2):
        knownMDNSs[parts[0].strip().lower()] = parts[1].strip()
    f.close()
    self.log.info("Known mDNS hostnames: %s" % repr(knownMDNSs))

    f = open("/etc/stratummonitor/known-macs", "r")
    for line in f.readlines():
      parts = line.split("=>")
      if(len(parts) == 2):
        knownMACs[parts[0].strip().lower()] = parts[1].strip()
    f.close()
    self.log.info("Known MACs: %s" % repr(knownMACs))

    f = open("/var/run/stratummonitor-mdnsscan", "r")
    for line in f.readlines():
      scannedMDNS = line.strip().lower()
      mdns = ""

      # some avahi clients tend to prefix numbers when the hostname already
      # exists on the network
      canonicalMDNS = scannedMDNS.rstrip("1234567890").rstrip("-")
      if(scannedMDNS in knownMDNSs.keys()):
        mdns = scannedMDNS
      elif(canonicalMDNS in knownMDNSs.keys()):
        self.log.info("canonicalize %s => %s" % (scannedMDNS, canonicalMDNS))
        mdns = canonicalMDNS

      if(mdns != ""):
        self.log.info("got mDNS hostname %s" % mdns)
        self.log.info("  this mDNS hostname belongs to user %s" % knownMDNSs[mdns])
        self.presentEntities.add(knownMDNSs[mdns])

    f.close()
    self.log.info("Present mDNSs: %s" % repr(self.presentEntities))

    f = open("/var/run/stratummonitor-netscan", "r")
    for line in f.readlines():
      scannedMAC = line.strip().lower()
      self.log.info("got mac address %s" % scannedMAC)
      if(scannedMAC in knownMACs.keys()):
        self.log.info("  this mac address belongs to user %s" % knownMACs[scannedMAC])
        self.presentEntities.add(knownMACs[scannedMAC])
    f.close()
    self.log.info("Present MACs: %s" % repr(self.presentEntities))

  def sendEventdistrPacket(self, opened):
    ip = "192.168.179.255"
    port = 31337
    s = sock.socket(sock.AF_INET, sock.SOCK_DGRAM)
    s.setsockopt(sock.SOL_SOCKET,sock.SO_BROADCAST,1)
    packet = ""
    if(opened):
      packet = b"EVENTDISTRv1;SpaceOpened"
    else:
      packet = b"EVENTDISTRv1;SpaceClosed"
    self.log.info("sending eventdistr packet")
    s.sendto(packet, (ip, port))
    s.close()

  def __call__(self, irc, msg):
    # only re-read the file every 60 seconds
    if self.lastCalled + 60 < int(time.time()):
      self.readMACs()
      self.lastCalled = int(time.time())

      chan = msg.args[0];      # FIXME: change channel!
      if(ircutils.isChannel(chan) and chan == "#stratum0" and
         chan in irc.state.channels.keys()):
        self.log.info("voices:  %s" % repr(irc.state.channels[chan].voices))
        self.log.info("present: %s" % repr(self.presentEntities))
        self.log.info("devoice  %s" % repr(irc.state.channels[chan].voices - self.presentEntities))
        self.log.info("voice:   %s\n" % repr(self.presentEntities - irc.state.channels[chan].voices))

        for nick in (irc.state.channels[chan].voices - self.presentEntities):
          irc.queueMsg(ircmsgs.devoice(chan, nick))

        for nick in (self.presentEntities - irc.state.channels[chan].voices):
          irc.queueMsg(ircmsgs.voice(chan, nick))

  def presentEntities(self, irc, msg, args):
    if(len(self.presentEntities) != 0):
      irc.reply(", ".join(self.presentEntities), prefixNick=False)
    else:
      irc.reply("No one is here but me. :-(", prefixNick=False)

  weristda = wrap(presentEntities)

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
    text = text.replace("{{{OPENER}}}", self.openedBy)
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
    self.writeFile(self.API_HTML_FILE, self.API_HTML_TEMPLATE)
    self.writeFile(self.API_ARCHIVE_FILE, self.API_ARCHIVE_TEMPLATE, True)
    
    if(self.isOpen):
      r = os.system("rm %s; ln -s %s %s" % (self.LOCAL_HTML_FILE,
        self.LOCAL_HTML_OPEN_FILE, self.LOCAL_HTML_FILE))
    else:
      r = os.system("rm %s; ln -s %s %s" % (self.LOCAL_HTML_FILE,
        self.LOCAL_HTML_CLOSED_FILE, self.LOCAL_HTML_FILE))
    
    r = os.system("sudo killall -HUP nginx"); # NOTE: must be in sudoers to do that!

  def spaceopen(self, irc, msg, args, nick):
    """
    This command is for internal use only. Any unauthorized use is prohibited.
    If you use it anyhow, this command will eat your dog, fry it and quarter it
    (in exactly this order). If you have no dog, it will take the Nyan cat
    instead.

    If you still need to use this: this command sets the hackerspace status to
    open and updates the API files. It returns a string which can be pasted to
    the channel topic. There is one optional parameter which specifies the nick
    name of the one who is to blame for the open command. If this parameter is
    empty, the nick of the caller is used instead.
    """
    self.since = datetime.now()
    self.isOpen = True;
    self.openedBy = nick if nick else msg.nick
    self.writeFiles()
    self.sendEventdistrPacket(True)
    irc.reply("Space ist offen (%s, %s)" %
      (self.topicTimeString(self.since), self.openedBy), prefixNick = False)

  spaceopen = wrap(spaceopen, [optional('text')])

  def spaceclosed(self, irc, msg, args):
    """
    This command is for internal use only. Any unauthorized use is prohibited.
    If you use it anyhow, this command will eat your dog, fry it and quarter it
    (in exactly this order). If you have no dog, it will take the Nyan cat
    instead.

    If you still need to use this: this command sets the hackerspace status to
    closed and updates the API files. It returns a string which can be pasted to
    the channel topic.
    """
    self.since = datetime.now()
    self.isOpen = False;
    self.openedBy = ""
    self.writeFiles()
    self.sendEventdistrPacket(False)
    irc.reply("Space ist zu (%s)" % self.topicTimeString(self.since),
      prefixNick = False)

  spaceclosed = wrap(spaceclosed)

  def spacestatus(self, irc, msg, args):
    if(self.isOpen):
      irc.reply("Space ist offen (%s)" % self.topicTimeString(self.since))
    else:
      irc.reply("Space ist zu (%s)" % self.topicTimeString(self.since))

  spacestatus = wrap(spacestatus)

  def spacebroadcast(self, irc, msg, args, argstring):
    """ [<text>]
    Test function
    """
    now = int(time.time())
    #now = int(time.mktime(datetime.now().timetuple()))
    self.log.info("last: %d" % self.lastBroadcast);
    self.log.info("now:  %d" % now);
    if(now < 60*3 + self.lastBroadcast):
      irc.reply("Sorry, flood limit of 3 minutes.")
    else:
      params = argstring[0].replace(" ", "+")
      os.spawnl(os.P_NOWAIT, "/usr/bin/mplayer", "mplayer",
        "http://translate.google.com/translate_tts?tl=de&q=Ein+Brief+von+Prinzessin+Celestia.+%s" % params, "-ao",
        "pulse:spacekiste.local")
      #os.spawnl(os.P_NOWAIT, "/usr/bin/mplayer", "mplayer",
      #  "http://tts-api.com/tts.mp3?q=i+r+c+broadcast+%s" % params, "-ao",
      #  "pulse:spacekiste.local")
      #os.spawnl(os.P_NOWAIT, "/usr/bin/mplayer", "mplayer",
      #  "http://tts-api.com/tts.mp3?q=i+r+c+broadcast+%s" % params, " ")
      irc.replySuccess()
      self.lastBroadcast = int(time.time())

  spacebroadcast = wrap(spacebroadcast, [many('text')])

Class = StratumMonitor

# vim:set shiftwidth=2 softtabstop=2 expandtab textwidth=79:
