import struct
import time
import logging
from datetime import datetime, timedelta
from Crypto.Cipher import AES
try:
    from Queue import Queue, Empty, Full
except ImportError:
    from queue import Queue, Empty, Full
from bluepy.btle import Peripheral, DefaultDelegate, ADDR_TYPE_RANDOM, BTLEException
from constants import UUIDS, AUTH_STATES, ALERT_TYPES, QUEUE_TYPES
from threading import Event


class AuthenticationDelegate(DefaultDelegate):

    """This Class inherits DefaultDelegate to handle the authentication process."""

    def __init__(self, device):
        DefaultDelegate.__init__(self)
        self.device = device

    def handleNotification(self, hnd, data):
        if hnd == self.device._char_auth.getHandle():
            if data[:3] == b'\x10\x01\x01':
                self.device._req_rdn()
            elif data[:3] == b'\x10\x01\x04':
                self.device.state = AUTH_STATES.KEY_SENDING_FAILED
            elif data[:3] == b'\x10\x02\x01':
                random_nr = data[3:]
                self.device._send_enc_rdn(random_nr)
            elif data[:3] == b'\x10\x02\x04':
                self.device.state = AUTH_STATES.REQUEST_RN_ERROR
            elif data[:3] == b'\x10\x03\x01':
                self.device.state = AUTH_STATES.AUTH_OK
            elif data[:3] == b'\x10\x03\x04':
                self.device.status = AUTH_STATES.ENCRIPTION_KEY_FAILED
                self.device._send_key()
            else:
                self.device.state = AUTH_STATES.AUTH_FAILED
        elif hnd == self.device._char_sensor_measure.getHandle():
            self.device.queue.put((QUEUE_TYPES.RAW_ACCEL, data))
        elif hnd == self.device._char_fetch.getHandle():
            if data[:3] == b'\x10\x01\x01':
                # get timestamp from what date the data actually is received
                year = struct.unpack("<H", data[7:9])[0]
                month = struct.unpack("b", data[9:10])[0]
                day = struct.unpack("b", data[10:11])[0]
                hour = struct.unpack("b", data[11:12])[0]
                minute = struct.unpack("b", data[12:13])[0]
                self.device.first_timestamp = datetime(year, month, day, hour, minute)
                print("Fetch data from {}-{}-{} {}:{}".format(year, month, day, hour, minute))
                self.device._char_fetch.write(b'\x02', False)
            elif data[:3] == b'\x10\x02\x01':
                self.device.active = False
                return
            else:
                print("Unexpected data on handle " + str(hnd) + ": " + str(data.encode("hex")))
                return
        else:
            self.device._log.error("Unhandled Response " + hex(hnd) + ": " +
                                   str(data.encode("hex")) + " len:" + str(len(data)))


