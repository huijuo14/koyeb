import requests
from bs4 import BeautifulSoup
import time
import re
import logging
import random
from datetime import datetime, timedelta
from flask import Flask
import threading
import pickle
import os
import json
import base64

# Enhanced logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger()

app = Flask(__name__)

class UltimateSmartBidder:
    def __init__(self):
        # ✅ ALL SETTINGS FROM ENVIRONMENT VARIABLES
        self.bot_token = os.environ.get('BOT_TOKEN', "8439342017:AAEmRrBp-AKzVK6cbRdHekDGSpbgi7aH5Nc")
        self.chat_id = os.environ.get('CHAT_ID', "2052085789")
        self.backup_user_id = os.environ.get('BACKUP_USER_ID', "3160648324")  # Your user ID
        self.email = os.environ.get('EMAIL', "loginallapps@gmail.com")
        self.password = os.environ.get('PASSWORD', "@Sd2007123")
        self.last_update_id = 0
        
        self.session = requests.Session()
        self.rotate_user_agent()
        self.session_valid = False
        
        self.is_monitoring = False
        self.campaigns = {}
        
        # Required attributes
        self.competitor_activity = {}
        self.bid_history = {}
        self.sent_alerts = {}
        self.last_bid_time = {}
        
        # ✅ CONFIGURABLE FROM ENV VARS
        self.minimal_bid_weights = [1, 2]
        self.check_interval = int(os.environ.get('CHECK_INTERVAL', '180'))  # 3 minutes
        self.max_bid_limit = int(os.environ.get('MAX_BID_LIMIT', '369'))
        self.bid_cooldown = 60
        
        self.visitor_alert_threshold = int(os.environ.get('VISITOR_ALERT_THRESHOLD', '1000'))
        self.visitor_stop_threshold = int(os.environ.get('VISITOR_STOP_THRESHOLD', '500'))
        self.current_traffic_credits = 0
        self.current_visitor_credits = 0
        self.last_credit_alert = None
        
        # Performance Tracking
        self.performance_stats = {
            'peak_hours': {},
            'off_peak_hours': {},  
            'hourly_views': {},
            'campaign_performance': {},
            'total_views_tracked': 0,
            'last_views_snapshot': {},
            'activity_pulses': 0,
            'total_bid_changes': 0,
            'last_restore_time': None
        }
        
        self.last_views_check = time.time()
        self.views_check_interval = 3600
        
        self.load_bot_state()
        self.setup_enhanced_logging()
        
        logger.info(f"BOT_INITIALIZED - Check interval: {self.check_interval}s, Max bid: {self.max_bid_limit}")

    def setup_enhanced_logging(self):
        """Enhanced logging for better Koyeb monitoring"""
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        class EnhancedFormatter(logging.Formatter):
            def format(self, record):
                emoji = {
                    'INFO': '🟢',
                    'WARNING': '🟡', 
                    'ERROR': '🔴',
                    'DEBUG': '🔵'
                }.get(record.levelname, '⚪')
                record.levelname = f"{emoji} {record.levelname}"
                return super().format(record)
        
        formatter = EnhancedFormatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    def save_bot_state(self):
        """Save state with Telegram backup to your user ID"""
        try:
            state_data = {
                'campaigns': self.campaigns,
                'last_update_id': self.last_update_id,
                'is_monitoring': self.is_monitoring,
                'performance_stats': self.performance_stats,
                'competitor_activity': self.competitor_activity,
                'bid_history': self.bid_history,
                'sent_alerts': self.sent_alerts,
                'save_time': datetime.now().isoformat(),
                'version': '2.0'
            }
            
            # 1. Save to /tmp
            tmp_file = '/tmp/bot_state.pkl'
            with open(tmp_file, 'wb') as f:
                pickle.dump(state_data, f)
            
            # 2. Backup to Telegram (to your user ID)
            self.backup_to_telegram(state_data)
            
            logger.info(f"STATE_SAVED - {len(self.campaigns)} campaigns with Telegram backup")
            
        except Exception as e:
            logger.error(f"STATE_SAVE_ERROR - {e}")

    def backup_to_telegram(self, state_data):
        """Backup state to your Telegram account"""
        try:
            # Convert to compact base64 for smaller messages
            state_bytes = pickle.dumps(state_data)
            state_b64 = base64.b64encode(state_bytes).decode('utf-8')
            
            # Split into chunks if too large
            if len(state_b64) > 4000:
                logger.warning("STATE_TOO_LARGE - Using compact backup")
                # Create compact version without large data
                compact_data = {
                    'campaigns': {name: {'my_bid': data['my_bid'], 'top_bid': data.get('top_bid', 0), 'auto_bid': data['auto_bid']} 
                                 for name, data in state_data['campaigns'].items()},
                    'last_update_id': state_data['last_update_id'],
                    'is_monitoring': state_data['is_monitoring'],
                    'save_time': state_data['save_time']
                }
                state_bytes = pickle.dumps(compact_data)
                state_b64 = base64.b64encode(state_bytes).decode('utf-8')
            
            message = f"🤖 STATE_BACKUP:{state_b64}"
            
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            data = {
                "chat_id": self.backup_user_id,  # Your user ID
                "text": message,
                "parse_mode": "HTML"
            }
            
            response = self.session.post(url, json=data, timeout=30)
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"TELEGRAM_BACKUP_FAILED - {e}")
            return False

    def load_bot_state(self):
        """Load state with Telegram fallback"""
        try:
            # 1. Try /tmp first
            tmp_file = '/tmp/bot_state.pkl'
            if os.path.exists(tmp_file):
                with open(tmp_file, 'rb') as f:
                    state_data = pickle.load(f)
                    self.restore_state_data(state_data)
                    logger.info("STATE_LOADED - From /tmp storage")
                    return True
            
            # 2. Fallback to Telegram backup
            if self.restore_from_telegram():
                logger.info("STATE_RESTORED - From Telegram backup")
                return True
                
            logger.info("STATE_FRESH - No previous state found")
            return False
            
        except Exception as e:
            logger.error(f"STATE_LOAD_ERROR - {e}")
            return False

    def restore_from_telegram(self):
        """Restore state from your Telegram messages"""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
            response = self.session.get(url, timeout=30)
            data = response.json()
            
            if data.get('ok'):
                # Find the latest state backup message
                for update in reversed(data['result']):
                    if 'message' in update and 'text' in update['message']:
                        text = update['message']['text']
                        if "STATE_BACKUP:" in text:
                            # Extract base64 data
                            state_b64 = text.split("STATE_BACKUP:")[1].strip()
                            state_bytes = base64.b64decode(state_b64)
                            state_data = pickle.loads(state_bytes)
                            
                            self.restore_state_data(state_data)
                            return True
            return False
            
        except Exception as e:
            logger.error(f"TELEGRAM_RESTORE_ERROR - {e}")
            return False

    def restore_state_data(self, state_data):
        """Restore data from state"""
        self.campaigns = state_data.get('campaigns', {})
        self.last_update_id = state_data.get('last_update_id', 0)
        self.is_monitoring = state_data.get('is_monitoring', False)
        self.performance_stats = state_data.get('performance_stats', self.performance_stats)
        self.competitor_activity = state_data.get('competitor_activity', {})
        self.bid_history = state_data.get('bid_history', {})
        self.sent_alerts = state_data.get('sent_alerts', {})
        
        # Update restore time
        self.performance_stats['last_restore_time'] = datetime.now().isoformat()

    def log_activity_pulse(self):
        """Log activity to prevent sleep"""
        self.performance_stats['activity_pulses'] += 1
        logger.info(f"ACTIVITY_PULSE - Bot active | Pulses: {self.performance_stats['activity_pulses']} | Campaigns: {len(self.campaigns)}")

    def rotate_user_agent(self):
        user_agents = ['Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36']
        self.session.headers.update({'User-Agent': random.choice(user_agents)})

    def human_delay(self, min_seconds=2, max_seconds=5):
        delay = random.uniform(min_seconds, max_seconds)
        time.sleep(delay)
        return delay

    def force_login(self):
        try:
            logger.info("LOGIN_ATTEMPT - Starting login process")
            self.human_delay(2, 4)
            
            login_url = "https://adsha.re/login"
            response = self.session.get(login_url, timeout=30)
            self.human_delay(1, 2)
            
            soup = BeautifulSoup(response.content, 'html.parser')
            form = soup.find('form', {'name': 'login'})
            if not form:
                logger.error("LOGIN_FAILED - Login form not found")
                return False
                
            action_path = form.get('action', '')
            post_url = f"https://adsha.re{action_path}" if not action_path.startswith('http') else action_path
            
            password_field = None
            for field in form.find_all('input'):
                field_name = field.get('name', '')
                field_value = field.get('value', '')
                if field_value == 'Password' and field_name != 'mail' and field_name:
                    password_field = field_name
                    break
            
            if not password_field:
                logger.error("LOGIN_FAILED - Password field not found")
                return False
            
            login_data = {
                'mail': self.email,
                password_field: self.password
            }
            
            response = self.session.post(post_url, data=login_data, allow_redirects=True)
            self.human_delay(1, 2)
            
            if self.check_session_valid():
                self.session_valid = True
                logger.info("LOGIN_SUCCESS - Session active")
                return True
            
            logger.error("LOGIN_FAILED - Session validation failed")
            return False
        except Exception as e:
            logger.error(f"LOGIN_ERROR - {e}")
            return False

    def check_session_valid(self):
        try:
            response = self.session.get("https://adsha.re/adverts", timeout=10, allow_redirects=False)
            if response.status_code == 302 and "login" in response.headers.get('Location', ''):
                self.session_valid = False
                return False
            self.session_valid = True
            return True
        except:
            self.session_valid = False
            return False

    def smart_login(self):
        if self.check_session_valid():
            logger.info("SESSION_VALID - Session still active")
            self.session_valid = True
            return True
        
        logger.warning("SESSION_EXPIRED - Re-login required")
        return self.force_login()

    def get_traffic_credits(self):
        try:
            response = self.session.get("https://adsha.re/exchange/credits/adverts", timeout=30)
            soup = BeautifulSoup(response.content, 'html.parser')
            credit_div = soup.find('div', style=re.compile(r'font-size:22pt'))
            if credit_div:
                credit_text = credit_div.get_text().strip()
                credit_match = re.search(r'(\d+\.?\d*)', credit_text)
                if credit_match:
                    return float(credit_match.group(1))
            return 0
        except Exception as e:
            logger.error(f"TRAFFIC_CREDITS_ERROR - {e}")
            return 0

    def get_visitor_credits(self):
        try:
            response = self.session.get("https://adsha.re/adverts", timeout=30)
            soup = BeautifulSoup(response.content, 'html.parser')
            visitors_match = re.search(r'Visitors:\s*([\d,]+)', soup.get_text())
            if visitors_match:
                visitors_str = visitors_match.group(1).replace(',', '')
                return int(visitors_str)
            return 0
        except Exception as e:
            logger.error(f"VISITOR_CREDITS_ERROR - {e}")
            return 0

    def check_credit_safety(self):
        self.current_traffic_credits = self.get_traffic_credits()
        self.current_visitor_credits = self.get_visitor_credits()
        
        if self.current_traffic_credits >= 1000:
            if self.last_credit_alert != 'convert':
                self.send_telegram(f"💰 CONVERT CREDITS: You have {self.current_traffic_credits} traffic credits - convert to visitors!")
                self.last_credit_alert = 'convert'
        
        if self.current_visitor_credits < self.visitor_stop_threshold:
            if self.last_credit_alert != 'stop':
                self.send_telegram(f"🛑 CRITICAL: Only {self.current_visitor_credits} visitors left! Auto-bid stopped.")
                self.last_credit_alert = 'stop'
            return False
        elif self.current_visitor_credits < self.visitor_alert_threshold:
            if self.last_credit_alert != 'alert':
                self.send_telegram(f"⚠️ WARNING: Low visitors - {self.current_visitor_credits} left!")
                self.last_credit_alert = 'alert'
            return True
        
        self.last_credit_alert = None
        return True

    def send_telegram(self, message, parse_mode='HTML'):
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            data = {
                "chat_id": self.chat_id, 
                "text": message, 
                "parse_mode": parse_mode
            }
            response = self.session.post(url, json=data, timeout=30)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"TELEGRAM_SEND_ERROR - {e}")
            return False

    def process_telegram_command(self):
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
            params = {'offset': self.last_update_id + 1, 'timeout': 5}
            response = self.session.get(url, params=params, timeout=10)
            data = response.json()
            
            if data.get('ok') and data.get('result'):
                for update in data['result']:
                    update_id = update['update_id']
                    if update_id > self.last_update_id:
                        self.last_update_id = update_id
                        if 'message' in update and 'text' in update['message']:
                            text = update['message']['text']
                            chat_id = update['message']['chat']['id']
                            if str(chat_id) != self.chat_id:
                                continue
                            if text.startswith('/'):
                                self.handle_command(text, chat_id)
        except Exception as e:
            logger.error(f"TELEGRAM_COMMAND_ERROR - {e}")

    def handle_command(self, command, chat_id):
        command_lower = command.lower().strip()
        
        if command_lower == '/start':
            self.start_monitoring()
        elif command_lower == '/stop':
            self.stop_monitoring()
        elif command_lower == '/status':
            self.send_enhanced_status()
        elif command_lower == '/campaigns':
            self.send_campaigns_list()
        elif command_lower == '/stats':
            self.send_performance_stats()
        elif command_lower == '/credits':
            self.send_credit_status()
        elif command_lower == '/backup':
            self.save_bot_state()
            self.send_telegram("💾 Manual backup completed!")
        elif command_lower == '/restore':
            if self.load_bot_state():
                self.send_telegram("🔄 State restored from backup!")
            else:
                self.send_telegram("❌ No backup found to restore")
        elif command_lower.startswith('/auto'):
            self.handle_auto_command(command)
        elif command_lower == '/help':
            self.send_enhanced_help()
        else:
            self.send_telegram("❌ Unknown command. Use /help for available commands")

    def handle_auto_command(self, command):
        parts = command.split()
        
        if len(parts) == 1:
            self.send_telegram("❌ Usage: /auto [campaign] on/off\nOr: /auto all on/off")
            return
            
        if len(parts) == 2 and parts[1].lower() in ['on', 'off']:
            action = parts[1].lower()
            self.toggle_all_auto_bid(action == 'on')
            return
            
        if len(parts) == 3 and parts[1].lower() == 'all':
            action = parts[2].lower()
            self.toggle_all_auto_bid(action == 'on')
            return
            
        if len(parts) >= 3:
            campaign_name = ' '.join(parts[1:-1])
            action = parts[-1].lower()
            
            if action not in ['on', 'off']:
                return
            
            found_campaign = None
            for stored_name in self.campaigns.keys():
                if stored_name.lower() == campaign_name.lower():
                    found_campaign = stored_name
                    break
            
            if found_campaign:
                self.toggle_auto_bid(found_campaign, action == 'on')

    def toggle_auto_bid(self, campaign_name, enable):
        if campaign_name in self.campaigns:
            self.campaigns[campaign_name]['auto_bid'] = enable
            status = "enabled" if enable else "disabled"
            self.send_telegram(f"🔄 Auto-bid {status} for '{campaign_name}'")
            logger.info(f"AUTO_BID_TOGGLE - {campaign_name} | {status}")
            self.save_bot_state()

    def toggle_all_auto_bid(self, enable):
        for campaign_name in self.campaigns:
            self.campaigns[campaign_name]['auto_bid'] = enable
        
        status = "enabled" if enable else "disabled"
        self.send_telegram(f"🔄 Auto-bid {status} for all campaigns")
        logger.info(f"AUTO_BID_ALL_TOGGLE - All campaigns | {status}")
        self.save_bot_state()

    def start_monitoring(self):
        self.is_monitoring = True
        logger.info("BOT_STARTED - Monitoring activated")
        self.send_telegram("🚀 Ultimate Smart Bidder ACTIVATED!\n\nMonitoring all campaigns...")
        self.send_enhanced_status()

    def stop_monitoring(self):
        self.is_monitoring = False
        logger.info("BOT_STOPPED - Monitoring stopped")
        self.send_telegram("🛑 Bot STOPPED!\nUse /start to resume monitoring.")

    def send_enhanced_status(self):
        if not self.campaigns:
            self.send_telegram("📊 No campaigns loaded. Monitoring adsha.re for campaigns...")
            return
        
        traffic_credits = self.get_traffic_credits()
        visitor_credits = self.get_visitor_credits()
            
        status_msg = f"""
📊 ENHANCED STATUS REPORT

💰 CREDITS:
Traffic: {traffic_credits} | Visitors: {visitor_credits:,}

🏆 CAMPAIGN STATUS:
"""
        
        for name, data in self.campaigns.items():
            is_top = data.get('my_bid', 0) >= data.get('top_bid', 0)
            status = "✅ AUTO" if data.get('auto_bid', False) else "❌ MANUAL"
            position = "🏆 #1" if is_top else f"📉 #{data.get('position', '2+')}"
            
            views_info = ""
            if 'views' in data:
                views = data['views']
                progress_pct = (views['current'] / views['total'] * 100) if views['total'] > 0 else 0
                views_info = f"\n   📈 Progress: {views['current']:,}/{views['total']:,} ({progress_pct:.1f}%)"
            
            status_msg += f"{position} {name}\n"
            status_msg += f"   💰 Bid: {data['my_bid']} | Top: {data.get('top_bid', 'N/A')} | {status}{views_info}\n\n"

        status_msg += f"🎯 Activity Pulses: {self.performance_stats['activity_pulses']}"
        if self.performance_stats['last_restore_time']:
            status_msg += f"\n🔄 Last Restore: {self.performance_stats['last_restore_time'][11:19]}"
        status_msg += "\n\n🤖 Bot is actively monitoring..."
        self.send_telegram(status_msg)

    def send_campaigns_list(self):
        if not self.campaigns:
            self.send_telegram("📊 No campaigns found yet. The bot is monitoring adsha.re for campaigns...")
            return
        
        campaigns_text = "📋 YOUR CAMPAIGNS\n\n"
        
        for name, data in self.campaigns.items():
            auto_status = "✅ AUTO" if data.get('auto_bid', False) else "❌ MANUAL"
            position = "🏆 #1" if data.get('my_bid', 0) >= data.get('top_bid', 0) else "📉 #2+"
            
            campaigns_text += f"{position} <b>{name}</b>\n"
            campaigns_text += f"   💰 Your Bid: {data['my_bid']} | Top Bid: {data.get('top_bid', 'N/A')} | {auto_status}\n"
            
            if 'views' in data:
                views = data['views']
                progress_pct = (views['current'] / views['total'] * 100) if views['total'] > 0 else 0
                campaigns_text += f"   📈 Progress: {views['current']:,}/{views['total']:,} ({progress_pct:.1f}%)\n"
            
            campaigns_text += "\n"
        
        campaigns_text += "💡 Use /auto [campaign] on/off to control auto-bidding"
        self.send_telegram(campaigns_text)

    def send_performance_stats(self):
        stats = self.performance_stats
        
        stats_msg = f"""
📈 PERFORMANCE ANALYTICS

👀 VIEWS TRACKING:
Total Views Tracked: {stats['total_views_tracked']:,}
Activity Pulses: {stats['activity_pulses']}
Total Bid Changes: {stats['total_bid_changes']}

📊 PEAK HOURS ANALYSIS:
"""
        
        if stats['peak_hours']:
            peak_avgs = {}
            for hour, views_list in stats['peak_hours'].items():
                peak_avgs[hour] = sum(views_list) / len(views_list)
            
            top_peak_hours = sorted(peak_avgs.items(), key=lambda x: x[1], reverse=True)[:3]
            stats_msg += "🏆 Best #1 Position Hours:\n"
            for hour, avg_views in top_peak_hours:
                stats_msg += f"   {hour:02d}:00 - {avg_views:.1f} views/hour\n"
        
        if stats['off_peak_hours']:
            off_peak_avgs = {}
            for hour, views_list in stats['off_peak_hours'].items():
                off_peak_avgs[hour] = sum(views_list) / len(views_list)
            
            bottom_off_peak = sorted(off_peak_avgs.items(), key=lambda x: x[1])[:3]
            stats_msg += "\n📉 Worst #2+ Position Hours:\n"
            for hour, avg_views in bottom_off_peak:
                stats_msg += f"   {hour:02d}:00 - {avg_views:.1f} views/hour\n"
        
        if stats['last_restore_time']:
            stats_msg += f"\n🔄 Last State Restore: {stats['last_restore_time']}"
        
        self.send_telegram(stats_msg)

    def send_credit_status(self):
        traffic_credits = self.get_traffic_credits()
        visitor_credits = self.get_visitor_credits()
        
        credit_msg = f"""
💰 CREDIT MANAGEMENT

Traffic Credits: {traffic_credits}
Visitor Credits: {visitor_credits:,}
"""
        
        if traffic_credits >= 1000:
            credit_msg += "\n💡 RECOMMENDATION: Convert traffic credits to visitors!\n"
        
        if visitor_credits < 1000:
            credit_msg += "⚠️ WARNING: Visitor credits getting low.\n"
        
        if visitor_credits < 500:
            credit_msg += "🛑 CRITICAL: Very low visitors. Auto-bid will stop soon.\n"
        
        credit_msg += f"\nAuto-bid status: {'✅ ACTIVE' if self.is_monitoring else '❌ PAUSED'}"
        
        self.send_telegram(credit_msg)

    def send_enhanced_help(self):
        help_msg = """
🤖 ULTIMATE SMART BIDDER - ENHANCED

📋 AVAILABLE COMMANDS:

/start - Start 24/7 monitoring
/stop - Stop monitoring  
/status - Enhanced status with analytics
/campaigns - List all campaigns with details
/stats - Performance analytics & peak hours
/credits - Credit management overview
/backup - Manual state backup
/restore - Restore from backup

⚙️ AUTO-BID CONTROL:
/auto all on/off - Toggle all campaigns
/auto [campaign] on/off - Toggle specific campaign

🎯 ENHANCED FEATURES:
• 24/7 monitoring with anti-sleep
• Auto state backup & restore
• Peak hours analysis (#1 vs #2+ performance)
• Automatic bid change alerts
• Campaign completion alerts
• Credit protection systems
• Live configuration via environment variables

💡 TIP: Use /stats to see when you get most views!
"""
        self.send_telegram(help_msg)

    def parse_campaigns(self, html_content):
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            new_campaigns = {}
            
            campaign_divs = soup.find_all('div', style=re.compile(r'border.*solid.*#8CC63F'))
            
            for div in campaign_divs:
                campaign_name = ""
                for element in div.contents:
                    if isinstance(element, str) and element.strip():
                        campaign_name = element.strip()
                        break
                    elif element.name == 'br':
                        break
                
                if 'http' in campaign_name:
                    campaign_name = campaign_name.split('http')[0].strip()
                campaign_name = campaign_name.rstrip('.:- ')
                
                if not campaign_name:
                    continue
                
                text_content = div.get_text()
                
                bid_match = re.search(r'Campaign Bid:\s*(\d+)', text_content)
                my_bid = int(bid_match.group(1)) if bid_match else 0
                
                views_match = re.search(r'(\d+)\s*/\s*(\d+)\s*visitors', text_content)
                hits_match = re.search(r'(\d+)\s*hits', text_content)
                
                current_views = int(views_match.group(1)) if views_match else 0
                total_views = int(views_match.group(2)) if views_match else 0
                total_hits = int(hits_match.group(1)) if hits_match else 0
                
                if campaign_name and my_bid > 0:
                    auto_bid = False
                    if campaign_name in self.campaigns:
                        auto_bid = self.campaigns[campaign_name].get('auto_bid', False)
                    
                    new_campaigns[campaign_name] = {
                        'my_bid': my_bid,
                        'top_bid': my_bid,
                        'auto_bid': auto_bid,
                        'last_bid_time': None,
                        'last_checked': None,
                        'views': {
                            'current': current_views,
                            'total': total_views,
                            'hits': total_hits
                        }
                    }
            
            return new_campaigns
        except Exception as e:
            logger.error(f"PARSE_CAMPAIGNS_ERROR - {e}")
            return {}

    def get_top_bid_from_bid_page(self, campaign_name):
        try:
            adverts_url = "https://adsha.re/adverts"
            response = self.session.get(adverts_url, timeout=30)
            self.human_delay(1, 2)
            
            soup = BeautifulSoup(response.content, 'html.parser')
            increase_links = soup.find_all('a', href=re.compile(r'/adverts/bid/'))
            
            for link in increase_links:
                campaign_div = link.find_parent('div', style=re.compile(r'border.*solid.*#8CC63F'))
                if campaign_div and campaign_name in campaign_div.get_text():
                    bid_url = link['href']
                    if not bid_url.startswith('http'):
                        bid_url = f"https://adsha.re{bid_url}"
                    
                    response = self.session.get(bid_url, timeout=30)
                    self.human_delay(1, 2)
                    
                    soup = BeautifulSoup(response.content, 'html.parser')
                    top_bid_text = soup.get_text()
                    top_bid_match = re.search(r'top bid is (\d+) credits', top_bid_text)
                    
                    if top_bid_match:
                        return int(top_bid_match.group(1))
            return None
        except Exception as e:
            logger.error(f"GET_TOP_BID_ERROR - {e}")
            return None

    def calculate_minimal_bid(self, current_top_bid):
        new_bid = current_top_bid + random.choice(self.minimal_bid_weights)
        
        if new_bid > self.max_bid_limit:
            self.send_telegram(f"🛑 MAX BID LIMIT: Would bid {new_bid} but max is {self.max_bid_limit}!")
            return None
        
        return new_bid

    def track_competitor_activity(self, campaign_name, old_top_bid, new_top_bid, current_time):
        """Track competitor bidding patterns"""
        if campaign_name not in self.competitor_activity:
            self.competitor_activity[campaign_name] = {
                'bid_changes': [],
                'last_bid_time': None
            }
        
        activity = self.competitor_activity[campaign_name]
        
        # Track bid changes
        if old_top_bid != new_top_bid:
            activity['bid_changes'].append({
                'time': current_time,
                'old_bid': old_top_bid,
                'new_bid': new_top_bid,
                'change': new_top_bid - old_top_bid
            })
            
            # Keep only last 50 changes
            activity['bid_changes'] = activity['bid_changes'][-50:]
            
            # Update last bid time
            activity['last_bid_time'] = current_time
            
            # Track in performance stats
            self.performance_stats['total_bid_changes'] += 1

    def check_completion_alerts(self, campaign_name, campaign_data):
        if 'views' not in campaign_data:
            return
            
        current = campaign_data['views']['current']
        total = campaign_data['views']['total']
        
        if total == 0:
            return
            
        completion_ratio = current / total
        alert_key = f"{campaign_name}_{int(completion_ratio * 100)}"
        
        if completion_ratio >= 0.5 and completion_ratio < 0.75:
            if alert_key not in self.sent_alerts:
                self.send_telegram(f"📊 Campaign Progress:\n\"{campaign_name}\" - {current:,}/{total:,} views (50%)\n✅ Halfway there!")
                self.sent_alerts[alert_key] = True
                logger.warning(f"PROGRESS_ALERT - {campaign_name} | 50% complete")
        
        elif completion_ratio >= 0.75 and completion_ratio < 0.98:
            if alert_key not in self.sent_alerts:
                self.send_telegram(f"📊 Campaign Progress:\n\"{campaign_name}\" - {current:,}/{total:,} views (75%)\n⚠️ Almost done!")
                self.sent_alerts[alert_key] = True
                logger.warning(f"PROGRESS_ALERT - {campaign_name} | 75% complete")
        
        elif completion_ratio >= 0.98 and completion_ratio < 1.0:
            if alert_key not in self.sent_alerts:
                self.send_telegram(f"📊 Campaign Progress:\n\"{campaign_name}\" - {current:,}/{total:,} views (98%)\n🎯 EXTEND SOON - Campaign almost complete!")
                self.sent_alerts[alert_key] = True
                logger.warning(f"PROGRESS_ALERT - {campaign_name} | 98% complete")
        
        elif completion_ratio >= 1.0:
            if alert_key not in self.sent_alerts:
                self.send_telegram(f"✅ Campaign Completed:\n\"{campaign_name}\" - {current:,}/{total:,} views (100%)\n🚨 EXTEND NOW - Bid reset to 0!")
                self.sent_alerts[alert_key] = True
                logger.warning(f"PROGRESS_ALERT - {campaign_name} | 100% complete")

    def execute_smart_auto_bid(self, campaign_name, campaign_data, current_top_bid):
        try:
            if campaign_data['my_bid'] >= current_top_bid:
                return
            
            # Rate limiting check
            current_time = time.time()
            last_bid = self.last_bid_time.get(campaign_name, 0)
            if current_time - last_bid < self.bid_cooldown:
                logger.info(f"RATE_LIMITED - {campaign_name} | Cooldown active")
                return
            
            old_bid = campaign_data['my_bid']
            new_bid = self.calculate_minimal_bid(current_top_bid)
            
            if new_bid is None:
                return
                
            if new_bid <= old_bid:
                return
            
            adverts_url = "https://adsha.re/adverts"
            response = self.session.get(adverts_url, timeout=30)
            self.human_delay(1, 2)
            
            soup = BeautifulSoup(response.content, 'html.parser')
            increase_links = soup.find_all('a', href=re.compile(r'/adverts/bid/'))
            bid_url = None
            
            for link in increase_links:
                campaign_div = link.find_parent('div', style=re.compile(r'border.*solid.*#8CC63F'))
                if campaign_div and campaign_name in campaign_div.get_text():
                    bid_url = link['href']
                    if not bid_url.startswith('http'):
                        bid_url = f"https://adsha.re{bid_url}"
                    break
            
            if not bid_url:
                return
            
            response = self.session.get(bid_url, timeout=30)
            self.human_delay(1, 2)
            
            soup = BeautifulSoup(response.content, 'html.parser')
            form = soup.find('form', {'name': 'bid'})
            
            if not form:
                return
            
            action = form.get('action', '')
            if not action.startswith('http'):
                action = f"https://adsha.re{action}"
            
            bid_data = {'bid': str(new_bid), 'vis': '0'}
            self.human_delay(2, 4)
            
            response = self.session.post(action, data=bid_data, allow_redirects=True)
            
            if response.status_code == 200:
                campaign_data['my_bid'] = new_bid
                campaign_data['last_bid_time'] = datetime.now()
                self.last_bid_time[campaign_name] = time.time()
                
                logger.info(f"AUTO_BID_SUCCESS - {campaign_name} | {old_bid} → {new_bid} | Regained #1")
                
                success_msg = f"""
🚀 AUTO-BID SUCCESS!

📊 Campaign: {campaign_name}
🎯 Bid: {old_bid} → {new_bid} credits
📈 Increase: +{new_bid - old_bid} credits
🏆 Position: #1 Achieved!
"""
                self.send_telegram(success_msg)
                
        except Exception as e:
            logger.error(f"AUTO_BID_ERROR - {campaign_name} | {e}")

    def check_all_campaigns(self):
        if not self.is_monitoring:
            return
        
        if not self.smart_login():
            logger.error("CAMPAIGN_CHECK_FAILED - Cannot check campaigns - login failed")
            return
        
        try:
            adverts_url = "https://adsha.re/adverts"
            response = self.session.get(adverts_url, timeout=30)
            self.human_delay(1, 2)
            
            new_campaigns_data = self.parse_campaigns(response.content)
            
            # Track bid changes even with no campaigns
            if not self.campaigns and new_campaigns_data:
                logger.info(f"NEW_CAMPAIGNS_DETECTED - Found {len(new_campaigns_data)} campaigns")
            
            for campaign_name, new_data in new_campaigns_data.items():
                if campaign_name in self.campaigns:
                    auto_bid = self.campaigns[campaign_name].get('auto_bid', False)
                    old_top_bid = self.campaigns[campaign_name].get('top_bid', 0)
                    
                    self.campaigns[campaign_name].update(new_data)
                    self.campaigns[campaign_name]['auto_bid'] = auto_bid
                    
                    # Check for bid changes
                    new_top_bid = new_data.get('top_bid', 0)
                    if old_top_bid > 0 and old_top_bid != new_top_bid:
                        self.track_competitor_activity(campaign_name, old_top_bid, new_top_bid, datetime.now())
                        
                        if new_top_bid < old_top_bid:
                            self.send_telegram(f"🔔 BID DECREASE:\n\"{campaign_name}\" - Top bid dropped from {old_top_bid} to {new_top_bid}!")
                            logger.warning(f"BID_CHANGE - {campaign_name} | {old_top_bid} → {new_top_bid} | Decrease")
                        elif new_top_bid > old_top_bid:
                            self.send_telegram(f"📈 BID INCREASE:\n\"{campaign_name}\" - Top bid rose from {old_top_bid} to {new_top_bid}!")
                            logger.warning(f"BID_CHANGE - {campaign_name} | {old_top_bid} → {new_top_bid} | Increase")
                else:
                    self.campaigns[campaign_name] = new_data
            
            if not self.campaigns:
                logger.info("NO_CAMPAIGNS - No campaigns found")
                return
            
            credit_safe = self.check_credit_safety()
            current_time = datetime.now()
            
            for campaign_name, campaign_data in self.campaigns.items():
                top_bid = self.get_top_bid_from_bid_page(campaign_name)
                
                if top_bid:
                    old_top_bid = campaign_data.get('top_bid', 0)
                    campaign_data['top_bid'] = top_bid
                    campaign_data['last_checked'] = current_time
                    
                    # Update position
                    position = 1 if campaign_data['my_bid'] >= top_bid else 2
                    campaign_data['position'] = position
                    
                    # Check completion alerts
                    self.check_completion_alerts(campaign_name, campaign_data)
                    
                    logger.info(f"CAMPAIGN_CHECK - {campaign_name} | Your: {campaign_data['my_bid']} | Top: {top_bid} | Position: #{position}")
                    
                    if credit_safe and campaign_data['auto_bid']:
                        self.execute_smart_auto_bid(campaign_name, campaign_data, top_bid)
            
            self.log_activity_pulse()
            self.save_bot_state()
                        
        except Exception as e:
            logger.error(f"CHECK_ALL_CAMPAIGNS_ERROR - {e}")

    def send_hourly_status(self):
        """Send automatic hourly status report"""
        if not self.campaigns:
            return
            
        traffic_credits = self.get_traffic_credits()
        visitor_credits = self.get_visitor_credits()
        
        status_msg = f"""
🕐 HOURLY STATUS REPORT

💰 CREDITS:
Traffic: {traffic_credits}
Visitors: {visitor_credits:,}

📊 CAMPAIGNS:
"""
        
        for name, data in self.campaigns.items():
            if 'views' in data:
                views = data['views']
                progress_pct = (views['current'] / views['total'] * 100) if views['total'] > 0 else 0
                position = "🏆 #1" if data.get('my_bid', 0) >= data.get('top_bid', 0) else "📉 #2+"
                status_msg += f"{position} \"{name}\" - {views['current']:,}/{views['total']:,} views ({progress_pct:.1f}%)\n"
        
        status_msg += f"\n🎯 Activity Pulses: {self.performance_stats['activity_pulses']}"
        if self.performance_stats['last_restore_time']:
            status_msg += f"\n🔄 Last Restore: {self.performance_stats['last_restore_time'][11:19]}"
        status_msg += "\n\n🤖 Bot is actively monitoring..."
        
        self.send_telegram(status_msg)
        logger.info("HOURLY_STATUS_SENT - Automatic report delivered")

    def track_views_performance(self):
        """Track views per hour based on position"""
        current_time = time.time()
        if current_time - self.last_views_check >= self.views_check_interval:
            self.calculate_hourly_views()
            self.last_views_check = current_time

    def calculate_hourly_views(self):
        """Calculate views gained in the last hour for each campaign"""
        current_hour = datetime.now().hour
        
        for campaign_name, campaign_data in self.campaigns.items():
            if 'views' not in campaign_data:
                continue
                
            current_views = campaign_data['views']['current']
            position = 1 if campaign_data.get('my_bid', 0) >= campaign_data.get('top_bid', 0) else 2
            
            if campaign_name not in self.performance_stats['last_views_snapshot']:
                self.performance_stats['last_views_snapshot'][campaign_name] = current_views
                continue
            
            last_views = self.performance_stats['last_views_snapshot'][campaign_name]
            views_change = current_views - last_views
            
            if views_change > 0:
                if position == 1:
                    if current_hour not in self.performance_stats['peak_hours']:
                        self.performance_stats['peak_hours'][current_hour] = []
                    self.performance_stats['peak_hours'][current_hour].append(views_change)
                else:
                    if current_hour not in self.performance_stats['off_peak_hours']:
                        self.performance_stats['off_peak_hours'][current_hour] = []
                    self.performance_stats['off_peak_hours'][current_hour].append(views_change)
                
                logger.info(f"VIEWS_TRACKED - {campaign_name} | +{views_change} views | Position: #{position}")
                self.performance_stats['total_views_tracked'] += views_change
            
            self.performance_stats['last_views_snapshot'][campaign_name] = current_views

    def run(self):
        logger.info("BOT_INITIALIZING - Starting Ultimate Smart Bidder...")
        
        if not self.force_login():
            logger.error("BOT_START_FAILED - Initial login failed")
            return
        
        self.send_telegram("🚀 Ultimate Smart Bidder ACTIVATED!\nType /help for commands")
        logger.info("BOT_STARTED - 24/7 monitoring activated")
        
        last_command_check = 0
        last_campaign_check = 0
        last_save_time = time.time()
        last_hourly_status = time.time()
        last_health_check = time.time()
        last_activity_pulse = time.time()
        
        while True:
            try:
                current_time = time.time()
                
                # ✅ ACTIVITY PULSE (every 2 minutes)
                if current_time - last_activity_pulse >= 120:
                    self.log_activity_pulse()
                    last_activity_pulse = current_time
                
                # Process Telegram commands every 3 seconds
                if current_time - last_command_check >= 3:
                    self.process_telegram_command()
                    last_command_check = current_time
                
                # Hourly status report (every 60 minutes)
                if current_time - last_hourly_status >= 3600:
                    if self.is_monitoring:
                        self.send_hourly_status()
                    last_hourly_status = current_time
                
                # Health check every 15 minutes
                if current_time - last_health_check >= 900:
                    if not self.smart_login():
                        logger.warning("HEALTH_CHECK_FAILED - Attempting re-login")
                        self.force_login()
                    last_health_check = current_time
                
                # Save state every 3 minutes
                if current_time - last_save_time >= 180:
                    self.save_bot_state()
                    last_save_time = current_time
                
                # Campaign checks every 3 minutes
                if self.is_monitoring:
                    if current_time - last_campaign_check >= self.check_interval:
                        self.check_all_campaigns()
                        last_campaign_check = current_time
                        logger.info(f"CHECK_CYCLE_COMPLETE - Next check in {self.check_interval//60}min")
                
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"MAIN_LOOP_ERROR - {e}")
                time.sleep(30)

