# range_tester.py
# Sideband Plugin for Mooring-SWAP Range Testing
# Place in Sideband/plugins/ directory

import time
import threading
import csv
import io
from datetime import datetime

# Sideband plugin imports
from sbapp.plugin import SidebandServicePlugin, SidebandTelemetryPlugin, SidebandCommandPlugin

# Reticulum imports
import RNS
import LXMF


class RangeTesterService(SidebandServicePlugin):
    """Background service that sends periodic pings and records results."""

    service_name = "range_tester_service"

    def __init__(self, sideband_core):
        super().__init__(sideband_core)
        self.is_running = False
        self.ping_interval = 10  # seconds
        self.base_hash = None
        self.worker_thread = None
        self.remote_rssi = None
        self.remote_snr = None
        self.reply_received = False
        self.results = []  # list of dicts with timestamp, lat, lon, local_rssi, local_snr, remote_rssi, remote_snr

        # Reticulum / LXMF setup
        self.identity = None
        self.lxmf_router = None
        self.server_dest = None

        # Telemetry reference
        self.telemetry_plugin = None

    def start(self):
        """Start the background service thread."""
        if self.is_running:
            return
        self.is_running = True
        self.worker_thread = threading.Thread(target=self._run, daemon=True)
        self.worker_thread.start()
        self.log("RangeTester service started.")
        super().start()

    def stop(self):
        """Stop the background service."""
        self.is_running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=2.0)
        self.log("RangeTester service stopped.")
        super().stop()

    def _init_reticulum(self):
        """Initialize Reticulum and LXMF."""
        if self.identity is None:
            self.identity = RNS.Identity()
        if self.lxmf_router is None:
            self.lxmf_router = LXMF.LXMRouter(
                identity=self.identity,
                storagepath=self.sideband_core.config_dir + "/lxmf_storage"
            )
            self.lxmf_router.register_delivery_callback(self._on_lxmf_message)

    def _create_server_dest(self, hash_str):
        """Create a destination object from the server hash."""
        hash_bytes = bytes.fromhex(hash_str)
        fake_id = RNS.Identity(create_keys=False)
        fake_id.hash = hash_bytes
        fake_id.hexhash = hash_str
        return RNS.Destination(
            fake_id,
            RNS.Destination.OUT,
            RNS.Destination.SINGLE,
            "mooring",
            "echo"
        )

    def _on_lxmf_message(self, message):
        """Handle incoming LXMF messages (PONG replies)."""
        try:
            content = message.content.decode('utf-8')
            if content.startswith("PONG:"):
                parts = content[5:].split(',')
                if len(parts) == 2:
                    self.remote_rssi = float(parts[0])
                    self.remote_snr = float(parts[1])
                    self.reply_received = True
        except Exception:
            pass

    def _get_current_location(self):
        """Get current GPS coordinates from telemetry plugin."""
        if self.telemetry_plugin and hasattr(self.telemetry_plugin, 'last_location'):
            loc = self.telemetry_plugin.last_location
            if loc and loc.get('latitude') and loc.get('longitude'):
                return loc['latitude'], loc['longitude']
        return None, None

    def _send_ping(self):
        """Send a single ping and record results."""
        if not self.base_hash or not self.lxmf_router:
            return

        if self.server_dest is None:
            self.server_dest = self._create_server_dest(self.base_hash)

        self.reply_received = False
        self.remote_rssi = None
        self.remote_snr = None

        # Get location
        lat, lon = self._get_current_location()

        # Send raw packet to get local stats
        link = RNS.Link(self.server_dest)
        local_rssi = None
        local_snr = None
        if link.status == RNS.Link.ACTIVE:
            ping_pkt = RNS.Packet(link, b'PING')
            receipt = ping_pkt.send()
            if receipt:
                receipt.wait(2.0)
                local_rssi = receipt.get_rssi()
                local_snr = receipt.get_snr()

        # Send LXMF PING
        msg = LXMF.LXMessage(
            self.server_dest,
            "PING",
            "Ping",
            desired_method=LXMF.LXMessage.DIRECT
        )
        self.lxmf_router.handle_outbound(msg)

        # Wait for reply
        waited = 0
        while not self.reply_received and waited < 12:
            time.sleep(0.2)
            waited += 0.2

        # Store result
        timestamp = datetime.now().isoformat(timespec='milliseconds')
        self.results.append({
            'timestamp': timestamp,
            'latitude': lat,
            'longitude': lon,
            'local_rssi': local_rssi,
            'local_snr': local_snr,
            'remote_rssi': self.remote_rssi,
            'remote_snr': self.remote_snr
        })

        # Trim old results if too many (keep last 2000)
        if len(self.results) > 2000:
            self.results = self.results[-2000:]

        self.log(f"Ping: local RSSI={local_rssi} remote RSSI={self.remote_rssi}")

    def _run(self):
        """Main service loop."""
        self._init_reticulum()
        while self.is_running:
            if self.base_hash:
                self._send_ping()
            time.sleep(self.ping_interval)

    def export_csv(self):
        """Export results as CSV string."""
        if not self.results:
            return "No data collected yet."

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Timestamp', 'Latitude', 'Longitude', 'Local_RSSI_dBm', 'Local_SNR_dB',
                         'Remote_RSSI_dBm', 'Remote_SNR_dB'])
        for r in self.results:
            writer.writerow([
                r['timestamp'],
                r['latitude'] if r['latitude'] is not None else '',
                r['longitude'] if r['longitude'] is not None else '',
                r['local_rssi'] if r['local_rssi'] is not None else '',
                r['local_snr'] if r['local_snr'] is not None else '',
                r['remote_rssi'] if r['remote_rssi'] is not None else '',
                r['remote_snr'] if r['remote_snr'] is not None else ''
            ])
        return output.getvalue()

    def log(self, message):
        """Log a message via Sideband's logger."""
        if hasattr(self.sideband_core, 'log'):
            self.sideband_core.log(f"[RangeTester] {message}")


