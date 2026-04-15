import csv
import time
from datetime import datetime

class SessionLogger:
    def __init__(self, filename=None):
        if filename is None:
            filename = f"range_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        self.file = open(filename, 'w', newline='')
        self.writer = csv.writer(self.file)
        self.writer.writerow(['timestamp', 'rssi', 'snr', 'lat', 'lon'])

    def log(self, rssi, snr, lat=None, lon=None):
        self.writer.writerow([time.time(), rssi, snr, lat or '', lon or ''])
        self.file.flush()  # Ensure data is written even if program crashes

    def close(self):
        self.file.close()
