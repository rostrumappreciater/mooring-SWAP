#!/usr/bin/env python3
"""
Mooring Station: Fixed node that announces a service and responds to signal requests.
"""

import time
import threading
import RNS
import LXMF


class MooringStation:
    def __init__(self, announce_aspect="mooring-swap.service"):
        self.announce_aspect = announce_aspect
        self.identity = RNS.Identity()
        self.reticulum = RNS.Reticulum(loglevel=RNS.LOG_DEBUG)  # DEBUG for first test
        self.lxmf_router = LXMF.LXMRouter(identity=self.identity, storagepath=None)
        self.lxmf_router.register_delivery_callback(self._on_lxmf_message)
        
        self.active_links = {}  # Track links by destination hash
        self.link_lock = threading.Lock()

        # Announce our presence
        RNS.Transport.announce(self.identity.hash, app_data=self.announce_aspect.encode('utf-8'))
        
        print(f"Mooring Station running.")
        print(f"Identity hash: {RNS.hexrep(self.identity.hash, delimit=False)}")
        print(f"Announcing as '{self.announce_aspect}'...")

    def _on_lxmf_message(self, message):
        """Handle incoming LXMF messages."""
        try:
            content = message.content.decode('utf-8')
            source_hash = message.source.hash
            
            # Track the link used for this message
            if hasattr(message, 'packet') and message.packet:
                link = message.packet.link
                if link:
                    with self.link_lock:
                        self.active_links[source_hash] = link

            print(f"Received message from {RNS.hexrep(source_hash, delimit=False)}: {content}")

            if content == "REQUEST_STATS":
                self._send_stats_response(message.source)
        except Exception as e:
            print(f"Error processing LXMF message: {e}")

    def _send_stats_response(self, destination):
        """Send back this station's observed RSSI and SNR for the link."""
        source_hash = destination.hash
        link = None
        
        with self.link_lock:
            link = self.active_links.get(source_hash)
        
        if not link:
            print(f"No active link found for {RNS.hexrep(source_hash, delimit=False)}")
            rssi = -999
            snr = -999
        else:
            # Get the latest stats from the link
            rssi = link.rssi if link.rssi is not None else -999
            snr = link.snr if link.snr is not None else -999
            print(f"Link stats for {RNS.hexrep(source_hash, delimit=False)}: RSSI={rssi}, SNR={snr}")

        response_text = f"STATS:rssi={rssi:.1f},snr={snr:.1f}"
        lxmf_dest = self.lxmf_router.register_delivery_identity(
            destination, 
            display_name="Mooring"
        )
        reply = LXMF.LXMessage(
            lxmf_dest, 
            response_text, 
            "Signal report", 
            desired_method=LXMF.LXMessage.DIRECT
        )
        self.lxmf_router.handle_outbound(reply)
        print(f"Sent stats: {response_text}")

    def run(self):
        """Keep the station alive."""
        print("Listening for requests. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down Mooring Station.")


if __name__ == "__main__":
    station = MooringStation()
    station.run()
