#!/usr/bin/env python3
"""
Mooring Station: Fixed node that announces a service and responds to signal requests.
"""

import time
import RNS
import LXMF


class MooringStation:
    def __init__(self, announce_aspect="mooring-swap.service"):
        self.announce_aspect = announce_aspect
        self.identity = RNS.Identity()
        self.link = None
        self.lxmf_router = None

        # Initialize Reticulum
        self.reticulum = RNS.Reticulum(loglevel=RNS.LOG_INFO)
        print(f"Mooring Station running.")
        print(f"Identity hash: {self.identity.hash.hex()}")

        # Start announcing
        RNS.Transport.announce(self.identity.hash, app_data=self.announce_aspect.encode('utf-8'))
        print(f"Announcing as '{self.announce_aspect}'...")

        # Set up LXMF router to receive requests
        self.lxmf_router = LXMF.LXMRouter(identity=self.identity, storagepath=None)
        self.lxmf_router.register_delivery_callback(self._on_lxmf_message)

    def _on_lxmf_message(self, message):
        """Handle incoming LXMF messages."""
        try:
            content = message.content.decode('utf-8')
            source_hash = message.source.hash.hex()

            print(f"Received message from {source_hash}: {content}")

            if content == "REQUEST_STATS":
                self._send_stats_response(message.source)
        except Exception as e:
            print(f"Error processing LXMF message: {e}")

    def _send_stats_response(self, destination):
        """Send back this station's observed RSSI and SNR for the link."""
        if not self.link:
            # We need an active link to get stats. The request itself may have come
            # over a link. Reticulum's LXMF delivers messages via links when available.
            # For simplicity, we'll use the last active link from the LXMF delivery.
            # In a more robust version, we'd track the link from the incoming packet.
            print("No active link reference. Stats unavailable.")
            return

        # Retrieve local RSSI/SNR from the link
        rssi = self.link.rssi if self.link.rssi else -999
        snr = self.link.snr if self.link.snr else -999

        response_text = f"STATS:rssi={rssi:.1f},snr={snr:.1f}"
        lxmf_dest = self.lxmf_router.register_delivery_identity(destination, display_name="Mooring")
        reply = LXMF.LXMessage(lxmf_dest, response_text, "Signal report", desired_method=LXMF.LXMessage.DIRECT)
        self.lxmf_router.handle_outbound(reply)

        print(f"Sent stats: RSSI={rssi:.1f} dBm, SNR={snr:.1f} dB")

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
