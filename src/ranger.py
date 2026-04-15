#!/usr/bin/env python3
import RNS

def main():
    # Initialize Reticulum with debug logging
    reticulum = RNS.Reticulum(loglevel=RNS.LOG_INFO)
    identity = RNS.Identity()

    print(f"Reticulum running. Local identity hash: {identity.hash.hex()}")
    print("Press Ctrl+C to exit.")

    try:
        while True:
            # Add monitoring logic here later
            pass
    except KeyboardInterrupt:
        print("\nShutting down.")

if __name__ == "__main__":
    main()
