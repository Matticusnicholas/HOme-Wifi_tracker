#!/usr/bin/env python3
"""
Scheduler module for HomeWatch.
Handles scheduled monitoring windows and automated daily reports.
"""

import threading
import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    HAS_SCHEDULER = True
except ImportError:
    HAS_SCHEDULER = False


CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'data', 'schedule_config.json')


class ReportScheduler:
    """
    Handles scheduling for monitoring windows and daily report generation.
    """

    def __init__(self, database):
        self.database = database
        self.config = self._load_config()
        self._scheduler = None

        if HAS_SCHEDULER:
            self._scheduler = BackgroundScheduler()
            self._scheduler.start()
            self._setup_jobs()

    def _load_config(self) -> Dict[str, Any]:
        """Load scheduler configuration from file."""
        default_config = {
            'enabled': False,
            'monitor_start_time': '00:00',
            'monitor_end_time': '23:59',
            'report_enabled': False,
            'report_time': '08:00',
            'report_email': '',
            'smtp_server': '',
            'smtp_port': 587,
            'smtp_user': '',
            'smtp_password': '',
            'days_of_week': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        }

        try:
            if os.path.exists(CONFIG_PATH):
                with open(CONFIG_PATH, 'r') as f:
                    saved_config = json.load(f)
                    default_config.update(saved_config)
        except Exception as e:
            print(f"Error loading config: {e}")

        return default_config

    def _save_config(self):
        """Save scheduler configuration to file."""
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        try:
            with open(CONFIG_PATH, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")

    def get_config(self) -> Dict[str, Any]:
        """Get current scheduler configuration."""
        # Don't expose sensitive SMTP password
        safe_config = self.config.copy()
        if 'smtp_password' in safe_config:
            safe_config['smtp_password'] = '***' if safe_config['smtp_password'] else ''
        return safe_config

    def update_config(self, new_config: Dict[str, Any]):
        """Update scheduler configuration."""
        # Don't overwrite password if masked
        if new_config.get('smtp_password') == '***':
            new_config['smtp_password'] = self.config.get('smtp_password', '')

        self.config.update(new_config)
        self._save_config()

        # Reschedule jobs with new config
        if self._scheduler:
            self._setup_jobs()

    def _setup_jobs(self):
        """Setup scheduled jobs based on configuration."""
        if not self._scheduler:
            return

        # Remove existing jobs
        self._scheduler.remove_all_jobs()

        if not self.config.get('enabled'):
            return

        # Schedule daily report if enabled
        if self.config.get('report_enabled') and self.config.get('report_email'):
            report_time = self.config.get('report_time', '08:00')
            hour, minute = map(int, report_time.split(':'))

            days_map = {
                'Mon': 'mon', 'Tue': 'tue', 'Wed': 'wed',
                'Thu': 'thu', 'Fri': 'fri', 'Sat': 'sat', 'Sun': 'sun'
            }
            days = self.config.get('days_of_week', [])
            day_of_week = ','.join([days_map[d] for d in days if d in days_map])

            if day_of_week:
                self._scheduler.add_job(
                    self._send_daily_report,
                    CronTrigger(hour=hour, minute=minute, day_of_week=day_of_week),
                    id='daily_report',
                    replace_existing=True
                )
                print(f"Daily report scheduled for {report_time} on {day_of_week}")

    def _send_daily_report(self):
        """Generate and send the daily report email."""
        # Generate report for yesterday
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        report = self.database.generate_report(yesterday, yesterday)

        # Format report as HTML email
        html_content = self._format_report_html(report)

        # Send email
        self._send_email(
            to_email=self.config.get('report_email'),
            subject=f"HomeWatch Daily Report - {yesterday}",
            html_content=html_content
        )

    def _format_report_html(self, report: Dict[str, Any]) -> str:
        """Format report data as HTML for email."""
        summary = report.get('summary', {})
        top_sites = report.get('top_sites', [])
        by_device = report.get('by_device', [])

        # Build top sites table
        sites_rows = ""
        for site in top_sites[:10]:
            sites_rows += f"""
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #ddd;">{site.get('domain', 'Unknown')}</td>
                <td style="padding: 8px; border-bottom: 1px solid #ddd; text-align: center;">{site.get('visits', 0)}</td>
            </tr>
            """

        # Build devices table
        devices_rows = ""
        for device in by_device:
            devices_rows += f"""
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #ddd;">{device.get('device', 'Unknown')}</td>
                <td style="padding: 8px; border-bottom: 1px solid #ddd; text-align: center;">{device.get('visits', 0)}</td>
                <td style="padding: 8px; border-bottom: 1px solid #ddd; text-align: center;">{device.get('sites', 0)}</td>
            </tr>
            """

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #4a90d9; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }}
                .content {{ background: #f9f9f9; padding: 20px; border-radius: 0 0 8px 8px; }}
                .stat-box {{ display: inline-block; background: white; padding: 15px; margin: 5px; border-radius: 8px; text-align: center; min-width: 100px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .stat-number {{ font-size: 24px; font-weight: bold; color: #4a90d9; }}
                .stat-label {{ font-size: 12px; color: #666; }}
                table {{ width: 100%; border-collapse: collapse; margin: 15px 0; background: white; border-radius: 8px; overflow: hidden; }}
                th {{ background: #4a90d9; color: white; padding: 12px 8px; text-align: left; }}
                h2 {{ color: #333; border-bottom: 2px solid #4a90d9; padding-bottom: 5px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>HomeWatch Daily Report</h1>
                    <p>{report.get('period', {}).get('start', 'Yesterday')}</p>
                </div>
                <div class="content">
                    <h2>Summary</h2>
                    <div style="text-align: center; margin: 20px 0;">
                        <div class="stat-box">
                            <div class="stat-number">{summary.get('total_visits', 0)}</div>
                            <div class="stat-label">Total Visits</div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-number">{summary.get('unique_sites', 0)}</div>
                            <div class="stat-label">Unique Sites</div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-number">{summary.get('devices', 0)}</div>
                            <div class="stat-label">Active Devices</div>
                        </div>
                    </div>

                    <h2>Top Visited Sites</h2>
                    <table>
                        <tr>
                            <th>Website</th>
                            <th style="text-align: center;">Visits</th>
                        </tr>
                        {sites_rows if sites_rows else '<tr><td colspan="2" style="padding: 20px; text-align: center;">No activity recorded</td></tr>'}
                    </table>

                    <h2>Activity by Device</h2>
                    <table>
                        <tr>
                            <th>Device</th>
                            <th style="text-align: center;">Visits</th>
                            <th style="text-align: center;">Sites</th>
                        </tr>
                        {devices_rows if devices_rows else '<tr><td colspan="3" style="padding: 20px; text-align: center;">No activity recorded</td></tr>'}
                    </table>

                    <p style="text-align: center; color: #666; font-size: 12px; margin-top: 20px;">
                        Generated by HomeWatch - Your friendly home WiFi monitor
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        return html

    def _send_email(self, to_email: str, subject: str, html_content: str):
        """Send an email using configured SMTP settings."""
        smtp_server = self.config.get('smtp_server')
        smtp_port = self.config.get('smtp_port', 587)
        smtp_user = self.config.get('smtp_user')
        smtp_password = self.config.get('smtp_password')

        if not all([smtp_server, smtp_user, smtp_password, to_email]):
            print("Email not configured properly, skipping...")
            return

        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = smtp_user
            msg['To'] = to_email

            # Plain text version
            text_content = f"HomeWatch Daily Report\n\nPlease view this email in an HTML-capable client."
            msg.attach(MIMEText(text_content, 'plain'))
            msg.attach(MIMEText(html_content, 'html'))

            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_password)
                server.sendmail(smtp_user, to_email, msg.as_string())

            print(f"Report sent to {to_email}")

        except Exception as e:
            print(f"Failed to send email: {e}")

    def generate_report_now(self, days_back: int = 1) -> Dict[str, Any]:
        """Generate a report immediately for the specified number of days back."""
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
        return self.database.generate_report(start_date, end_date)


# For testing
if __name__ == '__main__':
    from database import Database

    print("Testing scheduler module...")
    db = Database()
    scheduler = ReportScheduler(db)

    print("Current config:", scheduler.get_config())
