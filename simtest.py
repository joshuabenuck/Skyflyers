# vim: sw=4:ts=4:hls:ai:et
import unittest
from sim import SimPacket, UsbRequest

f_conn = [0x46, 0x01]
f_disc = [0x46, 0x00]
u = [0x55, 0x80, 0x06, 0x00, 0x01, 0x00, 0x00, 0x40, 0x00]

a_u = [0x41, 0x55, 0x55]
a_u_hex   = "4155 55   AUU"
d_req = [0x44, 0x00, 0x01, 0x00, 0x00, 0x09, 0x00]
d_req_hex = "4400 0100 00   D...."

"5500 0564 0000 0000 00   U..d....."
set_addr_req = [0x00, 0x05, 0x64, 0x00, 0x00, 0x00, 0x00, 0x00]

def arrToStr(arr):
    s = ""
    for i in arr:
        s += chr(i)
    return s

class UsbRequestTest(unittest.TestCase):
    def test_get_descriptor_req(self):
        request = UsbRequest(u[1:])
        self.assertEquals(0x80, request.bmRequestType)
        self.assertEquals(0x06, request.bRequest)
        self.assertEquals(True, request.canIgnore())

    def test_set_addr_req(self):
        request = UsbRequest(set_addr_req)
        self.assertEquals(0x00, request.bmRequestType)
        self.assertEquals(0x05, request.bRequest)
        self.assertEquals(0x00, request.wLength)
        self.assertEquals(True, request.canIgnore())

    def test_get_device_desc_req(self):
        dev_desc_req = [0x80, 0x06, 0x00, 0x01, 0x00, 0x00, 0x40, 0x00]
        request = UsbRequest(dev_desc_req)
        self.assertEquals(0x01, request.wValue)
        self.assertTrue(request.isDeviceDescriptorRequest())
        self.assertTrue(request.canIgnore())
    
    def test_format_usb_req(self):
        request = UsbRequest(set_addr_req)
        expected = \
"""bmRequestType: 00 0b0
bRequest: 05 (SET_ADDRESS)
wValue: 6400
wIndex: 0000
wLength: 0000
data: 
"""
        self.assertEquals(expected, request.format())

class SimPacketTest(unittest.TestCase):
    def setUp(self):
        self.uReq = u
        self.fConnReq = f_conn
        self.fDiscReq = f_disc

    def test_u_packet(self):
        packet = SimPacket(self.uReq)
        self.assertTrue(packet.isUsbPacket())
        self.assertFalse(packet.isConnectedEvent())
        request = packet.usbRequest()
        self.assertIsNotNone(request)
        self.assertEquals(0x80, request.bmRequestType)
        self.assertEquals(0x06, request.bRequest)
        self.assertTrue(request.isDescriptorRequest())

    def test_f_conn_packet(self):
        packet = SimPacket(self.fConnReq)
        self.assertTrue(packet.isConnectedEvent())
        self.assertFalse(packet.isDisconnectedEvent())

    def test_f_disc_packet(self):
        packet = SimPacket(self.fDiscReq)
        self.assertTrue(packet.isDisconnectedEvent())
        self.assertFalse(packet.isConnectedEvent())

    def test_format_a_u(self):
        packet = SimPacket(a_u)
        self.assertEquals(a_u_hex, packet.format())

    def test_d_req(self):
        packet = SimPacket(d_req)
        self.assertEquals(d_req_hex, packet.format())
        self.assertTrue(packet.isDescriptorPacket())

    def test_d_req(self):
        packet = SimPacket(d_req)
        self.assertEquals(0x09, packet.getRequestedDescriptorSize())
        self.assertTrue(packet.isDescriptorPacket())

if __name__ == '__main__':
    unittest.main()
