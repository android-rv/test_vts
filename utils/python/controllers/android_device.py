#!/usr/bin/env python3.4
#
#   Copyright 2016 - The Android Open Source Project
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

from builtins import str
from builtins import open

import logging
import os
import time
import traceback
import threading
import socket
import Queue

from vts.runners.host import logger as vts_logger
from vts.runners.host import signals
from vts.runners.host import utils
from vts.utils.python.controllers import adb
from vts.utils.python.controllers import event_dispatcher
from vts.utils.python.controllers import fastboot
from vts.runners.host.tcp_client import vts_tcp_client
from vts.utils.python.mirror import hal_mirror
from vts.runners.host import errors
import subprocess

VTS_CONTROLLER_CONFIG_NAME = "AndroidDevice"
VTS_CONTROLLER_REFERENCE_NAME = "android_devices"

ANDROID_DEVICE_PICK_ALL_TOKEN = "*"
# Key name for adb logcat extra params in config file.
ANDROID_DEVICE_ADB_LOGCAT_PARAM_KEY = "adb_logcat_param"
ANDROID_DEVICE_EMPTY_CONFIG_MSG = "Configuration is empty, abort!"
ANDROID_DEVICE_NOT_LIST_CONFIG_MSG = "Configuration should be a list, abort!"

# Target-side directory where the VTS binaries are uploaded
DEFAULT_AGENT_BASE_DIR = "/data/local/tmp"
# Time for which the current is put on sleep when the client is unable to
# make a connection.
THREAD_SLEEP_TIME = 1
# Max number of attempts that the client can make to connect to the agent
MAX_AGENT_CONNECT_RETRIES = 10


class AndroidDeviceError(signals.ControllerError):
    pass


def create(configs):
    if not configs:
        raise AndroidDeviceError(ANDROID_DEVICE_EMPTY_CONFIG_MSG)
    elif configs == ANDROID_DEVICE_PICK_ALL_TOKEN:
        ads = get_all_instances()
    elif not isinstance(configs, list):
        raise AndroidDeviceError(ANDROID_DEVICE_NOT_LIST_CONFIG_MSG)
    elif isinstance(configs[0], str):
        # Configs is a list of serials.
        ads = get_instances(configs)
    else:
        # Configs is a list of dicts.
        ads = get_instances_with_configs(configs)
    connected_ads = list_adb_devices()
    for ad in ads:
        if ad.serial not in connected_ads:
            raise AndroidDeviceError(
                ("Android device %s is specified in config"
                 " but is not attached.") % ad.serial)
        ad.startAdbLogcat()
    return ads


def destroy(ads):
    for ad in ads:
        try:
            ad.closeAllSl4aSession()
        except:
            pass
        if ad.adb_logcat_process:
            ad.stopAdbLogcat()


def _parse_device_list(device_list_str, key):
    """Parses a byte string representing a list of devices. The string is
    generated by calling either adb or fastboot.

    Args:
        device_list_str: Output of adb or fastboot.
        key: The token that signifies a device in device_list_str.

    Returns:
        A list of android device serial numbers.
    """
    clean_lines = str(device_list_str, 'utf-8').strip().split('\n')
    results = []
    for line in clean_lines:
        tokens = line.strip().split('\t')
        if len(tokens) == 2 and tokens[1] == key:
            results.append(tokens[0])
    return results


def list_adb_devices():
    """List all target devices connected to the host and detected by adb.

    Returns:
        A list of android device serials. Empty if there's none.
    """
    out = adb.AdbProxy().devices()
    return _parse_device_list(out, "device")


def list_fastboot_devices():
    """List all android devices connected to the computer that are in in
    fastboot mode. These are detected by fastboot.

    Returns:
        A list of android device serials. Empty if there's none.
    """
    out = fastboot.FastbootProxy().devices()
    return _parse_device_list(out, "fastboot")


def get_instances(serials):
    """Create AndroidDevice instances from a list of serials.

    Args:
        serials: A list of android device serials.

    Returns:
        A list of AndroidDevice objects.
    """
    results = []
    for s in serials:
        results.append(AndroidDevice(s))
    return results


def get_instances_with_configs(configs):
    """Create AndroidDevice instances from a list of json configs.

    Each config should have the required key-value pair "serial".

    Args:
        configs: A list of dicts each representing the configuration of one
            android device.

    Returns:
        A list of AndroidDevice objects.
    """
    results = []
    for c in configs:
        try:
            serial = c.pop("serial")
        except KeyError:
            raise AndroidDeviceError(('Required value "serial" is missing in '
                                      'AndroidDevice config %s.') % c)
        ad = AndroidDevice(serial)
        ad.loadConfig(c)
        results.append(ad)
    return results


