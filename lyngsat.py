#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Lyngsat Grabber, downloads all available satellites and creates sattelite.xml
"""
from __future__ import print_function
import re
import sys
import time
import argparse
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter

__author__ = "Athanasios Oikonomou"
__copyright__ = "Copyright 2018, OpenPLi"
__credits__ = ["Huevos"]
__license__ = "GPL"
__version__ = "1.0.0"

POLARISATION = {'H': 0, 'V': 1, 'L': 2, 'R': 3}
SYSTEMS = {'DVB-S': 0, 'DVB-S2': 1, 'DSS': -1, 'ISDB': -1,
           'Digicipher 2': -1, 'ABS': -1}
FECS = {'auto': 0, '1/2': 1, '2/3': 2, '3/4': 3, '5/6': 4, '7/8':
        5, '8/9': 6, '3/5': 7, '4/5': 8, '9/10': 9, '6/7': 10, 'none': 15}
MODULATIONS = {'auto': 0, 'QPSK': 1, '8PSK':2, 'QAM16': 3, '16APSK': 4,
               '32APSK': 5, '8PSK Turbo': -1, 'Turbo': -1}
SLEEP_TIMEOUT = 10
PARSER = 'html5lib'

SESSION = requests.Session()
SESSION.mount('http://', HTTPAdapter(max_retries=5))
SESSION.mount('https://', HTTPAdapter(max_retries=5))
SESSION.headers.update({'User-Agent': 'Mozilla/5.0'})

IS_PY3 = sys.version_info >= (3, 0)


def eprint(*args, **kwargs):
    """ print data in std error """
    print(*args, file=sys.stderr, **kwargs)


def escape(title):
    """ xml escape title """
    title = title.replace('&', '&amp;').replace('<', '&lt;')
    return title.replace('>', '&gt;').replace('\"', '&quot;')


def root2gold(root):
    """ root2gold python port based on
    http://github.com/OpenPLi/enigma2/blob/develop/lib/dvb/db.cpp#L27
    """
    if root < 0 or root > 0x3ffff:
        return 0
    ggg = 0
    xxx = 1
    while ggg < 0x3ffff:
        if root == xxx:
            return ggg
        xxx = (((xxx ^ (xxx >> 7)) & 1) << 17) | (xxx >> 1)
        ggg += 1
    return 0


class Lyngsat(object):
    """
    This class is responsible to perform parsing of lyngsat main site
    """
    __satlist = ['asia', 'europe', 'atlantic', 'america']

    def __init__(self, satlist=None, urls=None, feeds=False):
        """ We can create a Lyngsat without any parameters and it will
        automatically parse all regions and satellites.
        Alternatively we can specify regions in argument satlist and it will
        parse only the specified regions.
        Finally we can specify urls and it will ignore satlist and will
        parse satellites on this url.

        Args:
            satlist (:obj:`list` of :obj:`str`): list of satellites to parse.
            urls (:obj:`list` of :obj:`str`): list of urls to parse.
        """
        self.allsat = []
        self.urls = []
        self.feeds = feeds
        if urls:
            self.__satlist = ['none']
            self.urls = urls
        elif satlist:
            self.__satlist = satlist
            self.urls = self.get_urls()
        self.__process_urls()

    @property
    def satlist(self):
        """ returns the current satlist regions """
        return self.__satlist

    def save(self, filename):
        """ saves the satellites xml to the given file """
        if filename == '-':
            print(str(self))
        else:
            open(filename, "w").write(str(self))

    def get_urls(self):
        """ returns all url parsed on the given regions """
        valid_colors = ['#cccc66', '#ded9ac', 'khaki']
        td_filter = {'width': '70', 'bgcolor': valid_colors}
        urls = []
        for region in self.__satlist:
            eprint('Getting %s region...' % region)
            url = 'http://www.lyngsat.com/' + region + '.html'
            res = SESSION.get(url)
            page = BeautifulSoup(res.text, PARSER)
            for tds in page.find_all('td', td_filter):
                urls.append(tds.find('a')['href'])
            time.sleep(SLEEP_TIMEOUT)
        return urls

    def __process_urls(self):
        """ it prossesing urls and appends results on allsat list """
        cnt = len(self.urls)
        urls = list(self.urls)
        for idx, url in enumerate(urls, 1):
            eprint('Getting %s ... (%d of %d)' % (url, idx, cnt))
            try:
                sats = Satellites(url, self.feeds)
            except requests.exceptions.ConnectionError as cer:
                urls.append(url)
                eprint('[WARN] ConnectionError occured %s, will retry %s later...' % (str(cer), url))
                time.sleep(SLEEP_TIMEOUT + SLEEP_TIMEOUT)
                continue
            eprint(repr(sats))
            for sat in sats:
                eprint(repr(sat))
                self.allsat.append(sat)
            time.sleep(SLEEP_TIMEOUT)  # don't overload lyngsat

    def __repr__(self):
        params = ('-'.join(self.__satlist), len(self.urls), len(self.allsat))
        return 'Lyngsat(regions=%s, urls=%d, satellites=%d)' % params

    def __str__(self):
        time_created = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
        tmp_xml = []
        tmp_xml.append('<?xml version="1.0" encoding="UTF-8"?>')
        tmp_xml.append('<!--')
        tmp_xml.append('    lyngsat grabber %s' % __version__)
        tmp_xml.append('    File created on %s' % time_created)
        tmp_xml.append('    BeautifulSoup Parser %s' % PARSER)
        tmp_xml.append('    %s' % repr(self))
        tmp_xml.append('-->')
        tmp_xml.append('<satellites>')
        for sat in sorted(self.allsat, key=lambda s: (s.position)):
            tmp_xml.append(str(sat))
        tmp_xml.append('</satellites>\n')
        return '\n'.join(tmp_xml)


class Satellite(object):
    """
    This class holds the data for a signle satellite including transponders
    """

    def __init__(self, name, position, transponders):
        self.__name = name
        self.__position = position
        self.transponders = set(transponders)
        self.dupl = len(transponders) - len(self.transponders)

    @property
    def name(self):
        """ return satellite name """
        return self.__name

    @property
    def position(self):
        """ return satellite position """
        return self.__position

    def __repr__(self):
        feeds = len([x for x in self.transponders if x.is_feed])
        params = (self.name, self.position, len(self.transponders), feeds, self.dupl)
        return 'Satellite(name=%s, position=%d, transponders=%d, feeds=%d, duplicates=%d)' % params

    def __str__(self):
        tmp = []
        tmp.append('\t<sat name="%s" flags="1" position="%d">' %
                   (escape(self.name), self.position))
        keys = lambda t: (t.freq, t.symbol_rate, t.pol, t.fec, t.system,
                          t.modulation, t.is_id, t.pls_code, t.t2mi_plp_id)
        for tpr in sorted(self.transponders, key=keys):
            tmp.append(str(tpr))
        tmp.append('\t</sat>')
        return '\n'.join(tmp)


class Satellites(object):
    """
    Parse satellites on the given URL handling the fixed positions
    """
    __fixed = (-580, -555, -530, -500, -450, -431, -405, -375, -345, -315,
               -300, -275, -245, -220, -200, -180, -150, -125, -110, -80, -70,
               -50, -40, -8, 30, 48, 70, 90, 100, 130, 160, 170, 192, 200,
               216, 235, 255, 260, 282, 305, 315, 360, 390, 420, 450, 490,
               530, 549, 560, 570)

    def __init__(self, url, feeds):
        self.url = url
        self.feeds = feeds
        self.feed_num = 0
        self.transponders = {}
        self.tp_num = 0
        self.name = ''
        self.position = 0
        res = SESSION.get(url)
        page = BeautifulSoup(res.text, PARSER)
        self.__get_name_position(page)
        for all_tr in page.find_all('tr'):
            all_td = all_tr.find_all('td')
            tpr = Transponder(all_td)
            if not tpr.is_valid:
                continue
            if tpr.is_feed:
                self.feed_num += 1
                if not self.feeds:
                    continue
            band = tpr.band
            if band not in self.transponders:
                self.transponders[band] = []
            self.transponders[band].append(tpr)
            self.tp_num += 1

    @property
    def is_multiband(self):
        """ returns true when satellite contains more than one band """
        return len(self.transponders.keys()) > 1

    def __get_name_position(self, page):
        """ parse satellite name and position """
        title = page.find('title').text
        regexp = r'(.*) at (\d+\.\d+|\d+)°(W|E) - LyngSat'
        match = re.search(regexp, title if IS_PY3 else title.encode('utf-8'))
        pos = self.position
        if match:
            self.name = match.group(1)
            pos = int(float(match.group(2)) * (
                -10 if match.group(3) == 'W' else 10))
        # check for fixed positions
        fixed = lambda x: pos <= x + 3 and pos >= x - 3
        self.position = next(iter([x for x in self.__fixed if fixed(x)]), pos)

    def __get_satellites(self):
        """ return parsed satellites under a signle position """
        for band in self.transponders:
            yield Satellite(self.get_name(band), self.get_band_offset(band),
                            self.transponders[band])

    def get_name(self, band):
        """" returns the satellite name for the given band """
        tmp_name = []
        tmp_name.append('%.1f%s' % (float(abs(self.position) / 10.0),
                                    'E' if self.position > 0 else 'W'))
        if self.is_multiband or band != 'Ku':
            tmp_name.append('%s-band' % band)
        tmp_name.append(self.name)
        return ' '.join(tmp_name)

    def get_band_offset(self, band):
        """"
        returns the band offset in order not to have gray channels when
        multiband sat changes Ku > C > Ka on East or Ku < C < Ku on West
        """
        offset = {'Ku': 0, 'C': 1, 'Ka': 2, 'L': -2, 'S': -2}.get(
            band, 3) * (1 if self.position > 0 else -1)
        return self.position + offset

    def __iter__(self):
        for sat in sorted(self.__get_satellites(), key=lambda s: (s.position)):
            yield sat

    def __repr__(self):
        bands = ' '.join(self.transponders.keys())
        params = (self.name, self.position, bands, self.tp_num, self.feed_num)
        return 'Satellites(name=%s, position=%d, bands=%s, transponders=%d, feeds=%d)' % params

    def __str__(self):
        return '\n'.join([str(s) for s in self])


