"""
LinkMonitor: Discovers the mooring station and exchanges signal reports.
"""

import time
import threading
import RNS
import LXMF


class LinkMonitor:
    def __init__(self, target_aspect="mooring-swap.service"):
        self.target = target_aspect
        self.link = None
        self.destination = None
        self.lxmf_router = None
        self.last_remote_stats = {"rssi": None, "snr": None}
        self.stats_lock = threading.Lock()
        self._shutdown = False

    def discover_and_connect(self, timeout=30):
        """Listen for announce and establish a link and LXMF router."""
        print(f"Listening for '{self.target}' announcements...")
        RNS.Transport.register_announce_handler(self._on_announce)

        start_time = time.time()
        while self.link is None and (time.time() - start_time) < timeout:
            time.sleep(0.5)

        RNS.Transport.deregister_announce_handler(self._on_announce)

        if self.link:
            self.lxmf_router = LXMF.LXMRouter(identity=RNS.Identity(), storagepath=None)
            self.lxmf_router.register_delivery_callback(self._on_lxmf_message)
            return True
        return False

    def _on_announce(self, announced_identity, announced_hash, public_data):
        """Handle incoming announces; connect if target aspect matches."""
        if public_data and self.target in public_data.decode('utf-8', errors='ignore'):
            print(f"Found mooring station: {RNS.hexrep(announced_hash, delimit=False)}")
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
                rssi_val = None
                snr_val = None
                for part in parts:
                    if part.startswith("rssi="):
                        rssi_val = float(part[5:])
                    elif part.startswith("snr="):
                        snr_val = float(part[4:])
                
                if rssi_val is not None and snr_val is not None:
                    with self.stats_lock:
                        self.last_remote_stats["rssi"] = rssi_val
                        self.last_remote_stats["snr"] = snr_val
                    print(f"\n[DEBUG] Received remote stats: RSSI={rssi_val:.1f}, SNR={snr_val:.1f}")
        except Exception as e:
            print(f"\nError parsing LXMF message: {e}")

    def get_stats(self):
        """Send a ping, wait for response, and return local/remote RSSI/SNR."""
        if not self.link or self.link.status != RNS.Link.ACTIVE:
            return None, None, None, None

        # Send a ping packet to trigger link activity and capture local stats
        ping_data = b'MOORING_SWAP_PING'
        ping_packet = RNS.Packet(self.link, ping_data)
        packet_receipt = ping_packet.send()
        
        # Wait for packet to be sent to get local RSSI/SNR
        if packet_receipt:
            # Wait for delivery receipt (with timeout)
            packet_receipt.wait(2.0)
            
            # Extract local stats from the packet receipt
            local_rssi = packet_receipt.get_rssi()
            local_snr = packet_receipt.get_snr()
        else:
            local_rssi = None
            local_snr = None

        # Request remote stats via LXMF
        if self.lxmf_router and self.destination:
            lxmf_dest = self.lxmf_router.register_delivery_identity(
                self.destination, 
                display_name="Mooring"
            )
            request_msg = LXMF.LXMessage(
                lxmf_dest, 
                "REQUEST_STATS", 
                "Request signal report", 
                desired_method=LXMF.LXMessage.DIRECT
            )
            self.lxmf_router.handle_outbound(request_msg)

        # Wait for response (we'll collect via async callback)
        time.sleep(0.8)

        with self.stats_lock:
            remote_rssi = self.last_remote_stats["rssi"]
            remote_snr = self.last_remote_stats["snr"]

        return local_rssi, local_snr, remote_rssi, remote_snr

    def shutdown(self):
        self._shutdown = True
        if self.link:
            self.link.teardown()