class RangeTesterTelemetry(SidebandTelemetryPlugin):
    """Telemetry plugin to provide GPS location."""

    plugin_name = "range_tester_telemetry"
    last_location = {'latitude': None, 'longitude': None}

    def update_telemetry(self, telemeter):
        if telemeter is None:
            return

        # Ensure location sensor is enabled
        if "location" not in telemeter.sensors:
            telemeter.synthesize("location")

        loc_sensor = telemeter.sensors.get("location")
        if loc_sensor and loc_sensor.latitude is not None and loc_sensor.longitude is not None:
            self.last_location['latitude'] = loc_sensor.latitude
            self.last_location['longitude'] = loc_sensor.longitude


class RangeTesterCommand(SidebandCommandPlugin):
    """Command plugin to control the range tester."""

    command_name = "range_test"

    def __init__(self, sideband_core):
        super().__init__(sideband_core)
        self.service_plugin = None
        self.telemetry_plugin = None

    def _get_service_plugin(self):
        """Find or create the service plugin."""
        if self.service_plugin is None:
            # Check if already registered
            for plugin in self.sideband_core.plugins:
                if hasattr(plugin, 'service_name') and plugin.service_name == "range_tester_service":
                    self.service_plugin = plugin
                    break
            if self.service_plugin is None:
                self.service_plugin = RangeTesterService(self.sideband_core)
                self.sideband_core.register_plugin(self.service_plugin)
        return self.service_plugin

    def _get_telemetry_plugin(self):
        """Find or create the telemetry plugin."""
        if self.telemetry_plugin is None:
            for plugin in self.sideband_core.plugins:
                if hasattr(plugin, 'plugin_name') and plugin.plugin_name == "range_tester_telemetry":
                    self.telemetry_plugin = plugin
                    break
            if self.telemetry_plugin is None:
                self.telemetry_plugin = RangeTesterTelemetry(self.sideband_core)
                self.sideband_core.register_plugin(self.telemetry_plugin)
        return self.telemetry_plugin

    def handle_command(self, arguments, lxm):
        """Process user commands."""
        if not arguments:
            return "Usage: range_test <start|stop|export|status> [base_hash] [interval]"

        action = arguments[0].lower()
        service = self._get_service_plugin()
        telemetry = self._get_telemetry_plugin()
        service.telemetry_plugin = telemetry  # link for GPS access

        if action == "start":
            if len(arguments) < 2:
                return "Please provide base station hash: range_test start <hash> [interval]"
            service.base_hash = arguments[1]
            if len(arguments) > 2:
                try:
                    service.ping_interval = int(arguments[2])
                except ValueError:
                    return "Invalid interval. Use seconds (e.g., 10)."
            service.start()
            return f"Range test started. Pinging {service.base_hash} every {service.ping_interval}s."

        elif action == "stop":
            service.stop()
            return "Range test stopped."

        elif action == "status":
            if service.is_running:
                lat, lon = telemetry.last_location.get('latitude'), telemetry.last_location.get('longitude')
                return f"Running. Pings: {len(service.results)} collected. Last location: {lat}, {lon}"
            else:
                return "Not running."

        elif action == "export":
            csv_data = service.export_csv()
            # Send as a message (Sideband will display it)
            return f"CSV data:\n{csv_data}"

        else:
            return "Unknown action. Use start, stop, status, or export."


# Required plugin export
plugin_class = RangeTesterCommand
