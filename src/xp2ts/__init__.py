# Example package with a console entry point

#!/usr/bin/env python
# -*- coding:utf-8 -*-
# for a complete reference, go to http://doc.sd.ivao.aero/da:whazzup:desc#whazzup_file_format


import gzip

from math import radians, sin, cos, atan2, sqrt
from os import path, remove as remove_file
from tempfile import mkstemp
from urllib2 import urlopen
from time import time, ctime, sleep
from threading import Timer, BoundedSemaphore
from sys import float_info
from random import choice
from string import Template
from abc import ABCMeta, abstractmethod
from getpass import getpass

try:
    from ConfigParser import ConfigParser
except:
    from configparser import ConfigParser

import logging

logging.basicConfig()
log = logging.getLogger(__name__)
log.setLevel(logging.WARN)

__STATUS_URL__ = "http://www.ivao.aero/whazzup/status.txt" # w/out this, we are dead.
__STATUS_MSG0__ = 'msg0'
__STATUS_URL0__ = 'url0'
__STATUS_URL1__ = 'url1'
# REMEMBER: prefer zipped content.
__STATUS_GZURL0__ = 'gzurl0'

# the following keys are all marked 'Deprecated' in docs.

__STATUS_METAR0__ = 'metar0'
__STATUS_TAF0__ = 'taf0'
__STATUS_SHORTTAF0__ = 'shorttaf0'
__STATUS_USER0__ = 'user0'
__STATIS_ATIS0__ = 'atis0'

# Whazzup file format keys
__WZ_SECTION_TOKEN__ = '!'
__WZ_GENERAL__ = ''.join([__WZ_SECTION_TOKEN__, 'GENERAL'])
__WZ_CLIENTS__ = ''.join([__WZ_SECTION_TOKEN__, 'CLIENTS'])
__WZ_SERVERS__ = ''.join([__WZ_SECTION_TOKEN__, 'SERVERS'])
__WZ_AIRPORTS__ = ''.join([__WZ_SECTION_TOKEN__, 'AIRPORTS'])

## Enumerations:

__ATC__ = 'ATC'
__PILOT__ = 'PILOT'
__FOLLOW_ME__ = 'FOLME'
__UNICOM__ = "122.800"
__GUARD__ = "121.500"

__CLIENT_TYPE__ = { __ATC__ : "ATC or Observer connections",
                    __PILOT__ : "Pilot connections",
                    __FOLLOW_ME__: "Follow Me Car connections" }

__FACILITY_TYPE__ = {
    "0":"Observer",
    "1":"Flight Information",
    "2":"Delivery",
    "3":"Ground",
    "4":"Tower",
    "5":"Approach",
    "6":"ACC",
    "7":"Departure" }

__ADMINISTRATIVE_RATING__ = {
    "0":"Suspended",
    "1":"Observer",
    "2":"User",
    "11":"Supervisor",
    "12":"Administrator",
}

__PILOT_RATING__ = {
    "1":"Observer",
    "2":"Basic Flight Student (FS1)",
    "3":"Flight Student (FS2)",
    "4":"Advanced Flight Student (FS3)",
    "5":"Private Pilot (PP)",
    "6":"Senior Private Pilot (SPP)",
    "7":"Commercial Pilot (CP)",
    "8":"Airline Transport Pilot (ATP)",
    "9":"Senior Flight Instructor (SFI)",
    "10":"Chief Flight Instructor (CFI)",
}

__FLIGHT_SIMULATORS__ = {
    "0":"Unknown",
    "1":"Microsoft Flight Simulator 95",
    "2":"Microsoft Flight Simulator 98",
    "3":"Microsoft Combat Flight Simulator",
    "4":"Microsoft Flight Simulator 2000",
    "5":"Microsoft Combat Flight Simulator 2",
    "6":"Microsoft Flight Simulator 2002",
    "7":"Microsoft Combat Flight Simulator 3",
    "8":"Microsoft Flight Simulator 2004",
    "9":"Microsoft Flight Simulator X",
    "11":"X-Plane (unknown version)",
    "12":"X-Plane 8.x",
    "13":"X-Plane 9.x",
    "14":"X-Plane 10.x",
    "15":"PS1",
    "16":"X-Plane 11.x",
    "17":"X-Plane 12.x",
    "20":"Fly!",
    "21":"Fly! 2",
    "25":"FlightGear",
    "30":"Prepar3D 1.x ",
}

