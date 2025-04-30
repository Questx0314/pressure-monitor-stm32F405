import serial
import time
from threading import Lock, Condition
from queue import Queue
import numpy as np

class DataReader:
    def __init__(self, port):
        self.serial_port = port
        self.baud_rate = 115200
        self.ser = None
        self.connected = False
        
        # Initialize data structures
        self.data_queue = Queue()
        self.data_queue_lock = Lock()
        self.data_queue_condition = Condition()
        self.channel_buffers = [[] for _ in range(4)]
        self.last_median_values = [0.0] * 4

        # Constants for conversion
        self.ADC_MAX = 4095
        self.VOLTAGE_REF = 3.0
        self.CURRENT_MAX = 20.0
        self.PRESSURE_MAX = 40.0
        

    def adc_to_voltage(self, adc_value):
        """Convert ADC value to voltage (0-3.3V)"""
        return (adc_value / self.ADC_MAX) * self.VOLTAGE_REF

    def voltage_to_current(self, voltage):
        """Convert voltage to current (0-20mA)"""
        return (voltage / self.VOLTAGE_REF) * self.CURRENT_MAX

    def current_to_pressure(self, current):
        """Convert current to pressure (0-40MPa)"""
        return (current / self.CURRENT_MAX) * self.PRESSURE_MAX

    def process_batch(self, batch_size=5, channel_num=4):
        """Communicate with MCU batch_size times and return median values for each channel"""
        if not self.connected:
            return None
            
        results = []
        for _ in range(batch_size):
            try:
                # Send data request to MCU
                self.ser.write(b"data request\n")
                
                # Read response
                raw_data = self.ser.readline().decode('utf-8').strip()
                if raw_data:
                    # Parse the data format: "CH0: 1304 | CH1: 1260 | CH2: 1319 | CH3: 1300 | CH4: 1267"
                    channels = raw_data.split('|')
                    values = [int(ch.split(':')[1].strip()) for ch in channels[:5]]
                    
                    # Check if voltage exists (CH0)
                    # if values[0] >= 1000:
                    if values[0] <= 1000:
                        # Convert ADC values to pressure (only for CH1-CH4)
                        print(f"Raw ADC values: {values}")
                        pressure_values = [
                            self.current_to_pressure(
                                self.voltage_to_current(
                                    self.adc_to_voltage(value)
                                )
                            )
                            for value in values[1:5]
                        ]
                        
                        if len(pressure_values) == 4:
                            results.append(pressure_values)
                    
            except Exception as e:
                print(f"Error in process_batch: {str(e)}")
                continue
        
        if not results:
            return None
            
        # Calculate median for each channel
        medians = []
        for i in range(channel_num):
            channel_values = [result[i] for result in results]
            medians.append(np.median(channel_values))
            
        return medians

    def test_connection(self):
        """Test the connection to the MCU"""
        try:
            self.ser = serial.Serial(self.serial_port, self.baud_rate, timeout=1)
            self.ser.write(b"FS connect\n")  # Send connection request
            response = self.ser.readline().decode('utf-8').strip()
            if "connect success" in response:  # Check for success response
                self.connected = True
                return True
            return False
        except Exception as e:
            print(f"Connection test failed: {str(e)}")
            return False

    def get_latest_data(self):
        """Get the latest median values"""
        return self.last_median_values

    def stop(self):
        """Stop the data reading and clean up"""
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.connected = False
