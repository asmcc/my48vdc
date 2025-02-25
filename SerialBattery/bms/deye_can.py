# -*- coding: utf-8 -*-

# NOTES
# Idea and template based on two intergrations:
# jkbms_can.py by https://github.com/IrisCrimson
# daly_can.py by https://github.com/SamuelBrucksch 
# https://github.com/Louisvdw/dbus-serialbattery/pull/169
#
# Information about DEYE CAN protocols and further implementation ideas from:
# PCSCAN by Adminius https://github.com/Adminius/esphome-yaml-collection
# InternCAN by Psynosaur https://github.com/Psynosaur/esphome-deye-bms
#
# By asmcc@github
# Version 0.1

from __future__ import absolute_import, division, print_function, unicode_literals
from battery import Battery, Cell
from utils import (
    logger,
    INVERT_CURRENT_MEASUREMENT,
    FLOAT_CELL_VOLTAGE,
)
from struct import unpack_from
import can
import sys
import time

class Deye_Can(Battery):
    def __init__(self, port, baud, address):
        super(Deye_Can, self).__init__(port, baud, address)
        self.pcscan_bus = False                      # PCSCAN bus
        self.pcscan_timeout = False                  # Timeout occurred on PCSCAN bus
        self.intercan_available = False              # availability of second INTERCAN bus with cell voltages and settings
        self.intercan_bus = False                    # INTERCAN bus
        self.intercan_timeout = False                # Timeout occurred on INTERCAN bus
        self.intercan_timeout_count = 0              # Counter for achieved timeouts on INTERCAN bus 
        self.intercan_port = ""                      # INTERCAN bus interface
        self.cell_count = 1                          # initial number of cells
        self.poll_interval = 1000                    # polling interval to read CAN messages in milliseconds
        self.type = self.BATTERYTYPE                 # battery type
        self.last_error_time = time.time()           # timer to reset error flag
        self.error_active = False                    # error flag
        self.last_fet_status_time = time.time()      # timer to reset fet status flag
        self.fet_status_active = False               # fet status flag
        self.high_low_intercan_time = time.time()    # timer for highest and lowest cell voltages telegram over INTERCAN
        self.high_low_intercan = False               # flag for highest and lowest cell voltages telegram over INTERCAN
        self.cell_voltages_time = time.time()        # timer for cell voltages telegrams over INTERCAN
        self.cell_voltages_intercan = False          # flag for cell voltages over INTERCAN
        self.bms_software_version = ""               # BMS software version
        self.battery_software_version = ""           # battery software version
        self.battery_boot_version = ""               # battery boot version 
        self.battery_serial_number1 = ""             # battery serial number part1
        self.battery_serial_number2 = ""             # battery serial number part2
        self.bms_alarms = bytes(8)                   # BMS alarms
        self.bat_alarms = bytes(8)                   # battery alarms
        self.cell_mid_voltage = FLOAT_CELL_VOLTAGE   # mean cell voltage
        self.init_check = 0                          # collected value to check if all initialisation steps are done 
        self.init_done = False                       # init done flag

    def __del__(self):
        if self.pcscan_bus:
            self.pcscan_bus.shutdown()
            self.pcscan_bus = False
            logger.debug("PCSCAN bus shutdown")
        if self.intercan_bus:
            self.intercan_bus.shutdown()
            self.intercan_bus = False
            logger.debug("INTERCAN bus shutdown")

    BATTERYTYPE = "DEYE CAN"
    CAN_BUS_TYPE = "socketcan"
    BMS_LIM_VOLT_CURR = "BMS_LIM_VOLT_CURR"          # BMS limits: Maximal and minimal charge and discharge voltages, maximal charge and discharge currents
    BMS_SOC_SOH = "BMS_SOC_SOH"                      # BMS SOC and SOH
    BMS_VOLT_CURR_TEMP = "BMS_VOLT_CURR_TEMP"        # BMS voltage, current and temperature
    BMS_ERR_WARN_ALM = "BMS_ERR_WARN_ALM"            # Collected alarms and status bits from BMS for all batteries
    BMS_STAT = "BMS_STAT"                            # Collected BMS status bits for all batteries
    BMS_BAT_DATA = "BMS_BAT_DATA"                    # BMS manufacturer name, battery pack number, battery type and battery capacity
    BMS_MIN_MAX_CELL_DATA = "BMS_MIN_MAX_CELL_DATA"  # Collected BMS information: Minimal and maximal cell voltage and temperature (without number of concerned cell)
    BMS_SW_HW = "BMS_SW_HW"                          # BMS software and hardware version
    BMS_MODULE_STAT = "BMS_MODULE_STAT"              # Collected BMS status bits for all batteries
    BAT_ERR_WARN_ALM_STAT ="BAT_ERR_WARN_ALM_STAT"   # Individual alarms and status bits for each battery
    BAT_VOLT_CURR_SOC_SOH = "BAT_VOLT_CURR_SOC_SOH"  # Individual voltage, current, SOC and SOH for each battery
    BAT_MIN_MAX_CELL_DATA = "BAT_MIN_MAX_CELL_DATA"  # Individual information for each battery: Minimal and maximal cell voltage and temperature (without number of concerned cell)
    BAT_TEMP_MAX_CURR = "BAT_TEMP_MAX_CURR"          # Individual MOSFET and HEATING temperatures, minimal and maximal battery current for each battery
    BAT_SYS_STAT = "BAT_SYS_STAT"                    # Individual operation mode, failure level, charge cycles, balancing status and system substate for each battery
    BAT_SW_DATA = "BAT_SW_DATA"                      # Individual software and boot version for each battery
    BAT_ENERGY = "BAT_ENERGY"                        # Total charged and discharged energy for each battery
    BAT_SERIAL1 = "BAT_SERIAL1"                      # Battery serial number part 1 of 2
    BAT_SERIAL2 = "BAT_SERIAL2"                      # Battery serial number part 2 of 2
    BAT_NUMBER_OF_FAULTS1 = "BAT_NUMBER_OF_FAULTS1"  # Number of high/low voltage, short circuit, overtemperature alarms
    BAT_NUMBER_OF_FAULTS2 = "BAT_NUMBER_OF_FAULTS2"  # Number of charge/discharge overcurrent and charge/discharge overtemperature alarms
    INTER_HIGH_LOW = "INTER_HIGH_LOW"                # Minimal and maximal cell voltages including number of concerned cells
    INTER_CELL_VOLTAGES0 = "INTER_CELL_VOLTAGES0"    # Cell voltages 1-4
    INTER_CELL_VOLTAGES1 = "INTER_CELL_VOLTAGES1"    # Cell voltages 5-8
    INTER_CELL_VOLTAGES2 = "INTER_CELL_VOLTAGES2"    # Cell voltages 9-12
    INTER_CELL_VOLTAGES3 = "INTER_CELL_VOLTAGES3"    # Cell voltages 13-16
    MESSAGES_TO_READ = 25                            # Number of CAN messages, to be received during a function call
    ERROR_STATUS_TIMEOUT = 120                       # Timeout for errors and status bits
    INTERCAN_VALUES_TIMEOUT = 120                    # Timeout for INTERCAN values
    INTERCAN_TIMEOUT = 1000                          # Number of timeouts on INTERCAN until the interface will no loger be polled for new messages 
    INTERCAN_SKIPED_RECVS = 10                       # Skiped recv calls for INTERCAN after timeout
    
    CAN_FRAMES = {
        BMS_LIM_VOLT_CURR: [0x351],          # BMS limits: Maximal and minimal charge and discharge voltages, maximal charge and discharge currents
        BMS_SOC_SOH: [0x355],                # BMS SOC and SOH
        BMS_VOLT_CURR_TEMP: [0x356],         # BMS voltage, current and temperature
        BMS_ERR_WARN_ALM: [0x359],           # Collected alarms and status bits from BMS for all batteries
        BMS_STAT: [0x35C],                   # Collected BMS status bits for all batteries
        BMS_BAT_DATA: [0x35E],               # BMS manufacturer name, battery pack number, battery type and battery capacity
        BMS_MIN_MAX_CELL_DATA: [0x361],      # Collected BMS information: Minimal and maximal cell voltage and temperature (without number of concerned cell)
        BMS_SW_HW: [0x363],                  # BMS software and hardware version
        BMS_MODULE_STAT: [0x364],            # Collected BMS status bits for all batteries
        BAT_ERR_WARN_ALM_STAT: [0x110],      # Individual alarms and status bits for each battery
        BAT_VOLT_CURR_SOC_SOH: [0x150],      # Individual voltage, current, SOC and SOH for each battery
        BAT_MIN_MAX_CELL_DATA: [0x200],      # Individual information for each battery: Minimal and maximal cell voltage and temperature (without number of concerned cell)
        BAT_TEMP_MAX_CURR: [0x250],          # Individual MOSFET and HEATING temperatures, minimal and maximal battery current for each battery
        BAT_SYS_STAT: [0x400],               # Individual operation mode, failure level, charge cycles, balancing status and system substate for each battery
        BAT_SW_DATA: [0x500],                # Individual software and boot version for each battery
        BAT_ENERGY: [0x550],                 # Total charged and discharged energy for each battery
        BAT_SERIAL1: [0x600],                # Battery serial number part 1 of 2
        BAT_SERIAL2: [0x650],                # Battery serial number part 2 of 2
        BAT_NUMBER_OF_FAULTS1: [0x700],      # Number of high/low voltage, short circuit, overtemperature alarms 
        BAT_NUMBER_OF_FAULTS2: [0x750],      # Number of charge/discharge overcurrent and charge/discharge overtemperature alarms
        INTER_HIGH_LOW: [0x2098001],         # Minimal and maximal cell voltages including number of concerned cells
        INTER_CELL_VOLTAGES0: [0x4008001],   # Cell voltages 1-4
        INTER_CELL_VOLTAGES1: [0x4018001],   # Cell voltages 5-8
        INTER_CELL_VOLTAGES2: [0x4028001],   # Cell voltages 9-12
        INTER_CELL_VOLTAGES3: [0x4038001],   # Cell voltages 13-16
    }

    # bitmask helpers
    BITMASK = [
    int('0000000000000001', 2),  # Bit 0 
    int('0000000000000010', 2),  # Bit 1 
    int('0000000000000100', 2),  # Bit 2 
    int('0000000000001000', 2),  # Bit 3 
    int('0000000000010000', 2),  # Bit 4 
    int('0000000000100000', 2),  # Bit 5 
    int('0000000001000000', 2),  # Bit 6 
    int('0000000010000000', 2),  # Bit 7
    int('0000000100000000', 2),  # Bit 8
    int('0000001000000000', 2),  # Bit 9
    int('0000010000000000', 2),  # Bit 10
    int('0000100000000000', 2),  # Bit 11
    int('0001000000000000', 2),  # Bit 12
    int('0010000000000000', 2),  # Bit 13
    int('0100000000000000', 2),  # Bit 14
    int('1000000000000000', 2),  # Bit 15
    ]

    def connection_name(self) -> str:
        return "CAN " + self.port

    def test_connection(self):
        """
        call a function that will connect to the battery, send a command and retrieve the result.
        The result or call should be unique to this BMS. Battery name or version, etc.
        Return True if success, False for failure
        """
        result = False
        try:
            # Detection and initialisation of second INTERCAN bus interface
            result = self.init_intercan()
            if result is False:
                logger.info("No second CAN interface found. Use fallback simulation based on PCSCAN values")
            result = self.get_settings() # get settings to check if the data is valid and the connection is working
            # get the rest of the data to be sure, that all data is valid and the correct battery type is recognized
            # only read next data if the first one was successful, this saves time when checking multiple battery types
            if result is True:
                # Try to establish the CAN communications with the battery and read the first data
                ii_test = 1
                nn_test = 5 # Number of attempts
                while ii_test <= nn_test:
                    logger.info("Receiving data from the battery over CAN. Attempt " + str(ii_test) + " of " + str(nn_test))
                    result = self.refresh_data()
                    # Test, if initialisation is done and all requeired values are received over CAN
                    if result is True and self.init_done is True:
                        logger.info("Connection test successfully completed")
                        return result
                    ii_test +=1
        except Exception:
            (
                exception_type,
                exception_object,
                exception_traceback,
            ) = sys.exc_info()
            file = exception_traceback.tb_frame.f_code.co_filename
            line = exception_traceback.tb_lineno
            logger.error(f"Exception occurred: {repr(exception_object)} of type {exception_type} in {file} line #{line}")
            result = False

        return result

    def unique_identifier(self) -> str:
        """
        Used to identify a BMS when multiple BMS are connected
        Provide a unique identifier from the BMS to identify a BMS, if multiple same BMS are connected
        e.g. the serial number
        If there is no such value, please remove this function
        """
        return self.battery_serial_number1 + self.battery_serial_number2

    def init_intercan(self):
        # Detection and initialisation of second INTERCAN bus interface with cell voltages and settings

        from utils_can import CanReceiverThread, CanTransportInterface
        import subprocess

        self.intercan_available = False
        if self.intercan_port == "":
            # Automatic detection for a second CAN interface, if no port for INTERCAN was defined
            ip_out = subprocess.run(["ip", "link", "show", "type", "can"], capture_output=True, text=True, check=True)
            ip_out_filtered = "\n".join(x for x in ip_out.stdout.splitlines() if "link/can" not in x) # delete unnecessary rows from stdout
            ip_out_splited = ip_out_filtered.splitlines() # convert the string to a list
            number_of_cans = len(ip_out_splited) # number of detected cans
            if number_of_cans >= 2:
                for ip_out_row in ip_out_splited:
                    ip_out_row = ip_out_row.split(': <')[0] # cut the string after canX
                    begin_can_str=ip_out_row.find('can') # first position for canX in the string
                    ip_out_row = ip_out_row[begin_can_str:] # cut the string before canX
                    if ip_out_row != self.port:
                        self.intercan_port = ip_out_row
                        logger.info(f"Use automatic detected {self.intercan_port} as INTERCAN interface")
                        break
            if self.intercan_port == "":
                return False
        try:
            logger.info(f"Initialisation of second INTERCAN interface on {self.intercan_port}")
            can_thread = CanReceiverThread.get_instance(bustype="socketcan", channel=self.intercan_port)
        except Exception as e:
            logger.error(f"Error while accessing INTERCAN interface: {e}")
            self.intercan_port = ""
            return False

        # wait until thread has initialized
        if not can_thread.can_initialised.wait(2):
            logger.error("Timeout while accessing INTERCAN interface")
            self.intercan_port = ""
            return False

        try:
            baudrate = round(can_thread.get_bitrate(self.intercan_port) / 1000)
            can_transport_interface = CanTransportInterface()
            can_transport_interface.can_message_cache_callback = can_thread.get_message_cache
            can_transport_interface.can_bus = can_thread.can_bus
            can_thread.setup_can(channel=self.intercan_port, bitrate=baudrate, force=True)
        except Exception as e:
            logger.error(f"Error while accessing INTERCAN interface: {e}")
            self.intercan_port = ""
            return False

        self.intercan_available = True
        logger.info(f"INTERCAN interface initialised on {self.intercan_port} with bitrate {baudrate} kbps")

        return True

    def get_settings(self):
        # After successful connection get_settings() will be called to set up the battery
        # Set the current limits, populate cell count, etc
        # Return True if success, False for failure

        return True

    def refresh_data(self):
        # call all functions that will refresh the battery data.
        # This will be called for every iteration (1 second)
        # Return True if success, False for failure
        return self.read_status_data()

    def read_status_data(self):
        status_data = self.read_data_deye_CAN()
        # check if connection success
        if status_data is False:
            return False
        return True

    def init_battery_cell_settings(self):
        # init battery cell settings
        if self.cell_count == 1:
            if self.voltage > 0 and self.cell_mid_voltage > 0:
                # calculate number of cells based on the relationship between the whole battery voltage and mean cell voltage
                self.cell_count = int(round((self.voltage / self.cell_mid_voltage), 0))
                logger.info(f"Detected number of cells based on voltage relationship module/cell: {self.cell_count} ")
            else:
                self.cell_count = 16
                logger.info(f"Number of cells without automatic detection based on voltage relationship: {self.cell_count} ")

        # init the cell array add only missing cell instances
        missing_instances = self.cell_count - len(self.cells)
        if missing_instances > 0:
            for c in range(missing_instances):
                self.cells.append(Cell(False))
        return True

    def to_fet_bits(self, bat_mode_data, bat_balance_data):
        # set fet and balancing bits
        if bat_mode_data == 1:
            # mode 1: charging
            self.charge_fet = 1
            self.discharge_fet = 0
        elif bat_mode_data == 2:
            # mode 2: discharging
            self.charge_fet = 0
            self.discharge_fet = 1
        else:
            # mode 0: idle
            self.charge_fet = 0
            self.discharge_fet = 0
        if bat_balance_data == 0:
            # no balancing
            self.balance_fet = 0
        else:
            # balancing
            self.balance_fet = 1
        if self.init_done is True:
            # only if number of cells is known and cells are initialised
            for ii in range(self.cell_count):
                # set cell balancing status. True, if cell is balancing
                self.cells[ii].balance = False if bat_balance_data & self.BITMASK[ii] == 0 else True

    def reset_fet_bits(self, byte_data):
        # resset fet and balancing bits
        self.charge_fet = 0
        self.discharge_fet = 0
        self.balance_fet = 0
        if self.init_done is True:
            # only if number of cells is known and cells are initialised
            for ii in range(self.cell_count):
                # reset cell balancing status
                self.cells[ii].balance = False

    def to_protection_bits(self, bms_stat_data, bat_stat_data):
        # set protection bits
		
        # BMS warnings, errors and stats (collected for all batteries)
        (
            bms_warn0,
            bms_warn1_err1,
            bms_err2,
            bms_err3,
            bms_err4,
            bms_err5,
            bms_err6,
            bms_err7,
        ) = unpack_from(">BBBBBBBB", bms_stat_data)

        # Battery warnings, errors and stats (for each battery separately)
        (
            bat_warn0,
            bat_warn1_err1,
            bat_err2,
            bat_err3,
            bat_err4,
            bat_err5,
            bat_err6,
            bat_stat_fet,
        ) = unpack_from(">BBBBBBBB", bat_stat_data)
        
        logger.debug("bat_stat_fet = %s", "{:08b}".format(bat_stat_fet))

        if bms_err4 & self.BITMASK[0] or bat_err4 & self.BITMASK[0]:
            # High cell voltage levels - Alarm
            self.protection.high_cell_voltage = 2
        elif bms_warn0 & self.BITMASK[0] or bat_warn0 & self.BITMASK[0]:
            # High cell voltage Warning levels - Pre-alarm
            self.protection.high_cell_voltage = 1
        else:
            self.protection.high_cell_voltage = 0
        if bms_err4 & self.BITMASK[1] or bat_err4 & self.BITMASK[1]:
            # Low cell voltage levels - Alarm
            self.protection.low_cell_voltage = 2
        elif bms_warn0 & self.BITMASK[1] or bat_warn0 & self.BITMASK[1]:
            # Low cell voltage Warning levels - Pre-alarm
            self.protection.low_cell_voltage = 1
        else:
            self.protection.low_cell_voltage = 0
        if bms_err4 & self.BITMASK[2] or bat_err4 & self.BITMASK[2]:
            # High voltage levels - Alarm
            self.protection.high_voltage = 2
        elif bms_warn0 & self.BITMASK[2] or bat_warn0 & self.BITMASK[2]:
            # High voltage Warning levels - Pre-alarm
            self.protection.high_voltage = 1
        else:
            self.protection.high_voltage = 0
        if bms_err4 & self.BITMASK[3] or bat_err4 & self.BITMASK[3]:
            # Low voltage levels - Alarm
            self.protection.low_voltage = 2
        elif bms_warn0 & self.BITMASK[3] or bat_warn0 & self.BITMASK[3]:
            # Low voltage Warning levels - Pre-alarm
            self.protection.low_voltage = 1
        else:
            self.protection.low_voltage = 0
        if bms_err4 & self.BITMASK[4] or bat_err4 & self.BITMASK[4]:
            # High charge current levels - Alarm
            self.protection.high_charge_current = 2
        elif bms_warn0 & self.BITMASK[4] or bat_warn0 & self.BITMASK[4]:
            # High charge current levels - Pre-alarm
            self.protection.high_charge_current = 1
        else:
            self.protection.high_charge_current = 0
        if bms_err4 & self.BITMASK[5] or bat_err4 & self.BITMASK[5]:
            # High discharge current levels - Alarm
            self.protection.high_discharge_current = 2
        elif bms_warn0 & self.BITMASK[5] or bat_warn0 & self.BITMASK[5]:
            # High discharge current levels - Pre-alarm
            self.protection.high_discharge_current = 1
        else:
            self.protection.high_discharge_current = 0
        if bms_err4 & self.BITMASK[6] or bat_err4 & self.BITMASK[6]:
            # High charge temperature levels - Alarm
            self.protection.high_charge_temperature = 2
        elif bms_warn0 & self.BITMASK[6] or bat_warn0 & self.BITMASK[6]:
            # High charge temperature levels - Pre-alarm
            self.protection.high_charge_temperature = 1
        else:
            self.protection.high_charge_temperature = 0
        if bms_err4 & self.BITMASK[7] or bat_err4 & self.BITMASK[7]:
            # Low charge temperature levels - Alarm
            self.protection.low_charge_temperature = 2
        elif bms_warn0 & self.BITMASK[7] or bat_warn0 & self.BITMASK[7]:
            # Low charge temperature levels - Pre-alarm
            self.protection.low_charge_temperature = 1
        else:
            self.protection.low_charge_temperature = 0
        if bms_err5 & self.BITMASK[0] or bat_err5 & self.BITMASK[0]:
            # High discharge temperature levels - Alarm
            self.protection.high_temperature = 2
        elif bms_warn1_err1 & self.BITMASK[0] or bat_warn1_err1 & self.BITMASK[0]:
            # High discharge temperature levels - Pre-alarm
            self.protection.high_temperature = 1
        else:
            self.protection.high_temperature = 0
        if bms_err5 & self.BITMASK[1] or bat_err5 & self.BITMASK[1]:
            # Low discharge temperature levels - Alarm
            self.protection.low_temperature = 2
        elif bms_warn1_err1 & self.BITMASK[1] or bat_warn1_err1 & self.BITMASK[1]:
            # Low discharge temperature levels - Pre-alarm
            self.protection.low_temperature = 1
        else:
            self.protection.low_temperature = 0
        if bms_err5 & self.BITMASK[2] or bat_err5 & self.BITMASK[2]:
            # Cell imbalance - Alarm
            self.protection.cell_imbalance = 2
        elif bms_warn1_err1 & self.BITMASK[2] or bat_warn1_err1 & self.BITMASK[2]:
            # Cell imbalance - Pre-alarm
            self.protection.cell_imbalance = 1
        else:
            self.protection.cell_imbalance = 0
        if bms_err5 & 56 or bms_err6 & 9 or bat_err5 & 56 or bat_err6 & 9:
            # High internal temperature levels - Alarm
            self.protection.high_internal_temperature = 2
        elif bms_warn1_err1 & 56 or bat_warn1_err1 & 56:
            # High internal temperature - Pre-alarm
            self.protection.high_internal_temperature = 1
        else:
            self.protection.high_internal_temperature = 0
        if bms_err6 & self.BITMASK[4] or bat_err6 & self.BITMASK[4]:
            # Fuse blown - Alarm
            self.protection.fuse_blown = 2
        else:
            self.protection.fuse_blown = 0
        if bms_warn1_err1 & 192 or bms_err2 or bms_err3 or bms_err5 & 192 or bms_err6 & 230 or bat_warn1_err1 & 192 or bat_err2 or bat_err3 or bat_err5 & 192 or bat_err6 & 230:
            # Internal failure - Alarm (All other failures, which are not listed separately)
            self.protection.internal_failure = 2
        else:
            self.protection.internal_failure = 0

    def reset_protection_bits(self):
        # reset protection bits
        self.protection.high_cell_voltage = 0
        self.protection.low_cell_voltage = 0
        self.protection.high_voltage = 0
        self.protection.low_voltage = 0
        self.protection.high_charge_current = 0
        self.protection.high_discharge_current = 0
        self.protection.high_charge_temp = 0
        self.protection.low_charge_temp = 0
        self.protection.high_temperature = 0
        self.protection.low_temperature = 0
        self.protection.cell_imbalance = 0
        self.protection.high_internal_temperature = 0
        self.protection.fuse_blown = 0
        self.protection.internal_failure = 0

    def simulate_cell_voltages(self):
        # fetch data from min/max values if no InterCAN available
        self.cells = [Cell(False) for _ in range(self.cell_count)]

        for i in range(self.cell_count):
            # loop through all cells and set the mean voltage
            self.cells[i].voltage = round(self.cell_mid_voltage, 3)

    def read_data_deye_CAN(self):
        # read CAN data
        bms_check = 0                     # value to check if all needed BMS data received over PCSCAN is available
        bat_check = 0                     # value to check if all needed BATTERY data received over PCSCAN is available
        intercan_check = 0                # value to check if all needed data received over INTERCAN is available
        mean_cell_volt_available = False  # mean cell voltage is calculated based on min and max cell voltage 

        if self.pcscan_bus is False:
            logger.debug("PCSCAN bus init")
            # init PCSCAN interface
            try:
                self.pcscan_bus = can.interface.Bus(bustype=self.CAN_BUS_TYPE, channel=self.port)
                logger.debug(f"bustype: {self.CAN_BUS_TYPE}, channel: {self.port}, bitrate: {self.baud_rate}")
                self.pcscan_timeout = False
            except can.CanError as e:
                logger.error(e)
            if self.pcscan_bus is None:
                logger.error("PCSCAN bus init failed")
                return False
            logger.debug("PCSCAN bus init done")

        if self.intercan_bus is False:
            logger.debug("INTERCAN bus init")
            # init INTERCAN interface
            try:
                self.intercan_bus = can.interface.Bus(bustype=self.CAN_BUS_TYPE, channel=self.intercan_port)
                logger.debug(f"bustype: {self.CAN_BUS_TYPE}, channel: {self.intercan_port}, bitrate: {self.baud_rate}")
                self.intercan_timeout = False
                self.intercan_timeout_count = 0
            except can.CanError as e:
                logger.error(e)
            if self.intercan_bus is None:
                logger.error("INTERCAN bus init failed")
                return False
            logger.debug("INTERCAN bus init done")

        try:
            if ((time.time() - self.last_error_time) > self.ERROR_STATUS_TIMEOUT) and self.error_active is True:
                self.error_active = False # reset errors after timeout
                logger.debug("Reseting error and warning bits after timeout")
                self.reset_protection_bits()

            if ((time.time() - self.last_fet_status_time) > self.ERROR_STATUS_TIMEOUT) and self.fet_status_active is True:
                self.fet_status_active = False # reset fet bits after timeout
                logger.debug("Reseting MOSFET and status bits after timeout")
                self.reset_fet_bits()

            if ((time.time() - self.high_low_intercan_time) > self.INTERCAN_VALUES_TIMEOUT) and self.high_low_intercan is True:
                self.high_low_intercan = False # reset highest and lowest cell voltages message over INTERCAN active flag after timeout
                logger.warning("Timeout occurred when receiving highest and lowest cell voltages over INTERCAN. Switch to PCSCAN fallback")

            if ((time.time() - self.cell_voltages_time) > self.INTERCAN_VALUES_TIMEOUT) and self.cell_voltages_intercan is True:
                self.cell_voltages_intercan = False # reset cell voltages active flag after timeout
                logger.warning("Timeout occurred when receiving cell voltages over INTERCAN. Switch to PCSCAN fallback and to simulated values")

            messages_to_read = self.MESSAGES_TO_READ # counter for received CAN messages (common for both PCSCAN and INTERCAN)
            intercan_last_recv = self.MESSAGES_TO_READ # special counter storage for INTERCAN messages
            while messages_to_read > 0:
                # main while loop to pull/receive of CAN messages on both PCSCAN and INTERCAN (if available) and translate/convert these to according values 
                pcscan_msg = self.pcscan_bus.recv(1) # receive PCSCAN message
                if pcscan_msg is None:
                    if self.pcscan_timeout is False:
                        logger.warning("No CAN Message on PCSCAN received") # log it only first time, if timeout occurs
                    self.pcscan_timeout = True
                elif self.pcscan_timeout is True:
                    self.pcscan_timeout = False
                    logger.info("CAN Message on PCSCAN received again") # info log, if PCSCAN messages are available again

                intercan_msg = None
                if self.intercan_timeout_count < self.INTERCAN_TIMEOUT:
                    if self.intercan_timeout_count == 0 or intercan_last_recv - messages_to_read >= self.INTERCAN_SKIPED_RECVS:
                        # Receive INTERCAN message only if no issues were detected before or a defined number of messages was skiped already
                        # This measure avoids delays in the main loop during the message pulling on the INTERCAN device, if no messages are receiving 
                        # In such a case, each recv call takes approximately 1 second and results in a total delay of 100 seconds for the main loop
                        intercan_last_recv = messages_to_read
                        intercan_msg = self.intercan_bus.recv(1)

                if intercan_msg is None:
                    if self.intercan_timeout is False:
                        logger.warning("No CAN Message on INTERCAN received") # log it only first time, if timeout occurs
                        if self.high_low_intercan is False or self.cell_voltages_intercan is False: 
                            logger.warning("PCSCAN fallback and simulated values are used to replace missing values from INTERCAN")
                    self.intercan_timeout = True
                    if self.intercan_timeout_count < self.INTERCAN_TIMEOUT:
                        self.intercan_timeout_count += 1
                        if self.intercan_timeout_count == self.INTERCAN_TIMEOUT:
                            logger.warning("INTERCAN interface will no longer be polled for new messages until you restart the service")
                            logger.warning("PCSCAN fallback and simulated values are used to replace missing values from INTERCAN")
                elif self.intercan_timeout is True:
                    self.intercan_timeout = False
                    self.intercan_timeout_count = 0
                    logger.info("CAN Message on INTERCAN received again") # info log, if INTERCAN messages are available again

                if self.pcscan_timeout is True and self.intercan_timeout is True:
                    # return without decoding of messages, if both PCSCAN and INTERCAN achieved timeout
                    return False

                if pcscan_msg is not None:
                    messages_to_read -= 1
                    if pcscan_msg.arbitration_id in self.CAN_FRAMES[self.BMS_LIM_VOLT_CURR]:
                        # BMS limits: Maximal and minimal charge and discharge voltages, maximal charge and discharge currents
                        self.max_battery_voltage = unpack_from("<H", bytes([pcscan_msg.data[0], pcscan_msg.data[1]]))[0] / 10
                        self.max_battery_charge_current = unpack_from("<h", bytes([pcscan_msg.data[2], pcscan_msg.data[3]]))[0] / 10
                        self.max_battery_discharge_current = unpack_from("<h", bytes([pcscan_msg.data[4], pcscan_msg.data[5]]))[0] / 10
                        self.min_battery_voltage = unpack_from("<H", bytes([pcscan_msg.data[6], pcscan_msg.data[7]]))[0] / 10
                        bms_check |= self.BITMASK[0]

                    elif pcscan_msg.arbitration_id in self.CAN_FRAMES[self.BMS_SOC_SOH]:
                        # BMS SOC and SOH
                        self.soc = unpack_from("<H", bytes([pcscan_msg.data[0], pcscan_msg.data[1]]))[0]
                        self.soh = unpack_from("<H", bytes([pcscan_msg.data[2], pcscan_msg.data[3]]))[0]
                        bms_check |= self.BITMASK[1]

                    elif pcscan_msg.arbitration_id in self.CAN_FRAMES[self.BMS_VOLT_CURR_TEMP]:
                        # BMS voltage, current and temperature
                        self.voltage = unpack_from("<h", bytes([pcscan_msg.data[0], pcscan_msg.data[1]]))[0] / 100
                        self.current = unpack_from("<h", bytes([pcscan_msg.data[2], pcscan_msg.data[3]]))[0] / -10 * INVERT_CURRENT_MEASUREMENT
                        temperature_1 = unpack_from("<h", bytes([pcscan_msg.data[4], pcscan_msg.data[5]]))[0] / 10
                        self.to_temperature(1, temperature_1)
                        self.init_check |= self.BITMASK[0]
                        bms_check |= self.BITMASK[2]
                        
                    elif pcscan_msg.arbitration_id in self.CAN_FRAMES[self.BMS_BAT_DATA]:
                        # BMS manufacturer name, battery pack number, battery type and battery capacity
                        bms_manufacturer_name = "".join(map(chr, bytes([pcscan_msg.data[0], pcscan_msg.data[1]]))) # usualy DY as ASCII
                        bms_battery_pack_number = "".join(map(chr, bytes([pcscan_msg.data[2], pcscan_msg.data[3], pcscan_msg.data[4]]))) # usualy 001 as ASCII
                        bms_battery_type = unpack_from("<B", bytes([pcscan_msg.data[5]]))[0]
                        # DEYE specific battery code for cell manufacturer and cell types
                        if bms_battery_type == 1:
                            bms_bat_type_ascii = "GOTION 96Ah"
                        elif bms_battery_type == 2:
                            bms_bat_type_ascii = "CATL 100Ah"
                        elif bms_battery_type == 3:
                            bms_bat_type_ascii = "EVE 100Ah"
                        elif bms_battery_type == 4:
                            bms_bat_type_ascii = "PH 100Ah"
                        elif bms_battery_type == 5:
                            bms_bat_type_ascii = "EVE 120Ah"
                        elif bms_battery_type == 6:
                            bms_bat_type_ascii = "PH 100Ah(214R)"
                        elif bms_battery_type == 7:
                            bms_bat_type_ascii = "ZENERGY 104Ah"
                        else:
                            bms_bat_type_ascii = "TYP " + str(bms_battery_type) # fallback for all other types as TYP XY
                        self.type = bms_manufacturer_name + bms_battery_pack_number + " " + bms_bat_type_ascii # compose the battery type based of all information
                        self.capacity = unpack_from("<H", bytes([pcscan_msg.data[6], pcscan_msg.data[7]]))[0] / 10
                        self.init_check |= self.BITMASK[1]
                        bms_check |= self.BITMASK[3]

                    elif pcscan_msg.arbitration_id in self.CAN_FRAMES[self.BMS_MIN_MAX_CELL_DATA]:
                        # Collected BMS information: Minimal and maximal cell voltage and temperature (without number of concerned cell)
                        if self.high_low_intercan is False:
                            self.cell_max_voltage = unpack_from("<H", bytes([pcscan_msg.data[0], pcscan_msg.data[1]]))[0] / 1000
                            self.cell_min_voltage = unpack_from("<H", bytes([pcscan_msg.data[2], pcscan_msg.data[3]]))[0] / 1000
                            self.cell_mid_voltage = (self.cell_min_voltage + self.cell_max_voltage) / 2 # calculate mean cell voltage based on min and max values
                            self.init_check |= self.BITMASK[2]
                            bms_check |= self.BITMASK[4]
                            mean_cell_volt_available = True
                            if self.cell_voltages_intercan is False and self.init_done is True:
                                self.simulate_cell_voltages()  # simulate cell voltages, if no cell voltages were received over INTERCAN
                        temperature_2 = unpack_from("<h", bytes([pcscan_msg.data[4], pcscan_msg.data[5]]))[0] / 10
                        self.to_temperature(2, temperature_2) # use Temperature 2 as maximal cell temperature
                        temperature_3 = unpack_from("<h", bytes([pcscan_msg.data[6], pcscan_msg.data[7]]))[0] / 10
                        self.to_temperature(3, temperature_3) # use Temperature 3 as minimal cell temperature
                        bms_check |= self.BITMASK[5]

                    elif pcscan_msg.arbitration_id in self.CAN_FRAMES[self.BMS_SW_HW]:
                        # BMS software and hardware version
                        self.bms_software_version = f'{int(pcscan_msg.data[0]):X}'.rjust(2,'0') + f'{int(pcscan_msg.data[1]):X}'.rjust(2,'0')
                        self.custom_field = "BMS: " + self.bms_software_version + " Firmware: " + self.battery_software_version + " BOOT: " + self.battery_boot_version
                        self.hardware_version = f'{int(pcscan_msg.data[2]):X}'.rjust(2,'0') + f'{int(pcscan_msg.data[3]):X}'.rjust(2,'0')
                        self.init_check |= self.BITMASK[3]
                        bms_check |= self.BITMASK[6]

                    elif pcscan_msg.arbitration_id in self.CAN_FRAMES[self.BMS_MODULE_STAT]:
                        # Collected BMS status bits for all batteries
                        bms_num_of_bat_in_operation = unpack_from("<B", bytes([pcscan_msg.data[0]]))[0]
                        bms_num_of_bat_prohibited_charging = unpack_from("<B", bytes([pcscan_msg.data[1]]))[0]
                        bms_num_of_bat_prohibited_discharging = unpack_from("<B", bytes([pcscan_msg.data[2]]))[0]
                        bms_num_of_bat_com_disconnect = unpack_from("<B", bytes([pcscan_msg.data[3]]))[0]
                        bms_num_of_bat_in_parallel = unpack_from("<B", bytes([pcscan_msg.data[4]]))[0]
                        bms_check |= self.BITMASK[7]

                    elif pcscan_msg.arbitration_id in self.CAN_FRAMES[self.BMS_ERR_WARN_ALM]:
                        # Collected alarms and status bits from BMS for all batteries
                        self.bms_alarms = pcscan_msg.data
                        logger.debug("CAN Message Data BMS alarms: %s",self.bms_alarms.hex())
                        self.last_error_time = time.time()
                        self.error_active = True
                        self.to_protection_bits(self.bms_alarms, self.bat_alarms)
                        bms_check |= self.BITMASK[8]

                    elif pcscan_msg.arbitration_id in self.CAN_FRAMES[self.BAT_TEMP_MAX_CURR]:
                        # Individual MOSFET and HEATING temperatures, minimal and maximal battery current for each battery
                        temperature_0 = unpack_from("<h", bytes([pcscan_msg.data[0], pcscan_msg.data[1]]))[0] / 10
                        self.to_temperature(0, temperature_0)
                        temperature_4 = unpack_from("<h", bytes([pcscan_msg.data[2], pcscan_msg.data[3]]))[0] / 10
                        self.to_temperature(4, temperature_4)
						# optional min and max battery currents for each separate battery instead of collected bms value for all batteries in sum
