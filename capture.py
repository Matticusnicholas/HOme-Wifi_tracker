#!/usr/bin/env python3
"""
Network capture module for HomeWatch.
Captures DNS queries and HTTP traffic to identify visited websites.
"""

import threading
import re
import sys
import platform
from datetime import datetime
from typing import Optional

# Track capture status for UI feedback
capture_status = {
    'status': 'stopped',
    'message': '',
    'packets_captured': 0
}


class NetworkCapture:
    """
    Network packet capture handler.
    Captures DNS queries to identify websites being visited.
    """

    def __init__(self, database):
        self.database = database
        self.is_running = False
        self._capture_thread = None
        self._stop_event = threading.Event()
        self._interface = None
        self._error_message = None
        self._packet_count = 0

    def start(self, interface: str = 'auto'):
        """Start network capture on the specified interface."""
        if self.is_running:
            return False, "Already running"

        self._interface = interface
        self._stop_event.clear()
        self._error_message = None
        self._packet_count = 0

        # Test if we can capture before starting thread
        can_capture, msg = self._test_capture_ability()
        if not can_capture:
            return False, msg

        self.is_running = True
        capture_status['status'] = 'running'
        capture_status['message'] = 'Capturing network traffic...'

        self._capture_thread = threading.Thread(
            target=self._capture_loop,
            daemon=True
        )
        self._capture_thread.start()
        return True, "Monitoring started"

    def stop(self):
        """Stop network capture."""
        if not self.is_running:
            return False

        self._stop_event.set()
        self.is_running = False
        capture_status['status'] = 'stopped'

        if self._capture_thread:
            self._capture_thread.join(timeout=5)
        return True

    def get_status(self):
        """Get current capture status."""
        return {
            'running': self.is_running,
            'packets': self._packet_count,
            'error': self._error_message
        }

    def _test_capture_ability(self):
        """Test if we can capture packets."""
        try:
            from scapy.all import conf, get_if_list

            # Check if we have interfaces
            interfaces = get_if_list()
            if not interfaces:
                return False, "No network interfaces found"

            # On Windows, check for Npcap
            if platform.system() == 'Windows':
                try:
                    # Try to access the Windows pcap
                    from scapy.arch.windows import get_windows_if_list
                    win_ifaces = get_windows_if_list()
                    if not win_ifaces:
                        return False, "Npcap not installed! Please run setup_and_run.bat to install it."
                except Exception as e:
                    return False, f"Npcap not working: {e}. Please install Npcap from https://npcap.com"

            return True, "Ready to capture"

        except ImportError:
            return False, "Scapy not installed. Run: pip install scapy"
        except Exception as e:
            return False, f"Capture test failed: {e}"

    def _capture_loop(self):
        """Main capture loop using scapy."""
        try:
            from scapy.all import sniff, DNS, DNSQR, IP, TCP, Raw, conf

            # Suppress scapy warnings
            conf.verb = 0

            def packet_handler(packet):
                """Process each captured packet."""
                if self._stop_event.is_set():
                    return

                try:
                    # DNS Query capture (main method - catches all website lookups)
                    if packet.haslayer(DNS) and packet.haslayer(DNSQR):
                        dns_query = packet[DNSQR].qname.decode('utf-8', errors='ignore')
                        if dns_query.endswith('.'):
                            dns_query = dns_query[:-1]

                        if self._is_valid_domain(dns_query):
                            source_ip = packet[IP].src if packet.haslayer(IP) else 'unknown'
                            self._record_visit(dns_query, source_ip, 'DNS')
                            self._packet_count += 1
                            capture_status['packets_captured'] = self._packet_count

                    # HTTP Host header capture (for unencrypted traffic)
                    elif packet.haslayer(TCP) and packet.haslayer(Raw):
                        if packet[TCP].dport == 80:
                            try:
                                payload = packet[Raw].load.decode('utf-8', errors='ignore')
                                host_match = re.search(r'Host:\s*([^\r\n]+)', payload, re.IGNORECASE)
                                if host_match:
                                    host = host_match.group(1).strip()
                                    if self._is_valid_domain(host):
                                        source_ip = packet[IP].src if packet.haslayer(IP) else 'unknown'
                                        self._record_visit(host, source_ip, 'HTTP')
                                        self._packet_count += 1
                            except:
                                pass
                except Exception as e:
                    pass  # Don't crash on malformed packets

            # Determine interface
            iface = None if self._interface == 'auto' else self._interface

            print(f"[CAPTURE] Starting on interface: {iface or 'all interfaces'}")
            print(f"[CAPTURE] Listening for DNS queries (port 53) and HTTP traffic (port 80)")
            print(f"[CAPTURE] Waiting for network activity...")

            # Start sniffing - port 53 is DNS
            sniff(
                filter="port 53 or port 80",
                prn=packet_handler,
                store=False,
                stop_filter=lambda x: self._stop_event.is_set(),
                iface=iface
            )

        except PermissionError:
            self._error_message = "Permission denied! Run as Administrator."
            capture_status['status'] = 'error'
            capture_status['message'] = self._error_message
            print(f"[ERROR] {self._error_message}")
            self.is_running = False

        except Exception as e:
            self._error_message = str(e)
            capture_status['status'] = 'error'
            capture_status['message'] = f"Capture error: {e}"
            print(f"[ERROR] Capture failed: {e}")

            # Give helpful Windows-specific error
            if platform.system() == 'Windows' and 'Npcap' in str(e):
                print("[ERROR] Npcap is not installed or not working properly.")
                print("[ERROR] Please install from: https://npcap.com/#download")
                print("[ERROR] Make sure to check 'WinPcap API-compatible Mode' during install!")

            self.is_running = False

    def _is_valid_domain(self, domain: str) -> bool:
        """Check if domain should be recorded (filter out noise)."""
        if not domain or len(domain) < 4:
            return False

        domain_lower = domain.lower()

        # Skip local/internal domains and system queries
        skip_patterns = [
            '.local', '.lan', '.internal', '.home', '.localdomain',
            'localhost', '._dns-sd', '._tcp', '._udp', '_msdcs',
            '.in-addr.arpa', '.ip6.arpa', 'wpad.', 'isatap.',
            '.msftconnecttest.', '.windowsupdate.', '.microsoft.com',
            '.windows.com', '.bing.com', '.msn.com',  # Windows noise
            'time.windows.com', 'dns.msftncsi',
            '.gstatic.com', '.googleapis.com',  # Common API noise
            'safebrowsing.', 'ocsp.', 'crl.',  # Security checks
            '.arpa', 'broadcasthost'
        ]

        for pattern in skip_patterns:
            if pattern in domain_lower:
                return False

        # Must have at least one dot (real domain)
        if '.' not in domain:
            return False

        # Skip IP addresses
        if re.match(r'^\d+\.\d+\.\d+\.\d+$', domain):
            return False

        # Skip very short TLDs or domains
        parts = domain.split('.')
        if len(parts) < 2 or len(parts[-1]) < 2:
            return False

        return True

    def _record_visit(self, domain: str, device_ip: str, protocol: str):
        """Record a website visit to the database."""
        # Clean up domain
        domain = domain.strip().lower()
        if domain.endswith('.'):
            domain = domain[:-1]

        # Skip duplicates in rapid succession (within same second)
        # This reduces noise from multiple DNS queries for same domain

        url = f"https://{domain}/"

        print(f"[CAPTURED] {domain} from {device_ip}")

        # Save to database
        self.database.add_capture(
            url=url,
            domain=domain,
            device_ip=device_ip,
            device_name=None,
            protocol=protocol
        )


# For testing
if __name__ == '__main__':
    from database import Database

    print("=" * 50)
    print("HomeWatch Network Capture Test")
    print("=" * 50)

    db = Database()
    capture = NetworkCapture(db)

    success, message = capture.start('auto')
    if not success:
        print(f"\n[FAILED] {message}")
        print("\nTroubleshooting:")
        print("1. Make sure you're running as Administrator")
        print("2. Install Npcap from https://npcap.com")
        print("3. Check 'WinPcap API-compatible Mode' during Npcap install")
        sys.exit(1)

    print(f"\n[OK] {message}")
    print("\nCapturing... Press Ctrl+C to stop\n")

    try:
        import time
        while capture.is_running:
            time.sleep(1)
            status = capture.get_status()
            if status['packets'] > 0:
                print(f"Packets captured: {status['packets']}")
    except KeyboardInterrupt:
        print("\n\nStopping capture...")
        capture.stop()

    print(f"\nTotal URLs captured: {db.get_total_count()}")