__WZ_CLIENT_KEYS__ = [x.strip() for x in
    """callsign
    vid
    name
    client_type
    frequency
    latitude
    longitude
    altitude
    groundspeed
    fp_aircraft
    fp_cruise_speed
    fp_departure
    fp_cruise_level
    fp_destination
    server
    protocol
    combined_rating
    transponder_code
    facility_type
    visual_range
    fp_revision
    fp_flight_rules
    fp_departure_time
    fp_actual_departure_time
    fp_endurance_hours
    fp_endurance_mins
    fp_eet_hours
    fp_eet_mins
    fp_alternate
    fp_other_info
    fp_route
    _unused0_
    _unused1_
    d1
    d6
    atis
    atis_time
    connection_time
    software_name
    software_version
    administrative_version
    atc/pilot_version
    fp_second_alternate
    fp_type_of_flight
    fp_persons_on_board
    heading
    on_ground
    simulator
    plane""".split('\n')] ## __WZ_CLIENT_KEYS__

    # I have absplutely NO idea on why I had to introduce d1 and d2 on this list. Apparently
    # data coming from IVAO contains those fields not documented.

__WZ_SERVER_KEYS__ = [ x.strip() for x in"""ident
    address
    location
    name
    connections_allowed
    max_connections
    """.split('\n')]

__WZ_AIRPORT_KEYS = [ x.strip() for x in """icao
    atis
    """.split('\n')]


## TS specific commands
__TS_CONTROL__ = "tsControl"
__TS_CONNECT_URL__ = "CONNECT TeamSpeak://"
__TS_DISCONNECT__ = "DISCONNECT"
__TS_LOGIN_URL_TEMPLATE__ = '?nickname="$nickane"?loginname="$loginname"?password="$password"?channel="$channel"'

log.debug("Number of keys for __WZ_CLIENT_KEYS__: %d" % len(__WZ_CLIENT_KEYS__))

def _parse_general(line, container=None):
    if(container is not None):
        log.debug(line)
        key, value = [x.strip().lower().replace(' ','_') for x in line.split('=')]
        if not hasattr(container, key):
            setattr(container, key, value)
        else:
            new_key = key+'_'
            log.debug("container has already a %s property, new name: %s" % (key, new_key))
            setattr(container, new_key, value)

def _parse_clients(line, container=None):
    values = line.split(':')
    client = dict(zip(__WZ_CLIENT_KEYS__, values))
    if container is not None:
        container.clients[client["callsign"]]=client

    return client

def _parse_servers(line, container):
    values = line.split(':')
    server = dict(zip(__WZ_SERVER_KEYS__, values))
    if container is not None:
        container.servers[server['ident']] = server


def _parse_airports(line, container):
    values = line.split(':')
    airport = dict(zip(__WZ_AIRPORT_KEYS__, values))
    if container is not None:
        container.airports[airport['icao']] = airport


_wz_parse_handlers = {__WZ_GENERAL__ : _parse_general,
                  __WZ_CLIENTS__ : _parse_clients,
                  __WZ_SERVERS__ : _parse_servers,
                  __WZ_AIRPORTS__ : _parse_airports}



# Useful CONSTANTS
__DAY_IN_SECONDS__ = 24 * 60 * 60