#                        self.max_battery_current_bms = unpack_from("<H", bytes([pcscan_msg.data[4], pcscan_msg.data[5]]))[0]
#                        self.min_battery_current_bms = unpack_from("<H", bytes([pcscan_msg.data[6], pcscan_msg.data[7]]))[0]
                        bat_check |= self.BITMASK[0]

                    elif pcscan_msg.arbitration_id in self.CAN_FRAMES[self.BAT_SYS_STAT]:
                        # Individual operation mode, failure level, charge cycles, balancing status and system substate for each battery
                        battery_operation_mode = unpack_from("<B", bytes([pcscan_msg.data[0]]))[0]
                        battery_failure_level = unpack_from("<B", bytes([pcscan_msg.data[1]]))[0]
                        self.history.charge_cycles = unpack_from("<H", bytes([pcscan_msg.data[2], pcscan_msg.data[3]]))[0]
                        battery_balancing_status = unpack_from(">H", bytes([pcscan_msg.data[4], pcscan_msg.data[5]]))[0]
                        battery_system_substate = unpack_from("<B", bytes([pcscan_msg.data[6]]))[0]
                        self.last_fet_status_time = time.time()
                        self.fet_status_active = True
                        self.to_fet_bits(battery_operation_mode, battery_balancing_status)
                        self.init_check |= self.BITMASK[4]
                        bat_check |= self.BITMASK[1]

                    elif pcscan_msg.arbitration_id in self.CAN_FRAMES[self.BAT_SW_DATA]:
                        # Individual software and boot version for each battery
                        self.battery_software_version = f'{int(pcscan_msg.data[0]):X}'.rjust(2,'0') + f'{int(pcscan_msg.data[1]):X}'.rjust(2,'0')
                        self.battery_boot_version = "".join(map(chr, bytes([pcscan_msg.data[3], pcscan_msg.data[4], pcscan_msg.data[5], pcscan_msg.data[6], pcscan_msg.data[7]])))
                        self.custom_field = "BMS: " + self.bms_software_version + " Firmware: " + self.battery_software_version + " BOOT: " + self.battery_boot_version
                        self.init_check |= self.BITMASK[5]
                        bat_check |= self.BITMASK[2]

                    elif pcscan_msg.arbitration_id in self.CAN_FRAMES[self.BAT_SERIAL1]:
                        # Battery serial number part 1 of 2
                        self.battery_serial_number1 =  "".join(map(chr, pcscan_msg.data))
                        self.init_check |= self.BITMASK[6]
                        bat_check |= self.BITMASK[3]

                    elif pcscan_msg.arbitration_id in self.CAN_FRAMES[self.BAT_SERIAL2]:
                        # Battery serial number part 2 of 2
                        self.battery_serial_number2 =  "".join(map(chr, pcscan_msg.data))
                        self.init_check |= self.BITMASK[7]
                        bat_check |= self.BITMASK[4]

                    elif pcscan_msg.arbitration_id in self.CAN_FRAMES[self.BAT_ERR_WARN_ALM_STAT]:
                        # Individual alarms and status bits for each battery
                        self.bat_alarms = pcscan_msg.data
                        logger.debug("CAN Message Data BAT alarms: %s",self.bat_alarms.hex())
                        self.last_error_time = time.time()
                        self.error_active = True
                        self.to_protection_bits(self.bms_alarms, self.bat_alarms)
                        bat_check |= self.BITMASK[5]

                    elif pcscan_msg.arbitration_id in self.CAN_FRAMES[self.BAT_ENERGY]:
                        # Total charged and discharged energy for each battery
                        self.history.charged_energy = unpack_from("<L", bytes([pcscan_msg.data[0], pcscan_msg.data[1], pcscan_msg.data[2], pcscan_msg.data[3]]))[0] / 1000
                        self.history.discharged_energy = unpack_from("<L", bytes([pcscan_msg.data[4], pcscan_msg.data[5], pcscan_msg.data[6], pcscan_msg.data[7]]))[0] / 1000
                        bat_check |= self.BITMASK[6]

                    elif pcscan_msg.arbitration_id in self.CAN_FRAMES[self.BAT_NUMBER_OF_FAULTS1]:
                        # Number of high/low voltage, short circuit, overtemperature alarms
                        self.history.high_voltage_alarms = unpack_from("<H", bytes([pcscan_msg.data[0], pcscan_msg.data[1]]))[0]
                        self.history.low_voltage_alarms = unpack_from("<H", bytes([pcscan_msg.data[2], pcscan_msg.data[3]]))[0]
                        bat_check |= self.BITMASK[7]

                if intercan_msg is not None:
                    messages_to_read -= 1
                    # highest and lowest cell voltages received over INTERCAN (if available)
                    if intercan_msg.arbitration_id in self.CAN_FRAMES[self.INTER_HIGH_LOW]:
                        self.cell_max_voltage = unpack_from(">H", bytes([intercan_msg.data[0], intercan_msg.data[1]]))[0] / 1000
                        self.cell_max_no = unpack_from("<B", bytes([intercan_msg.data[2]]))[0] # cell number for maximal cell voltage
                        self.cell_min_voltage = unpack_from(">H", bytes([intercan_msg.data[3], intercan_msg.data[4]]))[0] / 1000
                        self.cell_min_no = unpack_from("<B", bytes([intercan_msg.data[5]]))[0] # cell number for minimal cell voltage
                        self.cell_mid_voltage = (self.cell_min_voltage + self.cell_max_voltage) / 2 # calculate mean cell voltage based on min and max values
                        mean_cell_volt_available = True
                        self.init_check |= self.BITMASK[2]
                        if self.cell_voltages_intercan is False and self.init_done is True:
                            self.simulate_cell_voltages()  # simulate cell voltages, if no cell voltages were received over INTERCAN
                        if self.high_low_intercan is False and self.init_done is True:
                            logger.info("Receive highest and lowest cell voltages from INTERCAN instead of PCSCAN")
                        self.high_low_intercan_time = time.time()
                        self.high_low_intercan = True
                        intercan_check |= self.BITMASK[0]

                    # cell voltages received over INTERCAN (if available)
                    elif self.init_done is True and intercan_msg.arbitration_id in self.CAN_FRAMES[self.INTER_CELL_VOLTAGES0]:
                        # cell voltages 1-4
                        self.cells[0].voltage = unpack_from(">H", bytes([intercan_msg.data[0], intercan_msg.data[1]]))[0] / 1000
                        self.cells[1].voltage = unpack_from(">H", bytes([intercan_msg.data[2], intercan_msg.data[3]]))[0] / 1000
                        self.cells[2].voltage = unpack_from(">H", bytes([intercan_msg.data[4], intercan_msg.data[5]]))[0] / 1000
                        self.cells[3].voltage = unpack_from(">H", bytes([intercan_msg.data[6], intercan_msg.data[7]]))[0] / 1000
                        if self.cell_voltages_intercan is False and self.init_done is True:
                            logger.info("Receive cell voltages from INTERCAN instead of simulation using min and max values from PCSCAN")
                        self.cell_voltages_time = time.time()
                        self.cell_voltages_intercan = True
                        intercan_check |= self.BITMASK[1]

                    elif self.init_done is True and intercan_msg.arbitration_id in self.CAN_FRAMES[self.INTER_CELL_VOLTAGES1]:
                        # cell voltages 5-8
                        self.cells[4].voltage = unpack_from(">H", bytes([intercan_msg.data[0], intercan_msg.data[1]]))[0] / 1000
                        self.cells[5].voltage = unpack_from(">H", bytes([intercan_msg.data[2], intercan_msg.data[3]]))[0] / 1000
                        self.cells[6].voltage = unpack_from(">H", bytes([intercan_msg.data[4], intercan_msg.data[5]]))[0] / 1000
                        self.cells[7].voltage = unpack_from(">H", bytes([intercan_msg.data[6], intercan_msg.data[7]]))[0] / 1000
                        if self.cell_voltages_intercan is False and self.init_done is True:
                            logger.info("Receive cell voltages from INTERCAN instead of simulation using min and max values from PCSCAN")
                        self.cell_voltages_time = time.time()
                        self.cell_voltages_intercan = True
                        intercan_check |= self.BITMASK[2]

                    elif self.init_done is True and intercan_msg.arbitration_id in self.CAN_FRAMES[self.INTER_CELL_VOLTAGES2]:
                        # cell voltages 9-12
                        self.cells[8].voltage = unpack_from(">H", bytes([intercan_msg.data[0], intercan_msg.data[1]]))[0] / 1000
                        self.cells[9].voltage = unpack_from(">H", bytes([intercan_msg.data[2], intercan_msg.data[3]]))[0] / 1000
                        self.cells[10].voltage = unpack_from(">H", bytes([intercan_msg.data[4], intercan_msg.data[5]]))[0] / 1000
                        self.cells[11].voltage = unpack_from(">H", bytes([intercan_msg.data[6], intercan_msg.data[7]]))[0] / 1000
                        if self.cell_voltages_intercan is False and self.init_done is True:
                            logger.info("Receive cell voltages from INTERCAN instead of simulation using min and max values from PCSCAN")
                        self.cell_voltages_time = time.time()
                        self.cell_voltages_intercan = True
                        intercan_check |= self.BITMASK[3]

                    elif self.init_done is True and intercan_msg.arbitration_id in self.CAN_FRAMES[self.INTER_CELL_VOLTAGES3]:
                        # cell voltages 13-16
                        self.cells[12].voltage = unpack_from(">H", bytes([intercan_msg.data[0], intercan_msg.data[1]]))[0] / 1000
                        self.cells[13].voltage = unpack_from(">H", bytes([intercan_msg.data[2], intercan_msg.data[3]]))[0] / 1000
                        self.cells[14].voltage = unpack_from(">H", bytes([intercan_msg.data[4], intercan_msg.data[5]]))[0] / 1000
                        self.cells[15].voltage = unpack_from(">H", bytes([intercan_msg.data[6], intercan_msg.data[7]]))[0] / 1000
                        if self.cell_voltages_intercan is False and self.init_done is True:
                            logger.info("Receive cell voltages from INTERCAN instead of simulation using min and max values from PCSCAN")
                        self.cell_voltages_time = time.time()
                        self.cell_voltages_intercan = True
                        intercan_check |= self.BITMASK[4]

                if self.init_done is False and self.init_check & 255 == 255:
                    self.init_done = self.init_battery_cell_settings() # init of battery cell settings after required values are received
                    logger.debug("self.init_done = %d", self.init_done)
                # bitwise status for receiving of CAN messages on PCSCAN and INTERCAN and status the INITIALISATION. Each bit represents respectively one CAN message or one init condition 
                logger.debug("bms_check = %s, bat_check = %s, intercan_check = %s, self.init_check = %s", "{:016b}".format(bms_check), "{:016b}".format(bat_check), "{:016b}".format(intercan_check), "{:016b}".format(self.init_check))
            return True

        except Exception:
            (
                exception_type,
                exception_object,
                exception_traceback,
            ) = sys.exc_info()
            file = exception_traceback.tb_frame.f_code.co_filename
            line = exception_traceback.tb_lineno
            logger.error(f"Exception occurred: {repr(exception_object)} of type {exception_type} in {file} line #{line}")
            return False
