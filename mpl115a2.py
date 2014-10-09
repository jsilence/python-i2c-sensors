#!/usr/bin/python

# ToDo: implement start-stopping via GPIO pins

import smbus
import time

class MPL115A2:
    """Class to read pressure from MPL115A2.
       Datasheet: http://cache.freescale.com/files/sensors/doc/data_sheet/MPL115A2.pdf
       Ressources:
         http://raspberrypi.hatenablog.com/entry/2014/07/04/225802 - calculated pressure is too high
         https://github.com/khoulihan/micropython-mpl115a2/blob/master/mpl115a2.py - depends on pyb
         Martin Steppuhn's code from http://www.emsystech.de/raspi-sht21"""

    #control constants
    _I2C_ADDRESS = 0x60
    _COMMAND_START_CONVERSION = 0x12
    _COEFFICIENT_START_ADDRESS = 0x04
    _COEFFICIENT_BLOCK_LENGTH = 8
    _SENSOR_DATA_BLOCK_LENGTH = 4

    def __init__(self, bus):
        self.bus = bus

        # Coefficients for compensation calculations - will be set on first
        # attempt to read pressure or temperature
        self.a0 = None
        self.b1 = None
        self.b2 = None
        self.c12 = None

    def parse_signed(self, msb, lsb):
        """Helper function for processing raw sensor readings.
        """
        combined = msb << 8 | lsb
        negative = combined & 0x8000
        if negative:
            combined ^= 0xffff
            combined *= -1
        return combined


    def read_coefficients(self):
        """Coefficients reflect the individual sensor calibration. Differs from sensor to sensor.
        Only needs to be read once per session.
        """
        block = self.bus.read_i2c_block_data(self._I2C_ADDRESS, 
                                             self._COEFFICIENT_START_ADDRESS, 
                                             self._COEFFICIENT_BLOCK_LENGTH)
        self.a0 = float(self.parse_signed(block[0], block[1])) / 8.0
        self.b1 = float(self.parse_signed(block[2], block[3])) / 8192.0
        self.b2 = float(self.parse_signed(block[4], block[5])) / 16384.0
        self.c12 = float(self.parse_signed(block[6], block[7]) >> 2) / 4194304.0

    def read_raw_pressure(self):
        """Retrieves msb and lsb from the sensor and calculates the raw sensor pressure reading.
        """
        self.bus.write_byte_data(self._I2C_ADDRESS, 
                                 self._COMMAND_START_CONVERSION, 
                                 0x00)
        time.sleep(0.005) 
        rp = self.bus.read_i2c_block_data(self._I2C_ADDRESS, 
                                          0x00, 
                                          2)
        return int((rp[0] << 8 | rp[1]) >> 6)

    def read_raw_temperature(self):
        """Retrieves msb and lsb from the sensor and calculates the raw sensor temperature reading.
        """
        self.bus.write_byte_data(self._I2C_ADDRESS, 
                                 self._COMMAND_START_CONVERSION, 
                                 0x02) 
        time.sleep(0.005) 
        rt = self.bus.read_i2c_block_data(self._I2C_ADDRESS, 
                                          0x02, 
                                          2)
        return int((rt[0] << 8 | rt[1]) >> 6)


    def pressure(self, times=10):
        """Reads sensor several times and returns the average to mitigate sensor noise.
        defaults to ten sensor readings. Rounds to one digit.
        """
        sum = 0
        for run in range(times):
            sum += self.read_pressure()
        return round(sum / times, 1)

    def read_pressure(self):
        """Starts sensor conversion, retrieves raw pressure and temperature data and 
        calculates barometric pressure in kPa from sensor readings and coefficients.
        Retrieves coefficients if neccessary.
        Note that this call blocks for 5 ms to allow the sensor to return the data.
        """
        if self.a0 is None:
            self.read_coefficients()
        rp = self.read_raw_pressure()
        rt = self.read_raw_temperature()
        compensated = (((self.b1 + (self.c12 * rt)) * rp) + self.a0) + (self.b2 * rt)
        return round((compensated * (65.0 / 1023.0)) + 50.0, 1)


    def __enter__(self):
        """used to enable python's with statement support"""
        return self
        

    def __exit__(self, type, value, traceback):
        """with support
        Disconnecting the bus object from the I2C bus.
        """
        self.bus.close()


if __name__ == "__main__":
    try:
        bus = smbus.SMBus(1)
        with MPL115A2(bus) as mpl115a2:
            print "Pressure (kPa): %s" % mpl115a2.pressure()
    except IOError, e:
        print e
        print 'Error creating connection to i2c.'