class WebPoller(object):
    """this class polls the web every 'period' to retrieve the specified resource, and notifies observers
    Eg:

    >>> poller = WebPoller("http://www.google.com", 60)
    >>> observer = ... # random object with def update(self, content) defined
    >>> poller.add_observer(observer)
    >>> poller.poll()

    will poll Google every 60 seconds and notify observer about it...

    >>> poller.stop()

    to stop the poller

    """
    def __init__(self, url, period, gzipped=False):
        self.url = url
        self.period = period
        self._lock = BoundedSemaphore(1)
        self._resource = None
        self._gzipped = gzipped
        self._last_accessed = 0
        self._observers = list()
        self._timer = None


    @property
    def resource(self):
        self._lock.acquire()
        try:
            return self._resource
        finally:
            self._lock.release()

    @resource.setter
    def resource(self, value):
        self._resource=value



    def _download(self):
        self._lock.acquire()
        try:
            self._resource = None
            log.debug("downloading stuff from %s" % self.url)
            self._resource = urlopen(self.url).read()
            # log.debug("raw contents: %s" % self._resource)
            if self._gzipped :
                log.debug("decompress contents")
                try:
                    fid, tmpfile = mkstemp()
                    log.debug(tmpfile)
                    with open(tmpfile, 'wb') as f:
                        f.write(self._resource)

                    with gzip.open(tmpfile, 'rb') as f:
                        self._resource = f.read()

                finally:
                    remove_file(tmpfile)

            log.debug("fine download")
        finally:
            log.debug("rilascio sto maledetto mutex")
            self._lock.release()





    ## observer pattern
    def add_observer(self, observer):
        if not hasattr(observer, 'updateContents'):
            raise Exception("observer %s cannot be updated" % str(observer))
        if observer not in self._observers:
            self._observers.append(observer)

    ## observer pattern
    def remove_observer(self, observer):
        try:
            self._observers.remove(observer)
        except:
            pass

    ## observer pattern
    def notify(self):
        log.debug("notifying observers (%d observers)" % len(self._observers))
        for observer in self._observers:
            log.debug(observer)
            log.debug(self._resource[0:200])
            log.debug("""l'Acqua te l'ho messa,
            il sale te te l'ho dato,
            la luce non ti manca,
            il detersivo te l'ho messo,
            o manico della tiella che ti dava fastidio l'ho spostato,
            il rubinetto te l'ho aperto,
            o programma e chi t'e' muort te l'ho messo,
            che cazzo ti manca?""") # questa rimane perche' m'ha fatto troppo impazzire...
            # liberamente tratto da Cosi' parlo' Bellavista...
            observer.updateContents(self._resource)


    def poll(self):
        """ this is the running function of the thread that
        downloads the data from the WWW compliant with the
        polling constraint"""

        now = time()
        delta = now - self._last_accessed
        if delta > self.period:
            log.debug("oh well, we have something to do now...")
            self._download()
            self.notify()
            self._last_accessed = now

        self._timer = Timer(self.period, self.poll)
        self._timer.start()

    def stop(self):
        try:
            self._timer.cancel()
        except Exception as e:
            log.warn(e)


    def __del__(self):
        self.stop()
        del self._timer
        del self.url
        del self.period
        try:
            self._lock.release()
        except Exception as e:
            log.debug(e)

        del self._lock
        del self._resource

        del self._gzipped
        del self._last_accessed

        for observer in observers:
            self.remove_observer(observer)
            del observer

        del self._observers
        del self._timer

class PollableResource(object):

    __metaclass__ = ABCMeta

    def __init__(self, url, period, gzipped = False):
        self._poller = WebPoller(url, period, gzipped=gzipped)
        self._poller.add_observer(self)
        self._poller.poll()

    def updateContents(self, contents):
        log.debug("Yay! New data! Updating...")
        self.contents = contents
        log.debug("Parsing...")
        # this method must be implemented by subclasses
        self.parse()

    def stop(self):
        """ this method stops the poller to the resource"""
        self._poller.stop()


    @abstractmethod
    # this method must be implemented by subclasses
    def parse(self):
        pass

    def __del__(self):
        log.debug("called desctructor")
        self.stop()
        del self._poller


