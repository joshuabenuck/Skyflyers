# Skyflyers
A project to create a wireless connection to a Skylanders Portal of Power

Thus far, the project is able to emulator a portal of power enough to successfully enumerate on a Linux host.

Other projects used to create this include:
   * LUFA: http://www.fourwalledcubicle.com/LUFA.php
   * USBSimulator: https://github.com/brandonlw/USBSimulator
   * vusb-analyzer: http://vusb-analyzer.sourceforge.net/

In order to run this, you will need to:

1.  Install my modified version of the USBSimulator source on a Teensy 2.1.
2.  Connect an FTDI USB Serial cable (5 volt version) to the transmit, receive, and ground pins on the Teensy.
3.  Edit sim.py to point to the correct /dev entry for your cable.
4.  Run *sudo python sim.py*
5.  Monitor */var/log/syslog* to see the Teensy show up as a portal!
