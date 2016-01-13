# vim: sw=4:ts=4:et:ai
import serial, sys, curses, os, tty, termios, time
from select import select

# Two Byte Int in Little Endian
def tbint(one, two):
    if type(one) == str: one = ord(one)
    if type(two) == str: two = ord(two)
    return one | (two << 8)

ack = "4153 AS"
u = [0x55, 0x80, 0x06, 0x00, 0x01, 0x00, 0x00, 0x40, 0x00]

"""
Device Descriptor from portal
0000: 12 01 00 02 00 00 00 20 30 14 50 01 00 01 01 02 ....... 0.P.....
0010: 00 01                                           ..    

Configuration Descriptor
0000: 09 02 29 00 01 01 00 80 96 09 04 00 00 02 03 00 ..).............
0010: 00 00 09 21 11 01 00 01 22 1d 00 07 05 81 03 20 ...!...."...... 
0020: 00 01 07 05 01 03 20 00 01                      ...... ..  

The above contains config, interfaces, and endpoints.
Marker bytes are 0x09 and 0x07.

Format of "endpoing configuration stuff" that is "tacked on" here...
1 - Count of endpoints
for each endpoint:
1 - Endpoint id | Direction
1 - Type
1 - MaxPacketSize & 0xFF
1 - MaxPacketSize >> 8
"""
device_descriptor = [
    0x12, 0x01, 0x00, 0x02, 0x00, 0x00, 0x00, 0x40, 0x30,
    0x14, 0x50, 0x01, 0x00, 0x01, 0x01, 0x02, 0x00, 0x01
]
endpoint_data = [0x2,
    0x81, 0x3, 0x20, 0x00,
    0x01, 0x3, 0x20, 0x00]

configuration = [
    0x09, 0x02, 0x29, 0x00, 0x01, 0x01, 0x00, 0x80, 0x96, 0x09, 0x04, 
    0x00, 0x00, 0x02, 0x03, 0x00,
    0x00, 0x00, 0x09, 0x21, 0x11, 0x01, 0x00, 0x01, 0x22, 0x1d, 0x00,
    0x07, 0x05, 0x81, 0x03, 0x20,
    0x00, 0x01, 0x07, 0x05, 0x01, 0x03, 0x20, 0x00, 0x01
]

# Consider storing this in a more easily readable format and then converting.
strings = [
[ 0x04, 0x03, 0x09, 0x04 ],
[ 0x16, 0x03, 0x41, 0x00 , 0x63, 0x00, 0x74, 0x00 , 0x69, 0x00, 0x76, 0x00 , 0x69, 0x00, 0x73, 0x00 , 0x69, 0x00, 0x6f, 0x00 , 0x6e, 0x00 ],
[ 0x18, 0x03, 0x53, 0x00 , 0x70, 0x00, 0x79, 0x00 , 0x72, 0x00, 0x6f, 0x00 , 0x20, 0x00, 0x50, 0x00 , 0x6f, 0x00, 0x72, 0x00 , 0x74, 0x00, 0x61, 0x00 ]
]

report = [
 0x06, 0x00, 0xff, 0x09 , 0x01, 0xa1, 0x01, 0x19 , 0x01, 0x29, 0x40, 0x15, 0x00, 0x26, 0xff, 0x00 , 0x75, 0x08, 0x95, 0x20, 0x81, 0x00, 0x19, 0x01, 0x29, 0x40, 0x91, 0x00 , 0xc0
]

# print byte with binary
def fbwb(field, value):
    if type(value) == str: value = ord(value)
    return field + ": " + "%02x %s"%(value, bin(value))

def fb(field, value, lookup=None):
    if type(value) == str: value = ord(value)
    ret = field + ": " + "%02x"%(value)
    if lookup != None and lookup[value] != None:
        ret += " (%s)"%lookup[value]
    return ret

# print word
def fw(field, p1, p2):
    if type(p1) == str: p1 = ord(p1)
    if type(p2) == str: p2 = ord(p2)
    return field + ": " + "%02x%02x"%(p1, p2)

