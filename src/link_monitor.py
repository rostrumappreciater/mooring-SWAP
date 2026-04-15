import time
import RNS

class LinkMonitor:
    def __init__(self, target_aspect="solar-ref-node.service"):
        self.target = target_aspect
        self.link = None
        self.last_rssi = None
        self.last_snr = None

    def discover_and_connect(self, timeout=30):
        """Listen for announce and establish a link."""
        print(f"Listening for '{self.target}' announcements...")
        # Set up a resource handler for announces
        RNS.Transport.register_announce_handler(self._on_announce)
        start_time = time.time()
        while self.link is None and (time.time() - start_time) < timeout:
            time.sleep(0.5)
        RNS.Transport.deregister_announce_handler(self._on_announce)
        return self.link is not None

    def _on_announce(self, announced_identity, announced_hash, public_data):
        if public_data and self.target in public_data.decode('utf-8'):
            print(f"Found target node: {announced_hash.hex()}")
            # Establish a link
            destination = RNS.Destination(
                announced_hash,
                RNS.Destination.OUT,
                RNS.Destination.SINGLE,
                "lxmf"
            )
            self.link = RNS.Link(destination)
            print("Link established.")
