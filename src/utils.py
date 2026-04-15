"""
Utilities for logging session data.
"""

import csv
import time
from datetime import datetime


class SessionLogger:
    def __init__(self, filename=None):
        if filename is None:
            filename = f"mooring_swap_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        self.file = open(filename, 'w', newline='')
        self.writer = csv.writer(self.file)
        self.writer.writerow(['timestamp', 'local_rssi', 'local_snr', 'remote_rssi', 'remote_snr'])
        print(f"Logging session to: {filename}")

    def log(self, local_rssi, local_snr, remote_rssi, remote_snr, lat=None, lon=None):
        self.writer.writerow([
            time.time(),
            local_rssi,
            local_snr,
            remote_rssi,
            remote_snr,
            lat or '',
            lon or ''
        ])
        self.file.flush()

    def close(self):
        self.file.close()
