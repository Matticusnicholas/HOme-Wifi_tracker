#!/usr/bin/env python3
"""
Database module for HomeWatch.
Handles all SQLite database operations for storing and retrieving URL data.
"""

import sqlite3
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import threading

DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'data', 'homewatch.db')


class Database:
    """Thread-safe SQLite database handler for URL tracking."""

    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
        self._local = threading.local()
        self._ensure_directory()
        self._init_db()

    def _ensure_directory(self):
        """Create data directory if it doesn't exist."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, 'connection'):
            self._local.connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False
            )
            self._local.connection.row_factory = sqlite3.Row
        return self._local.connection

    def _init_db(self):
        """Initialize database tables."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Main table for URL captures
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS captures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                url TEXT NOT NULL,
                domain TEXT NOT NULL,
                device_ip TEXT,
                device_name TEXT,
                protocol TEXT DEFAULT 'HTTP',
                category TEXT
            )
        ''')

        # Table for known devices
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip_address TEXT UNIQUE NOT NULL,
                mac_address TEXT,
                friendly_name TEXT,
                first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_seen DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Table for scheduled reports config
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS schedule_config (
                id INTEGER PRIMARY KEY,
                enabled BOOLEAN DEFAULT FALSE,
                monitor_start_time TEXT DEFAULT '00:00',
                monitor_end_time TEXT DEFAULT '23:59',
                report_time TEXT DEFAULT '08:00',
                report_email TEXT,
                days_of_week TEXT DEFAULT 'Mon,Tue,Wed,Thu,Fri,Sat,Sun'
            )
        ''')

        # Create indexes for better performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON captures(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_domain ON captures(domain)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_device ON captures(device_ip)')

        conn.commit()

    def add_capture(self, url: str, domain: str, device_ip: str = None,
                    device_name: str = None, protocol: str = 'HTTP') -> int:
        """Add a new URL capture to the database."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO captures (url, domain, device_ip, device_name, protocol)
            VALUES (?, ?, ?, ?, ?)
        ''', (url, domain, device_ip, device_name, protocol))

        # Update device last seen
        if device_ip:
            cursor.execute('''
                INSERT INTO devices (ip_address, last_seen)
                VALUES (?, CURRENT_TIMESTAMP)
                ON CONFLICT(ip_address) DO UPDATE SET last_seen = CURRENT_TIMESTAMP
            ''', (device_ip,))

        conn.commit()
        return cursor.lastrowid

    def get_urls(self, page: int = 1, per_page: int = 50, search: str = '',
                 date_filter: str = '', device: str = '') -> List[Dict[str, Any]]:
        """Get captured URLs with filtering and pagination."""
        conn = self._get_connection()
        cursor = conn.cursor()

        query = 'SELECT * FROM captures WHERE 1=1'
        params = []

        if search:
            query += ' AND (url LIKE ? OR domain LIKE ?)'
            params.extend([f'%{search}%', f'%{search}%'])

        if date_filter:
            query += ' AND DATE(timestamp) = ?'
            params.append(date_filter)

        if device:
            query += ' AND (device_ip = ? OR device_name = ?)'
            params.extend([device, device])

        query += ' ORDER BY timestamp DESC LIMIT ? OFFSET ?'
        params.extend([per_page, (page - 1) * per_page])

        cursor.execute(query, params)
        rows = cursor.fetchall()

        return [self._row_to_dict(row) for row in rows]

    def get_filtered_count(self, search: str = '', date_filter: str = '',
                           device: str = '') -> int:
        """Get total count of filtered results."""
        conn = self._get_connection()
        cursor = conn.cursor()

        query = 'SELECT COUNT(*) FROM captures WHERE 1=1'
        params = []

        if search:
            query += ' AND (url LIKE ? OR domain LIKE ?)'
            params.extend([f'%{search}%', f'%{search}%'])

        if date_filter:
            query += ' AND DATE(timestamp) = ?'
            params.append(date_filter)

        if device:
            query += ' AND (device_ip = ? OR device_name = ?)'
            params.extend([device, device])

        cursor.execute(query, params)
        return cursor.fetchone()[0]

    def get_total_count(self) -> int:
        """Get total number of captures."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM captures')
        return cursor.fetchone()[0]

    def get_today_count(self) -> int:
        """Get number of captures today."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT COUNT(*) FROM captures
            WHERE DATE(timestamp) = DATE('now')
        ''')
        return cursor.fetchone()[0]

    def get_devices(self) -> List[Dict[str, Any]]:
        """Get all known devices."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT d.*, COUNT(c.id) as visit_count
            FROM devices d
            LEFT JOIN captures c ON d.ip_address = c.device_ip
            GROUP BY d.id
            ORDER BY d.last_seen DESC
        ''')
        return [self._row_to_dict(row) for row in cursor.fetchall()]

    def update_device_name(self, ip_address: str, friendly_name: str) -> bool:
        """Update a device's friendly name."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE devices SET friendly_name = ? WHERE ip_address = ?
        ''', (friendly_name, ip_address))
        conn.commit()
        return cursor.rowcount > 0

    def get_stats(self, period: str = 'today') -> Dict[str, Any]:
        """Get statistics for a given period."""
        conn = self._get_connection()
        cursor = conn.cursor()

        if period == 'today':
            date_condition = "DATE(timestamp) = DATE('now')"
        elif period == 'week':
            date_condition = "timestamp >= DATE('now', '-7 days')"
        elif period == 'month':
            date_condition = "timestamp >= DATE('now', '-30 days')"
        else:
            date_condition = '1=1'

        cursor.execute(f'''
            SELECT
                COUNT(*) as total_visits,
                COUNT(DISTINCT domain) as unique_sites,
                COUNT(DISTINCT device_ip) as active_devices
            FROM captures
            WHERE {date_condition}
        ''')

        row = cursor.fetchone()
        return {
            'total_visits': row['total_visits'],
            'unique_sites': row['unique_sites'],
            'active_devices': row['active_devices']
        }

    def get_top_sites(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get most visited sites."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT domain, COUNT(*) as visit_count,
                   MAX(timestamp) as last_visit
            FROM captures
            WHERE timestamp >= DATE('now', '-7 days')
            GROUP BY domain
            ORDER BY visit_count DESC
            LIMIT ?
        ''', (limit,))
        return [self._row_to_dict(row) for row in cursor.fetchall()]

    def get_hourly_activity(self) -> List[Dict[str, int]]:
        """Get activity breakdown by hour for today."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT strftime('%H', timestamp) as hour, COUNT(*) as count
            FROM captures
            WHERE DATE(timestamp) = DATE('now')
            GROUP BY hour
            ORDER BY hour
        ''')

        # Fill in missing hours with 0
        hourly = {str(i).zfill(2): 0 for i in range(24)}
        for row in cursor.fetchall():
            hourly[row['hour']] = row['count']

        return [{'hour': h, 'count': c} for h, c in hourly.items()]

    def generate_report(self, start_date: str, end_date: str) -> Dict[str, Any]:
        """Generate a detailed report for a date range."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Summary stats
        cursor.execute('''
            SELECT
                COUNT(*) as total_visits,
                COUNT(DISTINCT domain) as unique_sites,
                COUNT(DISTINCT device_ip) as devices
            FROM captures
            WHERE DATE(timestamp) BETWEEN ? AND ?
        ''', (start_date, end_date))
        summary = self._row_to_dict(cursor.fetchone())

        # Top sites
        cursor.execute('''
            SELECT domain, COUNT(*) as visits
            FROM captures
            WHERE DATE(timestamp) BETWEEN ? AND ?
            GROUP BY domain
            ORDER BY visits DESC
            LIMIT 20
        ''', (start_date, end_date))
        top_sites = [self._row_to_dict(row) for row in cursor.fetchall()]

        # Activity by device
        cursor.execute('''
            SELECT
                COALESCE(d.friendly_name, c.device_ip) as device,
                COUNT(*) as visits,
                COUNT(DISTINCT c.domain) as sites
            FROM captures c
            LEFT JOIN devices d ON c.device_ip = d.ip_address
            WHERE DATE(c.timestamp) BETWEEN ? AND ?
            GROUP BY c.device_ip
            ORDER BY visits DESC
        ''', (start_date, end_date))
        by_device = [self._row_to_dict(row) for row in cursor.fetchall()]

        # Recent activity (last 100 entries in range)
        cursor.execute('''
            SELECT timestamp, domain, device_ip
            FROM captures
            WHERE DATE(timestamp) BETWEEN ? AND ?
            ORDER BY timestamp DESC
            LIMIT 100
        ''', (start_date, end_date))
        recent = [self._row_to_dict(row) for row in cursor.fetchall()]

        return {
            'period': {'start': start_date, 'end': end_date},
            'summary': summary,
            'top_sites': top_sites,
            'by_device': by_device,
            'recent_activity': recent
        }

    def clear_all(self):
        """Clear all captured data."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM captures')
        conn.commit()

    def _row_to_dict(self, row) -> Dict[str, Any]:
        """Convert a sqlite Row to a dictionary."""
        if row is None:
            return {}
        return dict(row)


# For testing
if __name__ == '__main__':
    db = Database()
    print("Database initialized successfully!")
    print(f"Database location: {DATABASE_PATH}")
