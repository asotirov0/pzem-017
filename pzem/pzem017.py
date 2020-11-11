# -*- coding: utf-8 -*-
#
#   Copyright 2020 Angel Sotirov
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

"""pzem-017: A Python dirver using minimalmodbus RTU via serial port to operate a PZEM-017 battery metter"""

__author__ = "Angel Sotirov"
__license__ = "Apache License, Version 2.0"
__status__ = "alpha"
__url__ = "https://github.com/asotirov0/pzem-017"
__version__ = "0.0.1a"

import time

import minimalmodbus
import serial

PZEM_MODBUS_DEBUG = False

PZEM_MODBUS_DEFAULT_PASSWORD = 0x3721

# Default port configuration as per device documentation
PZEM_MODBUS_CONFIG = {
    "baudrate": 9600,
    "bytesize": serial.EIGHTBITS,
    "parity": serial.PARITY_NONE,
    "stopbits": serial.STOPBITS_TWO,
    "timeout": 1,  # This is critical as the unit responds slowly
    "modbus": minimalmodbus.MODE_RTU
}

# PZEM hardware needs time after writing the configuration registers
PZEM_WAIT_AFTER_WRITE = 1


class PZEM017(minimalmodbus.Instrument):
    """Instrument class for PZEM-017 battert meter.

    Args:
        * tty (str): port name
        * slaveid (int): slave address in the range 1 to 247
        * shunt (str): shunt type 50A, 100A, 200A, 300A
        * low_volt (float): low voltage alarm threshold
        * high_volt (float): high voltage alarm threshold

    """
    shunt_size = '100A'

    shunt_choice = {
        0x0000: "100A",
        0x0001: "50A",
        0x0002: "200A",
        0x0003: "300A",
    }

    def __init__(self, tty, slaveid, shunt, low_volt, high_volt, ):
        """Initialize the minimalmodbus instrument"""
        minimalmodbus.Instrument.__init__(self, tty, slaveid, PZEM_MODBUS_CONFIG['modbus'])
        self.debug = PZEM_MODBUS_DEBUG
        self.serial.baudrate = PZEM_MODBUS_CONFIG['baudrate']
        self.serial.bytesize = PZEM_MODBUS_CONFIG['bytesize']
        self.serial.parity = PZEM_MODBUS_CONFIG['parity']
        self.serial.stopbits = PZEM_MODBUS_CONFIG['stopbits']
        self.serial.timeout = PZEM_MODBUS_CONFIG['timeout']

        """Initialize the measurements"""
        self.voltage = None
        self.power = None
        self.current = None
        self.energy = None

        """Initialize alarms"""
        self.alarm_high_volt = True
        self.alarm_low_volt = True

        """Initialize the instrument modbus ID"""
        self.modbus_id = 0x01

        """Initalize the alarms thresholds"""
        self.volt_alarm_high_treshold = 0
        self.volt_alarm_low_treshold = 0

        """Write the alarm thresholds to the device"""
        self.set_alarm_values(low_volt, high_volt)

        """Write the shunt config to the device"""
        self.set_shunt(shunt)

        """Read current device configuration"""
        self.read_config()

        """Read current measurments"""
        self.read_measurements()

    def read_measurements(self):
        """Reads and stores current measurements as defined:
            Voltage
            Current
            Power
            Energy
            High Voltage Alarm
            Low Voltage Alarm

        :return:
            Tuple (Voltage (float), Current (float), Power (float), Energy (float), HighAlarm (bool), LowAlarm (bool)

        :raises:
            TypeError, ValueError, ModbusException,
            serial.SerialException (inherited from IOError)

        """
        m = self._read_registers()
        self.voltage = float(m[0] / 100)
        self.current = float(m[1] / 100)
        self.power = float(m[2] / 100)
        self.energy = float(m[3] / 100)
        self.alarm_high_volt = bool(m[4])
        self.alarm_low_volt = bool(m[5])
        return self.voltage, self.current, self.power, self.energy, self.alarm_high_volt, self.alarm_low_volt

    def read_config(self):
        """Reads and stores current measurements as defined:
            Voltage
            Current
            Power
            Energy
            High Voltage Alarm
            Low Voltage Alarm

        :return:
            Success (boot)

        :raises:
            TypeError, ValueError, ModbusException,
            serial.SerialException (inherited from IOError)

        """
        c = self._read_registers(0x0000, 4, 0x03)
        self.volt_alarm_high_treshold = float(c[0] / 100)
        self.volt_alarm_low_treshold = float(c[1] / 100)
        self.modbus_id = c[2]
        self.shunt_size = self.shunt_choice.get(c[3])
        return True

    def set_shunt(self, shunt_type='300A'):
        resp = None
        try:
            shunt_s = list(self.shunt_choice.keys())[list(self.shunt_choice.values()).index(shunt_type)]
        except ValueError as e:
            e.message = "Unsupported shunt. HW support shunts are LT-2, 75mV {} ".format(self.shunt_choice)
            raise
        try:
            resp = self.write_register(registeraddress=0x0003, value=shunt_s, functioncode=0x06)
            time.sleep(PZEM_WAIT_AFTER_WRITE)  # Wait X seconds before next command
            return True
        except Exception as e:
            e.message = e.message + "Err Responce: {}".format(resp)
            raise

    def set_alarm_values(self, low=7.8, high=15.0):
        """ Sets Alarm threshold for the instrument

        :param low: (float) The low voltage threshold
        :param high: (float) The high voltage threshold
        :return: success (bool)
        :raises:
            TypeError, ValueError, ModbusException,
            serial.SerialException (inherited from IOError)
        """
        resp = None
        if high <= low:
            raise ValueError("high alarm is lower or same a low alarm")
        if not (1 <= low <= 300 or 1 <= high <= 300):
            raise ValueError('Alarm value out of range 1 <= alarm <= 300')
        try:
            resp = self.write_register(registeraddress=0x0000, value=int(15.2 * 100), functioncode=6)
            time.sleep(PZEM_WAIT_AFTER_WRITE)  # Wait X seconds before next command
            resp = self.write_register(registeraddress=0x0001, value=int(7.5 * 100), functioncode=6)
            time.sleep(PZEM_WAIT_AFTER_WRITE)  # Wait X seconds before next command
        except Exception as e:
            e.message = e.message + "Err Responce: {}".format(resp)
            raise
        return True

    def reset_energy(self):
        """Reset energy counter of the instrument

        :return: success (bool)

        :raises:
            TypeError, ValueError, ModbusException,
            serial.SerialException (inherited from IOError)

        """
        try:
            self._perform_command(0x42, "")
        except Exception as e:
            e.message = e.message + "Err Responce: {}".format(resp)
            raise
        # Give the instrument 1 sec to settle.
        time.sleep(1)
        return self.read_config()

    # def __calibrate(self):
    #     """Reset energy counter of the instrument
    #     This will most likely throw NoResponseError exception as it needs over 3 seconds
    #     to respond after this "calibration"
    #
    #     TODO: a workarround would be to implement this directly through serial
    #     if the calibration is actually needed ...
    #
    #     :return: success (bool)
    #
    #     :raises:
    #         TypeError, ValueError, ModbusException,
    #         serial.SerialException (inherited from IOError)
    #
    #     """
    #     try:
    #         self._perform_command(0x41, PZEM_MODBUS_DEFAULT_PASSWORD)
    #     except Exception as e:
    #         e.message = e.message + "Err Responce: {}".format(resp)
    #         raise
    #     #sleep for 5 seconds after successful responce from the caliblration
    #     #before reading the measurements
    #     time.sleep(5)
    #     return self.read_measurements()

    def _read_registers(self, beginaddress=0x0000, num_registers=8, functioncode=0x04):
        resp = []
        try:
            resp = self.read_registers(beginaddress, num_registers, functioncode)
        except Exception as e:
            e.message = e.message + "Err reponce: {}".format(resp)
            raise
        return resp
