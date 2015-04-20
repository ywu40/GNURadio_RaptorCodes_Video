#!/usr/bin/env python
#
# Copyright 2005,2006,2009,2011 Free Software Foundation, Inc.
# 
# This file is part of GNU Radio
# 
# GNU Radio is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
# any later version.
# 
# GNU Radio is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with GNU Radio; see the file COPYING.  If not, write to
# the Free Software Foundation, Inc., 51 Franklin Street,
# Boston, MA 02110-1301, USA.
# 


# ////////////////////////////////////////////////////////////////////
#
#    This code sets up up a virtual ethernet interface (typically
#    gr0), and relays packets between the interface and the GNU Radio
#    PHY+MAC
#
#    What this means in plain language, is that if you've got a couple
#    of USRPs on different machines, and if you run this code on those
#    machines, you can talk between them using normal TCP/IP
#    networking.
#
# ////////////////////////////////////////////////////////////////////


from gnuradio import gr, digital
from gnuradio import eng_notation
from gnuradio.eng_option import eng_option
from optparse import OptionParser

# from current dir
from receive_path  import receive_path
from transmit_path import transmit_path
from uhd_interface import uhd_transmitter
from uhd_interface import uhd_receiver

from raptor_encoder import *
import raptor_encoder

import os, sys
import random, time, struct
import numpy

#print os.getpid()
#raw_input('Attach and press enter')

# ////////////////////////////////////////////////////////////////////
#
#   Use the Universal TUN/TAP device driver to move packets to/from
#   kernel
#
#   See /usr/src/linux/Documentation/networking/tuntap.txt
#
# ////////////////////////////////////////////////////////////////////

# Linux specific...
# TUNSETIFF ifr flags from <linux/tun_if.h>

IFF_TUN		= 0x0001   # tunnel IP packets
IFF_TAP		= 0x0002   # tunnel ethernet frames
IFF_NO_PI	= 0x1000   # don't pass extra packet info
IFF_ONE_QUEUE	= 0x2000   # beats me ;)

def open_tun_interface(tun_device_filename):
    from fcntl import ioctl
    
    mode = IFF_TAP | IFF_NO_PI
    TUNSETIFF = 0x400454ca

    tun = os.open(tun_device_filename, os.O_RDWR)
    ifs = ioctl(tun, TUNSETIFF, struct.pack("16sH", "gr%d", mode))
    ifname = ifs[:16].strip("\x00")
    return (tun, ifname)
    

# ////////////////////////////////////////////////////////////////////
#                     the flow graph
# ////////////////////////////////////////////////////////////////////

class my_top_block(gr.top_block):

    def __init__(self, mod_class, demod_class,
                 rx_callback, options):

        gr.top_block.__init__(self)

        # Get the modulation's bits_per_symbol
        args = mod_class.extract_kwargs_from_options(options)
        symbol_rate = options.bitrate / mod_class(**args).bits_per_symbol()

        self.source = uhd_receiver(options.args, symbol_rate,
                                   options.samples_per_symbol,
                                   options.rx_freq, options.rx_gain,
                                   options.spec, options.antenna,
                                   options.verbose)
        
        self.sink = uhd_transmitter(options.args, symbol_rate,
                                    options.samples_per_symbol,
                                    options.tx_freq, options.tx_gain,
                                    options.spec, options.antenna,
                                    options.verbose)
        
        options.samples_per_symbol = self.source._sps

        self.txpath = transmit_path(mod_class, options)
        self.rxpath = receive_path(demod_class, rx_callback, options)
        self.connect(self.txpath, self.sink)
        self.connect(self.source, self.rxpath)

    def send_pkt(self, payload='', eof=False):
        return self.txpath.send_pkt(payload, eof)

    def carrier_sensed(self):
        """
        Return True if the receive path thinks there's carrier
        """
        return self.rxpath.carrier_sensed()

    def set_freq(self, target_freq):
        """
        Set the center frequency we're interested in.
        """

        self.sink.set_freq(target_freq)
        self.source.set_freq(target_freq)
        