class Transponder(object):
    """
    This class is responsible to parse transponder details from the given row
    """
    __is_valid = True
    __is_feed = False

    def __init__(self, values):
        if len(values) != 9:
            self.__is_valid = False
            return
        if not values[1].find('b'):  # frequency is always bold
            self.__is_valid = False
            return
        if values[3].attrs.get('bgcolor','') in ('#d0d0d0', '#ffaaff'): # feed, internet/interactive
            self.__is_feed = True
        self.modulation = 1  # Modulation_QPSK
        self.system = 0  # System_DVB_S
        self.freq = 0
        self.symbol_rate = 0
        self.pol = -1
        self.fec = 0  # FEC_Auto
        self.is_id = -1  # NO_STREAM_ID_FILTER
        self.pls_code = 0
        self.pls_mode = 1  # PLS_Gold
        self.t2mi_plp_id = -1  # not used by e2 yet
        # process values
        self.__get_frequency_polarisation(values)
        self.__get_system_mis_pls(values)
        self.__get_symbolrate_fec_modulation(values)
        if self.__is_valid:
            self.__is_valid = self.freq > 0 and self.symbol_rate > 0
        if self.modulation > 1 and self.system == 0:
            eprint('[FIXME] %s auto-correcting DVB-S to DVB-S2 because modulation is not QPSK' % repr(self))
            self.system = 1
        if self.system == -1: # non DVB system handle it as DVB-S feed!
            self.system = 0
            self.__is_feed = True
        if self.modulation == -1: # 8PSK Turbo handle it as feed!
            self.modulation = 0
            self.__is_feed = True

    @property
    def is_valid(self):
        """ returns true if transponder parsing succeed  """
        return self.__is_valid

    @property
    def is_feed(self):
        """ returns true if transponder is feed """
        return self.__is_feed

    @property
    def is_ka(self):
        """ returns true if frequency belongs to Ka band else false """
        return self.freq > 13000000

    @property
    def is_ku(self):
        """ returns true if frequency belongs to Ku band else false"""
        return self.freq > 10000000 and self.freq < 13000000

    @property
    def is_c(self):
        """ returns true if frequency belongs to C band else false """
        return self.freq > 3000000 and self.freq < 5000000

    @property
    def is_s(self):
        """ returns true if frequency belongs to S band else false """
        return self.freq > 2000000 and self.freq < 3000000

    @property
    def is_l(self):
        """ returns true if frequency belongs to L band else false """
        return self.freq > 1000000 and self.freq < 1700000

    @property
    def band(self):
        """ returns the band name X for unknown band """
        if self.is_ku:
            return 'Ku'
        elif self.is_c:
            return 'C'
        elif self.is_ka:
            return 'Ka'
        elif self.is_s:
            return 'S'
        elif self.is_l:
            return 'L'
        else:
            return 'X'

    def __get_frequency_polarisation(self, values):
        """ parse frequency and polarisation from the first column of row """
        freq_pol = values[1].find_all(text=True)
        if len(freq_pol) < 1:
            return
        if freq_pol[0][-1] in POLARISATION.keys():
            freq, pol = freq_pol[0].split()
        elif freq_pol[0][-1] == '.':
            freq = freq_pol[0] + freq_pol[1]
            pol = ''.join(freq_pol[2].split())
        else:
            freq, pol = (0, 0)
            eprint('[FIXME] getFrequencyPolarisation: %s' % freq_pol)
        self.freq = int(round(float(freq) * 1000))
        self.pol = POLARISATION.get(pol, 0)

    def __get_system_mis_pls(self, values):
        """ parse the system, mis, pls and plp from the fifth column of row """
        smp = values[5].find_all(text=True)
        if len(smp) < 1:
            return
        self.system = SYSTEMS.get(smp[0], 0)
        safeint = lambda i: int(''.join(c for c in i if c.isdigit()))
        for line in smp[1:]:
            if 'stream ' in line:
                self.is_id = safeint(line[7:])
            elif 'PLS gold ' in line:
                self.pls_code = safeint(line[9:])
            elif 'PLS root ' in line:
                self.pls_code = root2gold(safeint(line[9:]))
            elif 'PLP ' in line:
                self.t2mi_plp_id = safeint(line[4:])

    def __get_symbolrate_fec_modulation(self, values):
        """
        parse the symbol rate and fec and modulation from the 6th column of row
        """
        sfm = values[6].find_all(text=True)
        if len(sfm) < 1:
            return
        if '-' in sfm[0]:
            srate, fec = sfm[0].split('-')
            self.symbol_rate = int(srate) * 1000
            self.fec = FECS.get(fec, 0)
        if len(sfm) >= 2:
            self.modulation = MODULATIONS.get(sfm[1].strip(), 1)

    def __hash__(self):
        return hash((self.freq, self.symbol_rate, self.pol, self.fec,
                     self.system, self.modulation, self.is_id, self.pls_code,
                     self.t2mi_plp_id))

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return hash(self) == hash(other)
        else:
            return False

    def __repr__(self):
        rev = lambda d, v: d.keys()[d.values().index(v)]
        spol = rev(POLARISATION, self.pol)
        ssys = rev(SYSTEMS, self.system)
        sfec = rev(FECS, self.fec)
        smod = rev(MODULATIONS, self.modulation)
        params = (self.freq/1000.0, spol, ssys, self.symbol_rate/1000, sfec,
                  smod, self.is_id, self.pls_code, self.t2mi_plp_id)
        return 'Transponder(%g %s %s SR %d %s %s MIS %d Gold %d T2MI %d)' % params

    def __str__(self):
        if not self.__is_valid:
            return ''
        tmp_tp = []
        tmp_tp.append('\t\t<transponder')
        tmp_tp.append('frequency="%d"' % self.freq)
        tmp_tp.append('symbol_rate="%d"' % self.symbol_rate)
        tmp_tp.append('polarization="%d"' % self.pol)
        tmp_tp.append('fec_inner="%d"' % self.fec)
        tmp_tp.append('system="%d"' % self.system)
        tmp_tp.append('modulation="%d"' % self.modulation)
        if self.is_id > -1:
            tmp_tp.append('is_id="%d"' % self.is_id)
        if self.pls_code > 0:
            tmp_tp.append('pls_mode="%d"' % self.pls_mode)
            tmp_tp.append('pls_code="%s"' % self.pls_code)
        if self.t2mi_plp_id > -1:
            tmp_tp.append('t2mi_plp_id="%d"' % self.t2mi_plp_id)
        tmp_tp.append('/>')
        return ' '.join(tmp_tp)


def cli_args():
    """ Parse cli arguments """
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument('-u', '--url', nargs='*',
                       default=[], help='list of urls to generate xml file')
    group.add_argument('-r', '--region', nargs='*',
                       default=['asia', 'europe', 'atlantic', 'america'],
                       help='list of regions to generate xml file')
    parser.add_argument('-f', '--filename', default='satellites.xml',
                        help='filename to store resulting xml file, for stdout -')
    parser.add_argument('--with-feeds', action='store_true',
                        help='Include feeds in resulting xml file')

    return parser.parse_args()


def main():
    """ main program """
    args = cli_args()
    lyngsat_parser = Lyngsat(satlist=args.region, urls=args.url, feeds=args.with_feeds)
    eprint(repr(lyngsat_parser))
    lyngsat_parser.save(args.filename)


if __name__ == "__main__":
    main()
