"""
LinkMonitor: Discovers the mooring station and exchanges signal reports.
"""

import time
import RNS
import LXMF


class LinkMonitor:
    def __init__(self, target_aspect="mooring-swap.service"):
        self.target = target_aspect
        self.link = None
        self.destination = None
        self.lxmf_router = None
        self.local_rssi = None
        self.local_snr = None
        self.remote_rssi = None
        self.remote_snr = None

    def discover_and_connect(self, timeout=30):
        """Listen for announce and establish a link and LXMF router."""
        print(f"Listening for '{self.target}' announcements...")
        RNS.Transport.register_announce_handler(self._on_announce)

        start_time = time.time()
        while self.link is None and (time.time() - start_time) < timeout:
            time.sleep(0.5)

        RNS.Transport.deregister_announce_handler(self._on_announce)

        if self.link:
            # Initialize LXMF router for message exchange
            self.lxmf_router = LXMF.LXMRouter(identity=RNS.Identity(), storagepath=None)
            self.lxmf_router.register_delivery_callback(self._on_lxmf_message)
            return True
        return False

    def _on_announce(self, announced_identity, announced_hash, public_data):
        """Handle incoming announces; connect if target aspect matches."""
        if public_data and self.target in public_data.decode('utf-8', errors='ignore'):
            print(f"Found mooring station: {announced_hash.hex()}")
            self.destination = RNS.Destination(
                announced_hash,
                RNS.Destination.OUT,
                RNS.Destination.SINGLE,
                "lxmf"
            )
            self.link = RNS.Link(self.destination)
            print("Link established.")

    def _on_lxmf_message(self, message):
        """Callback for incoming LXMF messages containing remote stats."""
        try:
            content = message.content.decode('utf-8')
            if content.startswith("STATS:"):
                # Parse remote RSSI and SNR from response
                # Format: "STATS:rssi=-85.2,snr=12.5"
                parts = content[6:].split(',')
                for part in parts:
                    if part.startswith("rssi="):
                        self.remote_rssi = float(part[5:])
                    elif part.startswith("snr="):
                        self.remote_snr = float(part[4:])
        except Exception as e:
            print(f"\nError parsing LXMF message: {e}")

    def get_stats(self):
        """Send a ping, wait for response, and return local/remote RSSI/SNR."""
        if not self.link or self.link.status != RNS.Link.ACTIVE:
            return None, None, None, None

        # Send a ping packet to trigger link activity and capture local stats
        ping_packet = RNS.Packet(self.link, b'ping')
        ping_packet.send()
        time.sleep(0.3)  # Allow time for transmission

        # Capture local stats from the link
        self.local_rssi = self.link.rssi
        self.local_snr = self.link.snr

        # Request remote stats via LXMF
        lxmf_dest = self.lxmf_router.register_delivery_identity(self.destination, display_name="Mooring")
        request_msg = LXMF.LXMessage(lxmf_dest, "REQUEST_STATS", "Request signal report", desired_method=LXMF.LXMessage.DIRECT)
        self.lxmf_router.handle_outbound(request_msg)

        # Wait for response (simplified; production code would use async properly)
        time.sleep(0.5)

        return self.local_rssi, self.local_snr, self.remote_rssi, self.remote_snr