# print string
def fs(field, data):
    return field + ": "

def fhex(data):
    even = True; hex_str = ""; disp = ""
    for c in data:
        hex_str += "%02x"%c
        if even: even = False
        else: hex_str += " "; even = True
        if c < 32 or c >= 127: disp += "."
        else: disp += chr(c)

    if not even: hex_str+= "  "
    disp = " " + disp
    return hex_str + disp

REQUEST_TYPE_IDS = {
    0x80: ""
}

REQUEST_IDS = {
    0x00: "GET_STATUS",
    0x01: "CLEAR_FEATURE",
    0x02: "Reserved",
    0x03: "SET_FEATURE",
    0x04: "Reserved",
    0x05: "SET_ADDRESS",
    0x06: "GET_DESCRIPTOR",
    0x07: "SET_DESCRIPTOR",
    0x08: "GET_CONFIGURATION",
    0x09: "SET_CONFIGURATION",
    0x0A: "GET_INTERFACE",
    0x0B: "SET_INTERFACE",
    0x0C: "SYNC FRAME",
}

class UsbRequest:
    def __init__(self, packet):
        self.packet = packet
        self.bmRequestType = packet[0]
        self.bRequest = packet[1]
        # This still doesn't sit well with me.
        # It appears to be Big Endian and not Little Endian.
        # Is something reversing this?
        # Or does a "word sized value" in the spec mean it is in BE?
        self.wValue = tbint(packet[3], packet[2])
        self.wIndex = tbint(packet[5], packet[4])
        self.wLength = tbint(packet[6], packet[7])
        self.data = packet[8:]

    # Brandon's code ignores requests that meet these two criteria...
    def canIgnore(self):
        if self.bmRequestType & 0x80 == 0x80: return True
        if self.wLength == 0x00: return True
        return False

    def isDescriptorRequest(self):
        GET_DESCRIPTOR = 0x06
        if self.bRequest == GET_DESCRIPTOR:
            return True
        return False

    def isDeviceDescriptorRequest(self):
        if self.isDescriptorRequest() and self.wValue == 0x01:
            return True
        return False

    def isDeviceQualifierDescriptorRequest(self):
        if self.isDescriptorRequest() and self.wValue == 0x06:
            return True
        return False

    def isConfigurationDescriptorRequest(self):
        if self.isDescriptorRequest() and self.wValue == 0x02:
            return True
        return False

    def format(self):
        disp = ""
        disp += fbwb("bmRequestType", self.packet[0]) + "\n"
        disp += fb("bRequest", self.packet[1], REQUEST_IDS) + "\n"
        disp += fw("wValue", self.packet[2], self.packet[3]) + "\n"
        disp += fw("wIndex", self.packet[4], self.packet[5]) + "\n"
        disp += fw("wLength", self.packet[6], self.packet[7]) + "\n"
        disp += fs("data", self.packet[8:]) + "\n"
        return disp