def get_all_instances(include_fastboot=False):
    """Create AndroidDevice instances for all attached android devices.

    Args:
        include_fastboot: Whether to include devices in bootloader mode or not.

    Returns:
        A list of AndroidDevice objects each representing an android device
        attached to the computer.
    """
    if include_fastboot:
        serial_list = list_adb_devices() + list_fastboot_devices()
        return get_instances(serial_list)
    return get_instances(list_adb_devices())


def filter_devices(ads, func):
    """Finds the AndroidDevice instances from a list that match certain
    conditions.

    Args:
        ads: A list of AndroidDevice instances.
        func: A function that takes an AndroidDevice object and returns True
            if the device satisfies the filter condition.

    Returns:
        A list of AndroidDevice instances that satisfy the filter condition.
    """
    results = []
    for ad in ads:
        if func(ad):
            results.append(ad)
    return results


def get_device(ads, **kwargs):
    """Finds a unique AndroidDevice instance from a list that has specific
    attributes of certain values.

    Example:
        get_device(android_devices, label="foo", phone_number="1234567890")
        get_device(android_devices, model="angler")

    Args:
        ads: A list of AndroidDevice instances.
        kwargs: keyword arguments used to filter AndroidDevice instances.

    Returns:
        The target AndroidDevice instance.

    Raises:
        AndroidDeviceError is raised if none or more than one device is
        matched.
    """

    def _get_device_filter(ad):
        for k, v in kwargs.items():
            if not hasattr(ad, k):
                return False
            elif getattr(ad, k) != v:
                return False
        return True

    filtered = filter_devices(ads, _get_device_filter)
    if not filtered:
        raise AndroidDeviceError(("Could not find a target device that matches"
                                  " condition: %s.") % kwargs)
    elif len(filtered) == 1:
        return filtered[0]
    else:
        serials = [ad.serial for ad in filtered]
        raise AndroidDeviceError("More than one device matched: %s" % serials)


def takeBugReports(ads, test_name, begin_time):
    """Takes bug reports on a list of android devices.

    If you want to take a bug report, call this function with a list of
    android_device objects in on_fail. But reports will be taken on all the
    devices in the list concurrently. Bug report takes a relative long
    time to take, so use this cautiously.

    Args:
        ads: A list of AndroidDevice instances.
        test_name: Name of the test case that triggered this bug report.
        begin_time: Logline format timestamp taken when the test started.
    """
    begin_time = vts_logger.normalizeLogLineTimestamp(begin_time)

    def take_br(test_name, begin_time, ad):
        ad.takeBugReport(test_name, begin_time)

    args = [(test_name, begin_time, ad) for ad in ads]
    utils.concurrent_exec(take_br, args)


