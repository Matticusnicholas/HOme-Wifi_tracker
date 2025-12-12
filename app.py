#!/usr/bin/env python3
"""
HomeWatch - Simple Home WiFi Monitoring
A user-friendly web app to monitor websites visited on your home network.
"""

import os
import sqlite3
import threading
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import json

# Import our modules
from capture import NetworkCapture
from scheduler import ReportScheduler
from database import Database

app = Flask(__name__)
CORS(app)

# Initialize database
db = Database()

# Initialize network capture (will be started/stopped via UI)
capture = None
scheduler = None


@app.route('/')
def index():
    """Main dashboard page."""
    return render_template('index.html')


@app.route('/api/status')
def get_status():
    """Get current monitoring status."""
    global capture
    return jsonify({
        'monitoring': capture is not None and capture.is_running,
        'total_urls': db.get_total_count(),
        'today_count': db.get_today_count()
    })


@app.route('/api/start', methods=['POST'])
def start_monitoring():
    """Start network monitoring."""
    global capture
    if capture is None:
        capture = NetworkCapture(db)

    if not capture.is_running:
        interface = request.json.get('interface', 'auto')
        capture.start(interface)
        return jsonify({'success': True, 'message': 'Monitoring started'})
    return jsonify({'success': False, 'message': 'Already monitoring'})


@app.route('/api/stop', methods=['POST'])
def stop_monitoring():
    """Stop network monitoring."""
    global capture
    if capture and capture.is_running:
        capture.stop()
        return jsonify({'success': True, 'message': 'Monitoring stopped'})
    return jsonify({'success': False, 'message': 'Not currently monitoring'})


@app.route('/api/urls')
def get_urls():
    """Get captured URLs with optional filtering."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    search = request.args.get('search', '')
    date_filter = request.args.get('date', '')  # Format: YYYY-MM-DD
    device = request.args.get('device', '')

    urls = db.get_urls(
        page=page,
        per_page=per_page,
        search=search,
        date_filter=date_filter,
        device=device
    )

    return jsonify({
        'urls': urls,
        'page': page,
        'per_page': per_page,
        'total': db.get_filtered_count(search, date_filter, device)
    })


@app.route('/api/devices')
def get_devices():
    """Get list of devices seen on the network."""
    devices = db.get_devices()
    return jsonify({'devices': devices})


@app.route('/api/stats')
def get_stats():
    """Get statistics for the dashboard."""
    return jsonify({
        'today': db.get_stats('today'),
        'week': db.get_stats('week'),
        'top_sites': db.get_top_sites(10),
        'hourly_activity': db.get_hourly_activity()
    })


@app.route('/api/report')
def get_report():
    """Generate a report for a specific date range."""
    start_date = request.args.get('start', '')
    end_date = request.args.get('end', '')

    if not start_date:
        start_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    if not end_date:
        end_date = datetime.now().strftime('%Y-%m-%d')

    report = db.generate_report(start_date, end_date)
    return jsonify(report)


@app.route('/api/schedule', methods=['GET', 'POST'])
def manage_schedule():
    """Manage monitoring schedule and daily reports."""
    global scheduler

    if request.method == 'GET':
        if scheduler:
            return jsonify(scheduler.get_config())
        return jsonify({'enabled': False})

    # POST - update schedule
    config = request.json
    if scheduler is None:
        scheduler = ReportScheduler(db)

    scheduler.update_config(config)
    return jsonify({'success': True, 'message': 'Schedule updated'})


@app.route('/api/clear', methods=['POST'])
def clear_data():
    """Clear all captured data."""
    db.clear_all()
    return jsonify({'success': True, 'message': 'All data cleared'})


@app.route('/api/interfaces')
def get_interfaces():
    """Get available network interfaces."""
    interfaces = ['auto']
    try:
        # Try using scapy (which we already have)
        from scapy.all import get_if_list
        ifaces = get_if_list()
        # Filter out loopback and virtual interfaces
        filtered = [i for i in ifaces if not i.startswith(('lo', 'veth', 'docker', 'br-')) and i != 'lo']
        if filtered:
            interfaces = ['auto'] + filtered
    except:
        # Fallback: try socket method (works on most systems)
        try:
            import socket
            hostname = socket.gethostname()
            interfaces = ['auto', hostname]
        except:
            pass
    return jsonify({'interfaces': interfaces})


if __name__ == '__main__':
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║   🏠 HomeWatch - Simple WiFi Monitoring                   ║
    ║                                                           ║
    ║   Open your browser to: http://localhost:5000             ║
    ║                                                           ║
    ║   Note: Run with sudo for network capture capabilities    ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
    """)
    app.run(host='0.0.0.0', port=5000, debug=True)