class StatusFile(PollableResource):
    """This class represents the Status file Data from IVAO servers

    A complete reference can be found here: http://doc.sd.ivao.aero/da:whazzup:status
    """
    def __init__(self):
        super(StatusFile, self).__init__(__STATUS_URL__, __DAY_IN_SECONDS__)


    def parse(self):
        content = filter(lambda line: line[0] != '#' and
                         line[0] !=';'
                         and len(line) > 0,
                         self.contents.strip().split('\n'))

        content = [line.strip() for line in content]
        # I do ignore the first line, usually "120180:TCP"
        content = content[1:]
        log.debug(content)
        for line in content:
            log.debug("line = %s" % line)
            key, value = line.split('=')
            log.debug("%s=%s" % (key,value))
            if getattr(self, key, None) is None:
                setattr(self, key, [value])
            else:
                setattr(self, key, getattr(self, key).append(value))

        if hasattr(self, __STATUS_MSG0__):
            # if msg0 is present, print it!
            log.info(self[__STATUS_MSG0__])

    def __getitem__(self, key):
        return self.__dict__[key]

    def __contains__(self, key):
        return key in self.__dict__



class WhazzupData(PollableResource):
    """This class represents the data in the whazzup.txt file downloaded from IVAO servers

    A complete reference can be found at http://doc.sd.ivao.aero/da:whazzup:desc#whazzup_file_format
    """

    def __init__(self):
        # self._status = StatusFile()
        self._status = StatusFile()
        # if __STATUS_GZURL0__ in status file, prefer those, otherwise go on __STATUS_URL0__
        if __STATUS_GZURL0__ in self._status:
            log.debug("found %s in status file" % __STATUS_GZURL0__)
            url = choice(self._status[__STATUS_GZURL0__])
            gzipped = True
        else:
            url = choice(self._status[__STATUS_URL0__])
            gzipped = False

        log.debug("url chosen %s" % url)
        super(WhazzupData, self).__init__(url, 5*60, gzipped=gzipped) # 5 minutes

    def stop(self):
        super(WhazzupData, self).stop()
        self._status.stop()

    def parse(self):
        self.clients = dict()
        self.servers = dict()
        self.airports = dict()
        self.atc_by_freq = dict()

        handler = None
        for line in self.contents.split('\n'):
            line = line.strip()
            log.debug(line)
            if len(line) == 0:
                continue

            if line[0] == __WZ_SECTION_TOKEN__:
                try:
                    handler = _wz_parse_handlers[line]
                    log.debug(handler)
                except Exception as e:
                    log.error(e)
                continue

            if handler is None:
                log.error("I dunno how to handle whazzup's line: %s" % line)
            else:
                handler(line, self)

        for ident, client in self.clients.iteritems():
            if client['client_type'] == __ATC__ :
                self.atc_by_freq[client['frequency']] = client


    def extract_atc(self, xp):
        com1_freq = xp.com1
        com1_freq2 = com1_freq[:6]+"5" #workaround needed to manage 25KHz spacing.

        ret = None
        if com1_freq in self.atc_by_freq.keys():
            ret = self.atc_by_freq[com1_freq]

        if com1_freq2 in self.atc_by_freq.keys():
            ret =  self.atc_by_freq[com1_freq2]


        # I really don't understand why we do this...
        closer_atc = None
        shortest_distance = float_info.max
        for freq, atc in self.atc_by_freq.iteritems():
            lat, lon = float(atc['latitude']), float(atc['longitude'])
            dist = distance(xp.position, (lat, lon))
            if dist < shortest_distance:
                closer_atc = atc
                shortest_distance = dist



        log.info("the nearest valid station is %s (%s)" % (closer_atc['name'], closer_atc['frequency']))
        if ret is None :
            log.warn("No Valid ATC found")

        return ret