class AndroidDevice(object):
    """Class representing an android device.

    Each object of this class represents one Android device in ACTS, including
    handles to adb, fastboot, and sl4a clients. In addition to direct adb
    commands, this object also uses adb port forwarding to talk to the Android
    device.

    Attributes:
        serial: A string that's the serial number of the Androi device.
        device_command_port: int, the port number used on the Android device
                for adb port forwarding (for command-response sessions).
        device_callback_port: int, the port number used on the Android device
                for adb port reverse forwarding (for callback sessions).
        log_path: A string that is the path where all logs collected on this
                  android device should be stored.
        adb_logcat_process: A process that collects the adb logcat.
        adb_logcat_file_path: A string that's the full path to the adb logcat
                              file collected, if any.
        adb: An AdbProxy object used for interacting with the device via adb.
        fastboot: A FastbootProxy object used for interacting with the device
                  via fastboot.
        host_command_port: the host-side port for runner to agent sessions
                           (to send commands and receive responses).
        host_callback_port: the host-side port for agent to runner sessions
                            (to get callbacks from agent).
        background_thread: a thread that runs in background to upload the
            agent on the device.
        queue: an instance of queue.Queue that keeps main thread on wait unless
            the background_thread indicates it to move.
        base_dir: target-side directory where the VTS binaries are uploaded.
    """
    background_thread = None
    background_thread_proceed = False
    base_dir = None
    queue = Queue.Queue()

    def __init__(self, serial="", device_port=5001, device_callback_port=5010):
        self.serial = serial
        self.device_command_port = device_port
        self.device_callback_port = device_callback_port
        self.log = logging.getLogger()
        base_log_path = getattr(self.log, "log_path", "/tmp/logs/")
        self.log_path = os.path.join(base_log_path, "AndroidDevice%s" % serial)
        self.adb_logcat_process = None
        self.adb_logcat_file_path = None
        self.adb = adb.AdbProxy(serial)
        self.fastboot = fastboot.FastbootProxy(serial)
        if not self.isBootloaderMode:
            self.rootAdb()
        self.host_command_port = adb.get_available_host_port()
        self.host_callback_port = adb.get_available_host_port()
        self.adb.tcp_forward(self.host_command_port, self.device_command_port)
        self.adb.reverse_tcp_forward(
            self.device_callback_port, self.host_callback_port)
        self.hal = hal_mirror.HalMirror(
            self.host_command_port, self.host_callback_port)

    def __del__(self):
        if self.host_command_port:
            self.adb.forward("--remove tcp:%s" % self.host_command_port)
        if self.adb_logcat_process:
            self.stopAdbLogcat()

    @property
    def isBootloaderMode(self):
        """True if the device is in bootloader mode.
        """
        return self.serial in list_fastboot_devices()

    @property
    def isAdbRoot(self):
        """True if adb is running as root for this device.
        """
        return "root" in self.adb.shell("id -u").decode("utf-8")

    @property
    def model(self):
        """The Android code name for the device.
        """
        # If device is in bootloader mode, get mode name from fastboot.
        if self.isBootloaderMode:
            out = self.fastboot.getvar("product").strip()
            # "out" is never empty because of the "total time" message fastboot
            # writes to stderr.
            lines = out.decode("utf-8").split('\n', 1)
            if lines:
                tokens = lines[0].split(' ')
                if len(tokens) > 1:
                    return tokens[1].lower()
            return None
        out = self.adb.shell('getprop | grep ro.build.product')
        model = out.decode("utf-8").strip().split('[')[-1][:-1].lower()
        if model == "sprout":
            return model
        else:
            out = self.adb.shell('getprop | grep ro.product.name')
            model = out.decode("utf-8").strip().split('[')[-1][:-1].lower()
            return model

    @property
    def isAdbLogcatOn(self):
        """Whether there is an ongoing adb logcat collection.
        """
        if self.adb_logcat_process:
            return True
        return False

    def loadConfig(self, config):
        """Add attributes to the AndroidDevice object based on json config.

        Args:
            config: A dictionary representing the configs.

        Raises:
            AndroidDeviceError is raised if the config is trying to overwrite
            an existing attribute.
        """
        for k, v in config.items():
            if hasattr(self, k):
                raise AndroidDeviceError(
                    "Attempting to set existing attribute %s on %s" %
                    (k, self.serial))
            setattr(self, k, v)

    def rootAdb(self):
        """Change adb to root mode for this device.
        """
        if not self.isAdbRoot:
            self.adb.root()
            self.adb.wait_for_device()
            self.adb.remount()
            self.adb.wait_for_device()

    def startAdbLogcat(self):
        """Starts a standing adb logcat collection in separate subprocesses and
        save the logcat in a file.
        """
        if self.isAdbLogcatOn:
            raise AndroidDeviceError(("Android device %s already has an adb "
                                      "logcat thread going on. Cannot start "
                                      "another one.") % self.serial)
        # Disable adb log spam filter.
        self.adb.shell("logpersist.start")
        f_name = "adblog,%s,%s.txt" % (self.model, self.serial)
        utils.create_dir(self.log_path)
        logcat_file_path = os.path.join(self.log_path, f_name)
        try:
            extra_params = self.adb_logcat_param
        except AttributeError:
            extra_params = "-b all"
        cmd = "adb -s %s logcat -v threadtime %s >> %s" % (
            self.serial, extra_params, logcat_file_path)
        self.adb_logcat_process = utils.start_standing_subprocess(cmd)
        self.adb_logcat_file_path = logcat_file_path

    def stopAdbLogcat(self):
        """Stops the adb logcat collection subprocess.
        """
        if not self.isAdbLogcatOn:
            raise AndroidDeviceError(
                "Android device %s does not have an ongoing adb logcat collection."
                % self.serial)
        utils.stop_standing_subprocess(self.adb_logcat_process)
        self.adb_logcat_process = None

    def takeBugReport(self, test_name, begin_time):
        """Takes a bug report on the device and stores it in a file.

        Args:
            test_name: Name of the test case that triggered this bug report.
            begin_time: Logline format timestamp taken when the test started.
        """
        br_path = os.path.join(self.log_path, "BugReports")
        utils.create_dir(br_path)
        base_name = ",%s,%s.txt" % (begin_time, self.serial)
        test_name_len = utils.MAX_FILENAME_LEN - len(base_name)
        out_name = test_name[:test_name_len] + base_name
        full_out_path = os.path.join(br_path, out_name.replace(' ', '\ '))
        self.log.info("Taking bugreport for %s on %s", test_name, self.serial)
        self.adb.bugreport(" > %s" % full_out_path)
        self.log.info("Bugreport for %s taken at %s", test_name, full_out_path)

    @utils.timeout(15 * 60)
    def waitForBootCompletion(self):
        """Waits for Android framework to broadcast ACTION_BOOT_COMPLETED.

        This function times out after 15 minutes.
        """
        self.adb.wait_for_device()
        while True:
            try:
                out = self.adb.shell("getprop sys.boot_completed")
                completed = out.decode('utf-8').strip()
                if completed == '1':
                    return
            except adb.AdbError:
                # adb shell calls may fail during certain period of booting
                # process, which is normal. Ignoring these errors.
                pass
            time.sleep(5)

    def reboot(self):
        """Reboots the device and wait for device to complete booting.

        This is probably going to print some error messages in console. Only
        use if there's no other option.

        Raises:
            AndroidDeviceError is raised if waiting for completion timed
            out.
        """
        if self.isBootloaderMode:
            self.fastboot.reboot()
            return
        has_adb_log = self.isAdbLogcatOn
        if has_adb_log:
            self.stopAdbLogcat()
        self.adb.reboot()
        self.waitForBootCompletion()
        self.rootAdb()
        if has_adb_log:
            self.startAdbLogcat()

    def startAgent(self):
        """ To start agent.

        This function starts the target side native agent and is persisted
        throughout the test run. This process is handled by the VTS runner lib.
        """
        # to ensure that only one instance of this agent runs
        if(self.background_thread is not None):
            logging.error(
                "Another instance of background_thread is already "
                "running.")
            return

        background_thread = threading.Thread(target=self.runAgent)
        # Exit the server thread when the main thread terminates
        background_thread.daemon = True
        background_thread.start()

        # wait for the flag from child thread
        self.queue.get(block=True, timeout=None)

        client = vts_tcp_client.VtsTcpClient()

        # Ensure that the connection succeeds before it moves forward.
        for _ in range(MAX_AGENT_CONNECT_RETRIES):
            try:
                time.sleep(THREAD_SLEEP_TIME)  # put current thread on sleep
                response = client.Connect(
                    command_port=self.host_command_port,
                    callback_port=self.host_callback_port)

                if response:
                    return
            except socket.error as e:
                pass

        # Throw error if client is unable to make a connection
        raise errors.VtsTcpClientCreationError(
              "Couldn't connect to %s:%s" % (
                                    vts_tcp_client.TARGET_IP,
                                    self.host_command_port))

    def runAgent(self):
        """This functions runs the child thread that runs the agent."""

        # kill the existing instance of agent in DUT
        commands = ["killall vts_hal_agent > /dev/null 2&>1",
                    "killall fuzzer32 > /dev/null 2&>1",
                    "killall fuzzer64 > /dev/null 2&>1"]

        for cmd in commands:
            try:
                self.adb.shell(cmd)
            except adb.AdbError as e:
                logging.info('Exception occurred in command: %s', cmd)

        cmd = '{}{}{} {}{} {}{} {}{} {}{}'.format(
            'LD_LIBRARY_PATH=',
            DEFAULT_AGENT_BASE_DIR, "/64",
            DEFAULT_AGENT_BASE_DIR, "/64/vts_hal_agent",
            DEFAULT_AGENT_BASE_DIR, "/32/fuzzer32",
            DEFAULT_AGENT_BASE_DIR, "/64/fuzzer64",
            DEFAULT_AGENT_BASE_DIR, "/spec")

        self.queue.put('flag')
        self.adb.shell(cmd)

        # This should never happen.
        logging.exception("Agent Terminated!")

    def stopAgent(self):
        """Stop the agent running on target.

        This function stops the target side native agent which is persisted
        throughout the test run. Obtain the process ID for the agent running
        on DUT and then kill the process. This assumes each target device runs
        only one VTS agent at a time.

        """
        # TODO: figure out if this function is called from unregisterControllers
        cmd = 'adb shell pgrep vts_hal_agent'
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
        (out, err) = proc.communicate()
        out = out.strip()
        processList = out.split('\n')

        # Return if multiple agents are running on the device
        if len(processList) > 1:
            logging.error("Multiple instances of vts_hal_agent running on "
                "device.")
            return

        # Kill the processes corresponding to the agent
        for pid in processList:
            cmd = '{} {}'.format('adb shell kill -9', pid)
            subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