I_SP_TYPE = 0
I_SP_REQTYPE = 1
I_SP_REQ = 2
SP_REQTYPE_USB = 'U'
"""
What is the canonical representation for packets?
Sometimes they are chars as they come off the serial port.
Other times they are ordinals as it makes it easier to write in code.
"""
class SimPacket:
    def __init__(self, packet):
        self.packet = packet
        self.cmd = packet[0]

    def _packet_type(self): return self.packet[0]
    def _req_type(self): return self.packet[1]
    def _is_f_packet(self):
        if self._packet_type() == ord('F'): return True
        return False

    def isConnectedEvent(self):
        if self._is_f_packet() and self._req_type() == 0x01:
            return True
        return False

    def isDisconnectedEvent(self):
        if self._is_f_packet() and self._req_type() == 0x00:
            return True
        return False

    def isUsbPacket(self):
        if self.packet[0] == ord('U'): return True
        return False

    def isDescriptorPacket(self):
        if self.packet[0] == ord('D'): return True
        return False

    def isDeviceDescriptorPacket(self):
        if not self.isDescriptorPacket(): return False
        if self.packet[2] == 0x01: return True
        return False

    def isDeviceQualifierDescriptorPacket(self):
        if not self.isDescriptorPacket(): return False
        if self.packet[2] == 0x06: return True
        return False

    def isConfigurationDescriptorPacket(self):
        if not self.isDescriptorPacket(): return False
        if self.packet[2] == 0x02: return True
        return False

    def isStringDescriptorPacket(self):
        if not self.isDescriptorPacket(): return False
        if self.packet[2] == 0x03: return True
        return False

    def getStringIndex(self):
        return self.packet[1]

    def isReportDescriptorPacket(self):
        if not self.isDescriptorPacket(): return False
        if self.packet[2] == 0x22: return True
        return False

    def getRequestedDescriptorSize(self):
        if len(self.packet) == 7:
            return tbint(self.packet[5], self.packet[6])
        return 0

    def usbRequest(self):
        if not self.isUsbPacket():
            print "Warning: returning usb request for non-usb-request."
        return UsbRequest(self.packet[1:])

    def format(self):
        return fhex(self.packet)

    def p(self): print self.format()

"""
I may eventually merge this with SimPacket. For now, this is easier.
"""
class SimCommandPacket():
    def __init__(self, cmd, data=[]):
        self.cmd = cmd
        self.data = data

class SimUsbClient():
    def __init__(self):
        self.port = serial.Serial("/dev/ttyUSB0", 57600)

    def isPacketAvailable(self):
        """Are there enough chars on the port for another packet?"""
        if self.port.inWaiting() >= 2: return True
        return False

    def getNextPacket(self):
        """Get the next packet. Need to be sure there is one waiting."""
        total = tbint(self.port.read(), self.port.read())
        #print "Total:", total
        chrpacket = self.port.read(total)
        ordpacket = [ord(c) for c in chrpacket]
        packet = SimPacket(ordpacket)
        packet.p()
        return packet

    def sendPacket(self, packet):
        """Takes a SImPacket and sends it over the serial port."""
        length = len(packet.data) + 1
        towrite = []
        towrite.append(chr(length & 0xFF))
        towrite.append(chr((length>>8) & 0xFF))
        towrite.append(packet.cmd)
        for c in packet.data:
            towrite.append(c)
        print fhex([ord(c) for c in towrite])
        for c in towrite:
            self.port.write(c)

    """
    This method still feels off.
    Why is it the only one in the class that constructs the packet to send?
    I know I move it here to avoid the caller from having to know
    about the concept of a command in a packet, but is that really necessary?
    """
    def acknowledgePacket(self, statusPacket, stall=False):
        packet = SimCommandPacket(chr(statusPacket.cmd))
        IGNORE = 0x00
        HANDLE = 0x01
        STALL = 0x02
        print "Acknowledging:", packet.cmd, "Stall:", stall
        self.port.write(chr(2 & 0xFF))
        self.port.write(chr((2>>8) & 0xFF))
        self.port.write(packet.cmd)
        if not stall: self.port.write(chr(IGNORE))
        if stall: self.port.write(chr(STALL))