# ////////////////////////////////////////////////////////////////////
#                           Carrier Sense MAC
# ////////////////////////////////////////////////////////////////////

class cs_mac(object):
    """
    Prototype carrier sense MAC

    Reads packets from the TUN/TAP interface, and sends them to the
    PHY. Receives packets from the PHY via phy_rx_callback, and sends
    them into the TUN/TAP interface.

    Of course, we're not restricted to getting packets via TUN/TAP,
    this is just an example.
    """

    def __init__(self, verbose=False):
        #WYQ Removed
        #self.tun_fd = tun_fd       # file descriptor for TUN/TAP interface
        self.verbose = verbose
        self.tb = None             # top block (access to PHY)

    def set_top_block(self, tb):
        self.tb = tb

    def pack_pkt(self, SBN, ESI, K, N, T, symbols):

        # build the packet to be sent. packet = pktno + pkt + crc32
        #   - SBN:   source block number of raptor codes
        #   - ESI:   the id of encoded symbols
        #   - K: the number of source symbols
        #   - N: the number of encoded symbols
        #   - T: the length of the source/encoded symbols
        
        def hexint(mask):
            if mask >= 2**31:
                return int(mask-2**32)
            return mask

        trunk = ''
        for symbol in symbols:
            trunk += struct.pack('!H', symbol & 0xffff)
        #print "[pack_pkt] SBN: %d  ESI: %d, K: %d, T: %d" % (SBN, ESI, K, T)
        return (struct.pack('!H', SBN & 0xffff) + struct.pack('!H', ESI & 0xffff) + struct.pack('!H', K & 0xffff) 
         + struct.pack('!H', N & 0xffff) + struct.pack('!H', T & 0xffff) + trunk)

    def unpack_pkt(self, payload):
        if len(payload) < 12:
            return (False, None, None, None)
        
        pkt_ok = True

        (SBN,) = struct.unpack('!H', payload[0:2])
        (ESI,) = struct.unpack('!H', payload[2:4])
        (K,) = struct.unpack('!H', payload[4:6])
        (N,) = struct.unpack('!H', payload[6:8])
        (T,) = struct.unpack('!H', payload[8:10])
        pkt = payload[10:]

        symbols = list()

        for pos in xrange(0, len(pkt), 2):
            symbols.append(struct.unpack('!H', pkt[pos:pos+2])[0])

        #print "[unpack_pkt] pkt_ok: %r, SBN: %d  ESI: %d, K: %d, N: %d, T: %d" % (pkt_ok, SBN, ESI, K, N, T)
        return (pkt_ok, SBN, ESI, K, N, T, symbols)
    
    def pack_ack(self, pktno = None):
        if pktno is None:
            pktno = self.pktno

        return struct.pack('!HI', pktno & 0xffff)

    def unpack_ack(self, ack):
        if len(ack) != 2:
            return (None, None)

        return struct.unpack('!HI', ack)

    def phy_rx_callback(self, ok, payload):
        """
        Invoked by thread associated with PHY to pass received packet up.

        Args:
            ok: bool indicating whether payload CRC was OK
            payload: contents of the packet (string)
        """
        if self.verbose:
            print "Rx: ok = %r  len(payload) = %4d" % (ok, len(payload))
            #print "payload = %r" % payload
        if ok:
            #WYQ Removed
            #os.write(self.tun_fd, payload)
            #WYQ added

            #(tries, crc32) = self.unpack_ack(payload)
            #if tries is None:
            #    print "got a wrong ack, len(ack) != 6."
            #else:
            #    print "ack received. tries = %d  crc = %r" % (tries, crc32)
            print "start sending a new packet (I mean new data)."
        else:
            print "Oops! not an ack?"
            #Currently, we just set tx_done to be true

    def main_loop(self, file_data, packetLen, PLR):
        """
        Main loop for MAC.
        Only returns if we get an error reading from TUN.

        FIXME: may want to check for EINTR and EAGAIN and reissue read
        """
        min_delay = 0.001               # seconds

        # WYQ:2014/02/24
        def send_video_pkt(SBN, ESI, K, N, T, symbols='', eof=False):
            #WYQ Removed
            #payload = os.read(self.tun_fd, 10*1024)
            #WYQ added
            payload = self.pack_pkt(SBN, ESI, K, N, T, symbols)
            # let it loop forever. the receiver doesn't handle the 'eof' now.
            if not payload:  # it may not happen
                print "can't get a packet from raptor to send. exit."
                self.tb.txpath.send_pkt(eof=True)
                #break
            # 1 pkt per second 
            time.sleep(0.04)

            if self.verbose:
                m=1
                #print "Tx: len(payload) = %4d" % len(payload)
                #print "payload = 0x%s\n" % ''.join(x.encode('hex') for x in payload)

            delay = min_delay
            while self.tb.carrier_sensed():
                sys.stderr.write('B')
                time.sleep(delay)
                if delay < 0.010:
                    delay = delay * 2       # exponential back-off

            self.tb.send_pkt(payload)

        file_length = len(file_data)
        #print "file length is ", file_length

        #The number of the source symbols
        #K = file_length // packetLen
        K = 1000
        lossNum = (K + K * PLR // 100 + 8) * PLR // 100

        #print "K = %d, PLR = %d, lossNum = %d" %(K, PLR, lossNum)

        encoder = raptor_encoder.RaptorEncoder(K, lossNum, 20)

        #index = 0;
        #i = 0
        #while i < K:
        #    j = 0
        #    src_symbols = raptor_encoder.vectoruc()
        #    while j < packetLen:
        #        rndValue = random.randint(0, 255)
        #        #print rndValue
        #        src_symbols.append(rndValue)
        #        j += 1
        #    print list(src_symbols)
        #    print "\n"
        #    encoder.set_data(src_symbols)
        #    i += 1


        sendPktLen = 0
        # WYQ:2014/02/24
        pktNum = 0
        #while (sendPktLen + packetLen) <= file_length:
        while pktNum < K:
            src_symbols = raptor_encoder.vectoruc()

            curPktEnd = sendPktLen + packetLen
            data = file_data[sendPktLen:curPktEnd]
            #data_list = list(data)

            #src_symbols = file_data[sendPktLen:curPktEnd]

            # add error handling here 021609
            # except (KeyboardInterrupt, SystemExit):
            #    raise
            if not data:
                break

            #i = 0
            #while i < packetLen:
            #    print data_list[i]
            #    #src_symbols.append(data_list[i])
            #    i += 1

            #print list(src_symbols)
            #print "\n"
            #encoder.set_data(src_symbols)
            #src_symbols.clear()
            encoder.set_data(data)
            sendPktLen += packetLen
            pktNum += 1

        #data = file_data[sendPktLen:file_length] + 6 * "0"
        #print len(data)
        #encoder.set_data(data)

        #get the encoded symbols after raptor encoding
        encoder.get_data_access()
        N = encoder.count_encodedSym()
        SBN = 0
        ESI = 0
        #print "encoded symbols number = %4d" % N
        while encoder.is_empty() is False:
            encoded_symbols = encoder.get_encodedSym()
            payload = list(encoded_symbols)
            #print payload
            #print "\n"
            send_video_pkt(SBN, ESI, K, N, packetLen, payload)
            ESI += 1


# /////////////////////////////////////////////////////////////////////////////
#                                   main
# /////////////////////////////////////////////////////////////////////////////

def main():

    mods = digital.modulation_utils.type_1_mods()
    demods = digital.modulation_utils.type_1_demods()

    parser = OptionParser (option_class=eng_option, conflict_handler="resolve")
    expert_grp = parser.add_option_group("Expert")
    parser.add_option("-m", "--modulation", type="choice", choices=mods.keys(),
                      default='gmsk',
                      help="Select modulation from: %s [default=%%default]"
                            % (', '.join(mods.keys()),))

    parser.add_option("-s", "--size", type="eng_float", default=1500,
                      help="set packet size [default=%default]")
    parser.add_option("-v","--verbose", action="store_true", default=False)

    parser.add_option("-p", "--PLR", type="intx", default=3,
                      help="set packet loss rate [default=%default]")
    parser.add_option("-T", "--packLen", type="intx", default=200,
                      help="set source symbol numbers [default=%default]")


    expert_grp.add_option("-c", "--carrier-threshold", type="eng_float", default=30,
                          help="set carrier detect threshold (dB) [default=%default]")
    expert_grp.add_option("","--tun-device-filename", default="/dev/net/tun",
                          help="path to tun device file [default=%default]")

    transmit_path.add_options(parser, expert_grp)
    receive_path.add_options(parser, expert_grp)
    uhd_receiver.add_options(parser)
    uhd_transmitter.add_options(parser)

    for mod in mods.values():
        mod.add_options(expert_grp)

    for demod in demods.values():
        demod.add_options(expert_grp)

    (options, args) = parser.parse_args ()
    if len(args) != 0:
        parser.print_help(sys.stderr)
        sys.exit(1)

    # open the TUN/TAP interface
    #(tun_fd, tun_ifname) = open_tun_interface(options.tun_device_filename)

    if options.rx_freq is None or options.tx_freq is None:
        sys.stderr.write("You must specify -f FREQ or --freq FREQ\n")
        parser.print_help(sys.stderr)
        sys.exit(1)

    # Attempt to enable realtime scheduling
    r = gr.enable_realtime_scheduling()
    if r == gr.RT_OK:
        realtime = True
    else:
        realtime = False
        print "Note: failed to enable realtime scheduling"

    # instantiate the MAC
    #mac = cs_mac(tun_fd, verbose=True)
    mac = cs_mac(verbose=True)

    # build the graph (PHY)
    tb = my_top_block(mods[options.modulation],
                      demods[options.modulation],
                      mac.phy_rx_callback,
                      options)

    mac.set_top_block(tb)    # give the MAC a handle for the PHY

    if tb.txpath.bitrate() != tb.rxpath.bitrate():
        print "WARNING: Transmit bitrate = %sb/sec, Receive bitrate = %sb/sec" % (
            eng_notation.num_to_str(tb.txpath.bitrate()),
            eng_notation.num_to_str(tb.rxpath.bitrate()))
             
    print "modulation:     %s"   % (options.modulation,)
    print "freq:           %s"      % (eng_notation.num_to_str(options.tx_freq))
    print "bitrate:        %sb/sec" % (eng_notation.num_to_str(tb.txpath.bitrate()),)
    print "samples/symbol: %3d" % (tb.txpath.samples_per_symbol(),)

    tb.rxpath.set_carrier_threshold(options.carrier_threshold)
    print "Carrier sense threshold:", options.carrier_threshold, "dB"
    
    source_file = open('./foreman_cif.264', 'r')
    #print 'zhifeng: from file'
    #print 'source_file = ', source_file
    file_data = source_file.read()
    file_length = len(file_data)
    #print "file length is", file_length
    #print file_data
    #raw_input('zhifeng on 070928: press any key to continue') 
    source_file.close()

    tb.start()    # Start executing the flow graph (runs in separate threads)

    #K = 100
    print "PLR:     %s"   % (options.PLR,)
    mac.main_loop(file_data, options.packLen, options.PLR)    # don't expect this to return...

    tb.stop()     # but if it does, tell flow graph to stop.
    tb.wait()     # wait for it to finish
                

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