# Enhanced Flask routes
@app.route('/')
def home():
    bot = getattr(app, 'bot_instance', None)
    status = {
        "status": "active",
        "timestamp": datetime.now().isoformat(),
        "monitoring": bot.is_monitoring if bot else False,
        "campaigns": len(bot.campaigns) if bot else 0,
        "activity_pulses": bot.performance_stats['activity_pulses'] if bot else 0,
        "check_interval": bot.check_interval if bot else 180
    }
    return json.dumps(status, indent=2)

@app.route('/health')
def health():
    return "✅ Bot Healthy - " + datetime.now().strftime("%Y-%m-%d %H:%M:%S")

@app.route('/ping')
def ping():
    return "🏓 PONG - " + datetime.now().strftime("%H:%M:%S")

@app.route('/status')
def status():
    bot = getattr(app, 'bot_instance', None)
    if bot:
        return f"""
🤖 Enhanced Bot Status:
Monitoring: {bot.is_monitoring}
Campaigns: {len(bot.campaigns)}
Activity Pulses: {bot.performance_stats['activity_pulses']}
Check Interval: {bot.check_interval}s
Last Update: {datetime.now().strftime('%H:%M:%S')}
"""
    return "🤖 Bot instance not found"

@app.route('/alive')
def alive():
    return "💚 Instance Active - " + datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def run_bot():
    bot = UltimateSmartBidder()
    app.bot_instance = bot
    bot.run()

if __name__ == "__main__":
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    port = int(os.environ.get('PORT', 10002))
    app.run(host='0.0.0.0', port=port, debug=False)