#!/usr/bin/env python3
"""
Network capture module for HomeWatch.
Captures DNS queries and HTTP/HTTPS traffic to identify visited websites.
"""

import threading
import re
from datetime import datetime
from typing import Optional, Callable
from urllib.parse import urlparse


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

    def start(self, interface: str = 'auto'):
        """Start network capture on the specified interface."""
        if self.is_running:
            return False

        self._interface = interface
        self._stop_event.clear()
        self.is_running = True

        self._capture_thread = threading.Thread(
            target=self._capture_loop,
            daemon=True
        )
        self._capture_thread.start()
        return True

    def stop(self):
        """Stop network capture."""
        if not self.is_running:
            return False

        self._stop_event.set()
        self.is_running = False

        if self._capture_thread:
            self._capture_thread.join(timeout=5)
        return True

    def _capture_loop(self):
        """Main capture loop - tries different capture methods."""
        # Try scapy first (most capable)
        if self._try_scapy_capture():
            return

        # Fallback to DNS-based monitoring
        if self._try_dns_capture():
            return

        # If all else fails, use demo mode
        self._demo_capture()

    def _try_scapy_capture(self) -> bool:
        """Try to capture using scapy library."""
        try:
            from scapy.all import sniff, DNS, DNSQR, IP, TCP, Raw
            import scapy.all as scapy

            def packet_handler(packet):
                """Process each captured packet."""
                if self._stop_event.is_set():
                    return

                # DNS Query capture
                if packet.haslayer(DNS) and packet.haslayer(DNSQR):
                    dns_query = packet[DNSQR].qname.decode('utf-8', errors='ignore')
                    if dns_query.endswith('.'):
                        dns_query = dns_query[:-1]

                    # Filter out noise (local domains, etc.)
                    if self._is_valid_domain(dns_query):
                        source_ip = packet[IP].src if packet.haslayer(IP) else 'unknown'
                        self._record_visit(dns_query, source_ip, 'DNS')

                # HTTP capture (port 80)
                if packet.haslayer(TCP) and packet.haslayer(Raw):
                    if packet[TCP].dport == 80 or packet[TCP].sport == 80:
                        try:
                            payload = packet[Raw].load.decode('utf-8', errors='ignore')
                            # Look for Host header in HTTP requests
                            host_match = re.search(r'Host:\s*([^\r\n]+)', payload)
                            if host_match:
                                host = host_match.group(1).strip()
                                source_ip = packet[IP].src if packet.haslayer(IP) else 'unknown'
                                self._record_visit(host, source_ip, 'HTTP')
                        except:
                            pass

            # Determine interface
            iface = None if self._interface == 'auto' else self._interface

            # Start sniffing
            print(f"Starting scapy capture on interface: {iface or 'default'}")
            sniff(
                filter="port 53 or port 80",
                prn=packet_handler,
                store=False,
                stop_filter=lambda x: self._stop_event.is_set(),
                iface=iface
            )
            return True

        except ImportError:
            print("Scapy not available, trying alternative methods...")
            return False
        except PermissionError:
            print("Permission denied - run with sudo for packet capture")
            return False
        except Exception as e:
            print(f"Scapy capture error: {e}")
            return False

    def _try_dns_capture(self) -> bool:
        """Try DNS-based capture using pypcap or similar."""
        try:
            import pcap

            pc = pcap.pcap(name=self._interface if self._interface != 'auto' else None)
            pc.setfilter('port 53')

            print("Starting pcap DNS capture...")

            for timestamp, packet in pc:
                if self._stop_event.is_set():
                    break

                # Parse DNS packet (simplified)
                try:
                    # Skip ethernet header (14 bytes) and IP header (20 bytes)
                    dns_data = packet[42:]
                    if len(dns_data) > 12:
                        # Extract domain name from DNS query
                        domain = self._parse_dns_name(dns_data[12:])
                        if domain and self._is_valid_domain(domain):
                            self._record_visit(domain, 'unknown', 'DNS')
                except:
                    pass

            return True

        except ImportError:
            print("pcap not available...")
            return False
        except Exception as e:
            print(f"pcap capture error: {e}")
            return False

    def _demo_capture(self):
        """Demo mode - generates sample data for testing."""
        import time
        import random

        print("Running in DEMO MODE - generating sample data")
        print("For real capture, install scapy and run with sudo")

        demo_sites = [
            'google.com', 'youtube.com', 'facebook.com', 'twitter.com',
            'instagram.com', 'reddit.com', 'amazon.com', 'netflix.com',
            'tiktok.com', 'wikipedia.org', 'github.com', 'stackoverflow.com',
            'twitch.tv', 'discord.com', 'spotify.com', 'linkedin.com'
        ]

        demo_devices = [
            '192.168.1.101', '192.168.1.102', '192.168.1.103',
            '192.168.1.104', '192.168.1.105'
        ]

        while not self._stop_event.is_set():
            # Generate random visit
            site = random.choice(demo_sites)
            device = random.choice(demo_devices)
            self._record_visit(site, device, 'DEMO')

            # Random delay between visits (1-10 seconds)
            time.sleep(random.uniform(1, 10))

    def _parse_dns_name(self, data: bytes) -> Optional[str]:
        """Parse a DNS name from raw bytes."""
        parts = []
        i = 0
        while i < len(data) and data[i] != 0:
            length = data[i]
            if length > 63:  # Pointer
                break
            parts.append(data[i+1:i+1+length].decode('utf-8', errors='ignore'))
            i += length + 1
        return '.'.join(parts) if parts else None

    def _is_valid_domain(self, domain: str) -> bool:
        """Check if domain should be recorded (filter noise)."""
        if not domain or len(domain) < 3:
            return False

        # Skip local/internal domains
        skip_patterns = [
            '.local', '.lan', '.internal', '.home',
            'localhost', '._dns-sd', '._tcp', '._udp',
            'arpa', '.in-addr.arpa', '.ip6.arpa'
        ]

        domain_lower = domain.lower()
        for pattern in skip_patterns:
            if pattern in domain_lower:
                return False

        # Must have at least one dot (be a real domain)
        if '.' not in domain:
            return False

        # Skip IP addresses
        if re.match(r'^\d+\.\d+\.\d+\.\d+$', domain):
            return False

        return True

    def _record_visit(self, domain: str, device_ip: str, protocol: str):
        """Record a website visit to the database."""
        # Clean up domain
        domain = domain.strip().lower()
        if domain.endswith('.'):
            domain = domain[:-1]

        # Create URL from domain
        url = f"https://{domain}/"

        # Get device name if known
        device_name = None  # Could lookup from database

        # Save to database
        self.database.add_capture(
            url=url,
            domain=domain,
            device_ip=device_ip,
            device_name=device_name,
            protocol=protocol
        )


# For testing
if __name__ == '__main__':
    from database import Database

    print("Testing network capture module...")
    db = Database()
    capture = NetworkCapture(db)

    print("Starting capture (Ctrl+C to stop)...")
    capture.start('auto')

    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping capture...")
        capture.stop()

    print(f"Total captures: {db.get_total_count()}")
