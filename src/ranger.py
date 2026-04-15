#!/usr/bin/env python3
"""
Mooring-SWAP: Reciprocal signal assessment between a mobile node and a fixed mooring station.
"""

import sys
import time
import RNS

from link_monitor import LinkMonitor
from utils import SessionLogger


def main():
    # Initialize Reticulum with informational logging
    reticulum = RNS.Reticulum(loglevel=RNS.LOG_INFO)
    identity = RNS.Identity()

    print(f"Mooring-SWAP running.")
    print(f"Local identity hash: {identity.hash.hex()}")
    print("Searching for mooring station...")

    monitor = LinkMonitor(target_aspect="mooring-swap.service")
    logger = SessionLogger()

    if not monitor.discover_and_connect(timeout=30):
        print("No mooring station found within timeout. Exiting.")
        return

    print("Connected to mooring. Beginning reciprocal signal assessment.")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            rssi_local, snr_local, rssi_remote, snr_remote = monitor.get_stats()

            if rssi_local is not None and rssi_remote is not None:
                # Live updating display
                sys.stdout.write(
                    f"\rLocal  -> RSSI: {rssi_local: >6} dBm  SNR: {snr_local: >6} dB  |  "
                    f"Mooring -> RSSI: {rssi_remote: >6} dBm  SNR: {snr_remote: >6} dB   "
                )
                sys.stdout.flush()

                # Log to CSV
                logger.log(rssi_local, snr_local, rssi_remote, snr_remote)
            else:
                sys.stdout.write("\rWaiting for data...                              ")
                sys.stdout.flush()

            time.sleep(2)

    except KeyboardInterrupt:
        print("\n\nShutting down.")
        logger.close()


if __name__ == "__main__":
    main()