def distance(origin, destination):
    """Evaluate the distance of two lat/long tuples
    all credits to : https://gist.github.com/rochacbruno/2883505"""
    lat1, lon1 = origin
    lat2, lon2 = destination
    # radius = 6371 # km
    radius = 3960 # miles
    dlat = radians(lat2-lat1)
    dlon = radians(lon2-lon1)
    a = sin(dlat/2) * sin(dlat/2) + cos(radians(lat1)) \
      * cos(radians(lat2)) * sin(dlon/2) * sin(dlon/2)
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    d = radius * c

    return d


class ConfigHolder(object):
    def __init__(self, config):
        self.username = config.get('info','username')
        self.password = config.get('info','password')
        self.nick = config.get('info','username')
        self.ts_path = config.get('info','ts_path')
        self.xp_path = config.get('info','xp_path')
        self.ts_control_cmd = path.join(self.ts_path, "tsControl")
        self.ts_login_template = Template(__TS_LOGIN_URL_TEMPLATE__)
        self.disconnect_on_unicom = bool(config.get('info', 'disconnect_on_unicom'))
        self.ts_prefix = " ".join([self.ts_control_cmd, __TS_CONNECT_URL__])

global config # this holds conf info for all the process..
_cfgfile = ConfigParser()
_cfgfile.read('config.ini')
global config
config = ConfigHolder(_cfgfile)

def console_cmd(cmd):
    try:
        p=subprocess.Popen(cmd,
                           shell=True,
                           stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE)
        return p.stdout.read()
    except Exception as e:
        log.error(e)
        return 0


class XPlanePluginProxy(object):
    def __init__(self, path):
        self.path = path
        self._com1 = __UNICOM__
        self._old_com1 = '' # not setting unicom to trigger the changed status

    @property
    def com1(self):
        return self._com1

    def scan_com1(self):
        try:
            with open(path.join(self.path, "com1.txt"), "r") as f:
                freq_str = com1_obj.readline()

            freq_str = freq_str.strip() # erase newline character
            freq_left = freq_str[:3]
            freq_right = freq_str[3:]+"0" # adds "0" because missing from dateref. 25KHz and 8.33KHz spacing are managed later
            freq = freq_left+"."+freq_right
        except:
            log.warn("WARNING: No Com1 data found. This is normal at the first run.")
            log.warn("We will pre-select UNICOM awating for changes from xplane")
            freq = __UNICOM__

        self._com1 = freq


        try :
            return (self.com1, self.old_com1 != self.com1)
        finally:
            self._old_com1 = self.com1



    @property
    def position():
        try:
            with open(path.join(self.path, 'latlon.txt'), 'r') as f:
                lat, lon = [float(coord) for coord in f.readlines()]
        except:
            log.warn("Location data file not found. This is normal for the first run")
            log.warn("Setting fictious (lat,lon) to (0.0,0.0)")
            lat, lon = 0.0, 0.0

        return (lat, lon)


class TeamSpeakProxy(object):
    def __init__(self, path):
        self.path=path

    def join_channel(self, server, username, password, nick, channel):
        pass

    def disconnect():
        cmd = " ".join([config.ts_control_cmd, __DISCONNECT__])
        stdout = consolecmd(cmd)
        if re.search("-1001", stdout):
            log.error("ERROR: Teamspeak is not running: no changes done")
        else:
            log.info("Disconnected")


def main():
    global config
    wz = WhazzupData()
    ts = TeamSpeakProxy(config.ts_path)
    xplane = XPlaneProxy(config.xp_path)
    try:
        while True:
            sleep(config.loop_time) # I don't wanna fry your CPU
            com1, changed = xp.scan_com1()
            if changed:
                log.info(ctime())
                if com1 == __UNICOM__ and config.disconnect_on_unicom:
                    log.info("UNICOM selected, disconnecting voice")
                    ts.disconnect()
                elif com1 == __GUARD__:
                    log.info("GUARD freq selected, no voice changes")
                else:
                    ts.join_channel(wz.extract_channel(com1))
    except KeyboardInterrupt as ki:
        log.info(ki)
    finally:
        wz.stop()

if __name__ == '__main__':
    main()
