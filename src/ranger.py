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
    # Initialize Reticulum with debug logging for first test
    reticulum = RNS.Reticulum(loglevel=RNS.LOG_DEBUG)
    identity = RNS.Identity()

    print(f"Mooring-SWAP running.")
    print(f"Local identity hash: {RNS.hexrep(identity.hash, delimit=False)}")
    print("Searching for mooring station...")

    monitor = LinkMonitor(target_aspect="mooring-swap.service")
    logger = SessionLogger()

    if not monitor.discover_and_connect(timeout=60):  # Longer timeout for LoRa
        print("No mooring station found within timeout. Exiting.")
        return

    print("Connected to mooring. Beginning reciprocal signal assessment.")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            rssi_local, snr_local, rssi_remote, snr_remote = monitor.get_stats()

            # Display stats even if remote is missing (first few cycles)
            local_str = f"RSSI: {rssi_local: >6.1f} dBm  SNR: {snr_local: >6.1f} dB" if rssi_local is not None else "RSSI:    N/A      SNR:    N/A"
            remote_str = f"RSSI: {rssi_remote: >6.1f} dBm  SNR: {snr_remote: >6.1f} dB" if rssi_remote is not None else "RSSI:    N/A      SNR:    N/A"
            
            sys.stdout.write(f"\rLocal  -> {local_str}  |  Mooring -> {remote_str}   ")
            sys.stdout.flush()

            # Log to CSV (even partial data is useful)
            logger.log(rssi_local, snr_local, rssi_remote, snr_remote)

            time.sleep(3)  # Longer sleep for LoRa to avoid flooding

    except KeyboardInterrupt:
        print("\n\nShutting down.")
        logger.close()
        monitor.shutdown()


if __name__ == "__main__":
    main()