"""
This class represents a portal.
It receives commands from a Teensy client and responds to them as if it was
a real portal.
The goal of this phase is to make it through enumeration.
Once that is successfull, I'll move on to establishing pass through
to a real portal.
That class will probably be named SimUsbPortalPassthrough.
"""
class SimUsbPortal():
    def __init__(self):
        self.client = SimUsbClient()

    def loop(self):
        while 1:
            self.handleIncoming()
        self.disconnectUsb()

    """
    Is the Law of Demeter or DIP being violated here?
    Part of the method directly references the client while part
    goes through another method.
    """
    def handleIncoming(self):
        if self.client.isPacketAvailable():
            packet = self.client.getNextPacket()
            if packet.isConnectedEvent():
                print "Connected event."
                self.connectUsb()
            elif packet.isDisconnectedEvent():
                print "Diconnected event. Do nothing?"
            elif packet.isDeviceQualifierDescriptorPacket():
                self.sendEmptyDescriptor()
            elif packet.isStringDescriptorPacket():
                #self.sendEmptyDescriptor()
                self.sendStringDescriptor(packet)
            elif packet.isDeviceDescriptorPacket():
                self.sendDeviceDescriptor()
            elif packet.isConfigurationDescriptorPacket():
                self.sendConfiguration(packet)
            elif packet.isReportDescriptorPacket():
                self.sendReportDescriptor(packet)
            elif packet.isUsbPacket():
                request = packet.usbRequest()
                for line in request.format().split("\n"):
                    print "\t" + line
                self.handleUsbRequest(packet, request)

    def handleUsbRequest(self, packet, request):
        if request.isDescriptorRequest():
            if request.isDeviceDescriptorRequest():
                self.client.acknowledgePacket(packet)
            elif request.isDeviceQualifierDescriptorRequest():
                self.client.acknowledgePacket(packet, stall = False)
            elif request.isConfigurationDescriptorRequest():
                self.client.acknowledgePacket(packet)
            # Handle the descriptor requests that should be ignored.
            elif request.canIgnore():
                print "Ignoring device descriptor request."
                self.client.acknowledgePacket(packet)
        # There are some non descriptor requsts that should be ignored.
        elif request.canIgnore():
            print "Ignoring other command."
            self.client.acknowledgePacket(packet)
        else:
            print "Unknown."
            sys.exit(1)

    def sendConfiguration(self, reqPacket):
        print "Sending configuration descriptor."
        size = reqPacket.getRequestedDescriptorSize()
        data = configuration[:size]
        print fhex(data)
        packet = SimCommandPacket('D', [chr(o) for o in data])
        self.client.sendPacket(packet)

    def sendReportDescriptor(self, reqPacket):
        print "Sending report descriptor."
        size = reqPacket.getRequestedDescriptorSize()
        data = report[:size]
        print fhex(data)
        packet = SimCommandPacket('D', [chr(o) for o in data])
        self.client.sendPacket(packet)

    def sendDeviceDescriptor(self):
        print "Sending device descriptor."
        data = device_descriptor + endpoint_data
        packet = SimCommandPacket('D', [chr(o) for o in data])
        self.client.sendPacket(packet)

    # TODO: Fix! Not working!
    def sendStringDescriptor(self, reqPacket):
        print "Sending string descriptor."
        data = []
        data = strings[reqPacket.getStringIndex()]
        packet = SimCommandPacket('D', [chr(o) for o in data])
        self.client.sendPacket(packet)

    def sendEmptyDescriptor(self):
        print "Sending empty device descriptor."
        packet = SimCommandPacket('D', [])
        self.client.sendPacket(packet)

    def connectUsb(self):
        print "Connecting..."
        packet = SimCommandPacket('S', [chr(0x01)])
        self.client.sendPacket(packet)

    def disconnectUsb(self):
        print "Disconnecting..."
        packet = SimCommandPacket('S', [chr(0x00)])
        self.client.sendPacket(packet)

# http://stackoverflow.com/questions/24072790/detect-key-press-in-python
#fd = sys.stdin.fileno()
#old_settings = termios.tcgetattr(fd)
#try:
#    tty.setraw(sys.stdin.fileno())

if __name__ == '__main__':
    SimUsbPortal().loop()

#decodeControlRequest(u[1:])

def getch():
    """getch() -> key character

    Read a single keypress from stdin and return the resulting character. 
    Nothing is echoed to the console. This call will block if a keypress 
    is not already available, but will not wait for Enter to be pressed. 

    If the pressed key was a modifier key, nothing will be detected; if
    it were a special function key, it may return the first character of
    of an escape sequence, leaving additional characters in the buffer.
    """
    print "getch"
    ch = None
    [i, o, e] = select([sys.stdin.fileno()], [], [], 0.01)
    if len(i) > 0: ch=sys.stdin.read(1)
    print "return:", ch
    return ch