class MiBand2(Peripheral):
    _KEY = b'\xf5\xd2\x29\x87\x65\x0a\x1d\x82\x05\xab\x82\xbe\xb9\x38\x59\xcf'
    _send_key_cmd = struct.pack('<18s', b'\x01\x00' + _KEY)
    _send_rnd_cmd = struct.pack('<2s', b'\x02\x00')
    _send_enc_key = struct.pack('<2s', b'\x03\x00')
    pkg = 0

    def __init__(self, mac_address, timeout=0.5, debug=False, accel_max_Q=300):
        self._stop_getting_real_time = Event()
        FORMAT = '%(asctime)-15s %(name)s (%(levelname)s) > %(message)s'
        logging.basicConfig(format=FORMAT)
        log_level = logging.WARNING if not debug else logging.DEBUG
        self._log = logging.getLogger(self.__class__.__name__)
        self._log.setLevel(log_level)
        self._log.info('Connecting to ' + mac_address)
        Peripheral.__init__(self, mac_address, addrType=ADDR_TYPE_RANDOM)
        self._log.info('Connected')
        self.timeout = timeout
        self.mac_address = mac_address
        self.state = None
        self.queue = Queue()
        self.accel_queue = Queue(maxsize=accel_max_Q)
        self.accel_raw_callback = None
        self.svc_1 = self.getServiceByUUID(UUIDS.SERVICE_MIBAND1)
        self.svc_2 = self.getServiceByUUID(UUIDS.SERVICE_MIBAND2)
        self._char_auth = self.svc_2.getCharacteristics(UUIDS.CHARACTERISTIC_AUTH)[0]
        self._desc_auth = self._char_auth.getDescriptors(forUUID=UUIDS.NOTIFICATION_DESCRIPTOR)[0]
        self._char_sensor_ctrl = self.svc_1.getCharacteristics(UUIDS.CHARACTERISTIC_SENSOR_CONTROL)[0]
        self._char_sensor_measure = self.svc_1.getCharacteristics(UUIDS.CHARACTERISTIC_SENSOR_MEASURE)[0]
        self._auth_notif(True)   # Enable auth service notifications on startup
        self.waitForNotifications(0.1)                  # Let MiBand2 to settle

    # Auth helpers ############################################################

    def _auth_notif(self, enabled):
        if enabled:
            self._log.info("Enabling Auth Service notifications status...")
            self._desc_auth.write(b"\x01\x00", True)
        elif not enabled:
            self._log.info("Disabling Auth Service notifications status...")
            self._desc_auth.write(b"\x00\x00", True)
        else:
            self._log.error("Something went wrong while changing the Auth Service notifications status...")

    def _auth_previews_data_notif(self, enabled):
        if enabled:
            self._log.info("Enabling Fetch Char notifications status...")
            self._desc_fetch.write(b"\x01\x00", True)
            self._log.info("Enabling Activity Char notifications status...")
            self._desc_activity.write(b"\x01\x00", True)
        elif not enabled:
            self._log.info("Disabling Fetch Char notifications status...")
            self._desc_fetch.write(b"\x00\x00", True)
            self._log.info("Disabling Activity Char notifications status...")
            self._desc_activity.write(b"\x00\x00", True)
        else:
            self._log.error("Something went wrong while changing the Fetch and Activity notifications status...")

    def _encrypt(self, message):
        aes = AES.new(self._KEY, AES.MODE_ECB)
        return aes.encrypt(message)

    def _send_key(self):
        self._log.info("Sending Key...")
        self._char_auth.write(self._send_key_cmd)
        self.waitForNotifications(self.timeout)

    def _req_rdn(self):
        self._log.info("Requesting random number...")
        self._char_auth.write(self._send_rnd_cmd)
        self.waitForNotifications(self.timeout)

    def _send_enc_rdn(self, data):
        self._log.info("Sending encrypted random number")
        cmd = self._send_enc_key + self._encrypt(data)
        send_cmd = struct.pack('<18s', cmd)
        self._char_auth.write(send_cmd)
        self.waitForNotifications(self.timeout)

    # Parse helpers ###########################################################

    def _parse_raw_accel(self, bytes):
        for i in range(int((len(bytes)-2)/6)):
            g = struct.unpack('hhh', bytes[2 + i * 6:8 + i * 6])
            try:
                self.accel_queue.put(g)
            except Full:
                self.accel_queue.get_nowait()
                self.accel_queue.put(g)
            return g

    # Queue ###################################################################


    def _parse_queue(self):
        while True:
            try:
                res = self.queue.get(False)
                _type = res[0]
                if self.accel_raw_callback and _type == QUEUE_TYPES.RAW_ACCEL:
                    self.accel_raw_callback(self._parse_raw_accel(res[1]))
            except Empty as err:
                break

    # API ####################################################################

    def initialize(self):
        self.setDelegate(AuthenticationDelegate(self))
        self._send_key()

        while True:
            self.waitForNotifications(0.1)
            if self.state == AUTH_STATES.AUTH_OK:
                self._log.info('Initialized')
                self._auth_notif(False)
                return True
            elif self.state is None:
                continue

            self._log.error(self.state)
            return False

    def authenticate(self):
        self.setDelegate(AuthenticationDelegate(self))
        self._req_rdn()

        while True:
            self.waitForNotifications(0.1)
            if self.state == AUTH_STATES.AUTH_OK:
                self._log.info('Authenticated')
                return True
            elif self.state is None:
                continue

            self._log.error(self.state)
            return False


    def set_encoding(self, encoding="en_US"):
        char = self.svc_1.getCharacteristics(UUIDS.CHARACTERISTIC_CONFIGURATION)[0]
        packet = struct.pack('5s', encoding)
        packet = b'\x06\x17\x00' + packet
        return char.write(packet)

    def get_serial(self):
        svc = self.getServiceByUUID(UUIDS.SERVICE_DEVICE_INFO)
        char = svc.getCharacteristics(UUIDS.CHARACTERISTIC_SERIAL)[0]
        data = char.read()
        serial = struct.unpack('12s', data[-12:])[0] if len(data) == 12 else None
        return serial


    def send_alert(self, _type):
        svc = self.getServiceByUUID(UUIDS.SERVICE_ALERT)
        char = svc.getCharacteristics(UUIDS.CHARACTERISTIC_ALERT)[0]
        char.write(_type)

    def start_raw_data_realtime(self, accel_raw_callback=None):
        if accel_raw_callback:
            self.accel_raw_callback = accel_raw_callback

        char_sensor_desc = self._char_sensor_measure.getDescriptors(forUUID=UUIDS.NOTIFICATION_DESCRIPTOR)[0]
        self._log.info("Enabling accel raw data notification")
        self._char_sensor_ctrl.write(b'\x01\x01\x19')
        self._log.info("Start getting sensor data")
        self._char_sensor_ctrl.write(b'\x02')
        self._log.info("Data written to descrip.")
        char_sensor_desc.write(b'\x01\x00')
        t = time.time()
        while not self.is_realtime_stopped():
            self.waitForNotifications(0.5)
            self._parse_queue()
            # send ping request every 60 sec
            if (time.time() - t) > 60:
                self._char_sensor_ctrl.write(b'\x01\x01\x19')
                self._char_sensor_ctrl.write(b'\x02')
                t = time.time()

    def stop_realtime(self):
        self._stop_getting_real_time.set()
        char_sensor_desc = self._char_sensor_measure.getDescriptors(forUUID=UUIDS.NOTIFICATION_DESCRIPTOR)[0]
        char_sensor_desc.write(b'\x00\x00')   #stop getting notifications
        self._char_sensor_ctrl.write(b'\x03') #stopping
        self.accel_raw_callback = None

    def is_realtime_stopped(self):
        return self._stop_getting_real_time.is_set()

    def get_accel(self):
        try:
            # self._log.debug(print(list(self.accel_queue.queue)))
            return self.accel_queue.get()
        except Empty:
            # self._log.debug("Queue is Empty")
            return (0, 0, 0)

    def get_euler(self):
        try:
            gx, gy, gz = self.accel_queue.get()
            roll = math.atan2(-gx, gz)
            pitch = math.atan2(gy, math.sqrt(pow(gx, 2) + pow(gz, 2)))


            return (gx, gy, 0)
        except Empty:
            # self._log.debug("Queue is Empty")
            return (0, 0, 0)

    def dump_to_file(self, length=1000):
        with open('dump.txt', 'w') as fp:
            while length > 0:
                length -= 1
                fp.writelines("{}\n".format(self.accel_queue.get()))






