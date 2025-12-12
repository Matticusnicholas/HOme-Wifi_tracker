# HomeWatch - Simple WiFi Monitor

A user-friendly web application for monitoring websites visited on your home network. Unlike complex tools like Wireshark, HomeWatch presents information in simple terms that anyone can understand.

## Features

- **Simple Dashboard** - See at-a-glance what websites are being visited
- **Activity Log** - Browse all captured URLs with search and filtering
- **Device Tracking** - See which devices on your network are visiting which sites
- **Daily Reports** - Automated email reports summarizing daily activity
- **Scheduled Monitoring** - Set specific times for monitoring
- **Clean Interface** - No technical jargon, just simple information

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the Application

```bash
# For demo mode (generates sample data, no root required):
python app.py

# For real network capture (requires root/admin):
sudo python app.py
```

### 3. Open Your Browser

Navigate to: **http://localhost:5000**

## How It Works

HomeWatch monitors your network by capturing DNS queries - the requests your devices make to look up website addresses. This allows it to see what domains are being accessed without needing to decrypt any traffic.

### What You'll See

| Column | Description |
|--------|-------------|
| **Time** | When the website was visited |
| **Website** | The domain name (e.g., youtube.com) |
| **Device** | Which device on your network made the request |

### What You Won't See

- Specific pages visited (only the main domain)
- Content of encrypted (HTTPS) traffic
- Login credentials or private data

## Screenshots

### Dashboard
The main dashboard shows:
- Total sites captured today
- Unique websites visited
- Active devices on network
- Top visited sites chart

### Activity Log
Browse and search all captured activity with filters for:
- Date range
- Specific device
- Domain search

### Reports
Generate reports for any date range showing:
- Summary statistics
- Most visited sites
- Activity by device

## Setup for Real Monitoring

### Linux (Recommended)

1. Install required system packages:
```bash
sudo apt-get install python3-pip libpcap-dev
```

2. Install Python dependencies:
```bash
pip3 install -r requirements.txt
```

3. Run with sudo:
```bash
sudo python3 app.py
```

### macOS

1. Install Homebrew if not present, then:
```bash
brew install libpcap
pip3 install -r requirements.txt
```

2. Run with sudo:
```bash
sudo python3 app.py
```

### Windows

Network capture on Windows requires additional setup:
1. Install [Npcap](https://nmap.org/npcap/) with WinPcap compatibility mode
2. Run Command Prompt as Administrator
3. Run: `python app.py`

## Network Setup Options

For HomeWatch to see all network traffic, it needs to be positioned appropriately:

### Option 1: Run on Your Router (Advanced)
If you have a Linux-based router (OpenWrt, DD-WRT, etc.), you can run HomeWatch directly on it.

### Option 2: Network Tap/Mirror Port
Configure your router or switch to mirror all traffic to the monitoring device.

### Option 3: ARP Spoofing (Not Recommended)
Can capture traffic but may cause network issues.

### Option 4: DNS Server Mode (Easiest)
Run a local DNS server and configure your router to use it. HomeWatch can log all DNS queries.

## Configuration

### Email Reports Setup

To receive daily email reports:

1. Go to Settings tab
2. Enable "Send daily email report"
3. Enter your email address
4. Configure SMTP settings:

**For Gmail:**
- Server: smtp.gmail.com
- Port: 587
- Username: your@gmail.com
- Password: App Password (not your regular password)

Note: Create an App Password at https://myaccount.google.com/apppasswords

## Demo Mode

If you run without root privileges, HomeWatch automatically enters demo mode, generating realistic sample data so you can explore the interface.

## Privacy & Security Notes

- All data is stored locally in SQLite database
- No data is sent to external servers
- Captured data includes only domain names, not full URLs or content
- Consider the privacy implications before monitoring others

## Troubleshooting

### "Permission denied" error
Run with sudo/administrator privileges for network capture.

### No data captured
- Check that your network interface is correct
- Verify the monitoring device can see network traffic
- Try running in demo mode first to verify the app works

### Email reports not sending
- Verify SMTP settings
- Check spam folder
- For Gmail, use an App Password, not your regular password

## Files Structure

```
homewatch/
├── app.py              # Main Flask application
├── database.py         # Database operations
├── capture.py          # Network capture module
├── scheduler.py        # Report scheduling
├── requirements.txt    # Python dependencies
├── templates/
│   └── index.html      # Web interface
├── static/
│   ├── css/
│   │   └── style.css   # Styles
│   └── js/
│       └── app.js      # Frontend JavaScript
└── data/
    └── homewatch.db    # SQLite database (created automatically)
```

## License

MIT License - Feel free to use and modify for personal use.

---

**HomeWatch** - Simple WiFi monitoring for your home
