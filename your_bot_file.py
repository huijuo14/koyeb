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
import socket
import sys

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

app = Flask(__name__)

class UltimateSmartBidder:
    def __init__(self):
        self.bot_token = "8439342017:AAEmRrBp-AKzVK6cbRdHekDGSpbgi7aH5Nc"
        self.chat_id = "2052085789"
        self.last_update_id = 0
        self.email = "loginallapps@gmail.com"
        self.password = "@Sd2007123"
        
        self.session = requests.Session()
        self.rotate_user_agent()
        self.session_valid = False
        
        self.is_monitoring = False
        self.campaigns = {}
        
        self.minimal_bid_weights = [1, 2]  # Only +1 or +2 credits
        self.check_interval = 300  # Fixed 5-minute checks
        self.max_bid_limit = 369  # Your maximum bid limit
        
        self.visitor_alert_threshold = 1000
        self.visitor_stop_threshold = 500
        self.current_traffic_credits = 0
        self.current_visitor_credits = 0
        self.last_credit_alert = None
        
        # Enhanced competitor tracking
        self.competitor_activity = {}
        self.bid_history = {}
        self.competitor_patterns = {}
        
        # Alert tracking
        self.sent_alerts = {}
        
        # Rate limiting
        self.last_bid_time = {}
        self.bid_cooldown = 60  # 1 minute between bids per campaign
        
        # Performance metrics
        self.performance_stats = {
            'total_bids': 0,
            'successful_bids': 0,
            'campaigns_won': 0,
            'credits_saved': 0
        }
        
        self.load_bot_state()

    def save_bot_state(self):
        try:
            state_data = {
                'campaigns': self.campaigns,
                'last_update_id': self.last_update_id,
                'session_valid': self.session_valid,
                'is_monitoring': self.is_monitoring,
                'sent_alerts': self.sent_alerts,
                'competitor_activity': self.competitor_activity,
                'bid_history': self.bid_history,
                'competitor_patterns': self.competitor_patterns,
                'performance_stats': self.performance_stats
            }
            # ✅ FIX: Use /tmp directory which is always writable
            state_file = '/tmp/bot_state.pkl'
            with open(state_file, 'wb') as f:
                pickle.dump(state_data, f)
            logger.info("💾 Bot state saved successfully")
        except Exception as e:
            logger.error(f"Save state error: {e}")

    def load_bot_state(self):
        try:
            # ✅ FIX: Use /tmp directory
            state_file = '/tmp/bot_state.pkl'
            if os.path.exists(state_file):
                with open(state_file, 'rb') as f:
                    state_data = pickle.load(f)
                    self.campaigns = state_data.get('campaigns', {})
                    self.last_update_id = state_data.get('last_update_id', 0)
                    self.session_valid = state_data.get('session_valid', False)
                    self.is_monitoring = state_data.get('is_monitoring', False)
                    self.sent_alerts = state_data.get('sent_alerts', {})
                    self.competitor_activity = state_data.get('competitor_activity', {})
                    self.bid_history = state_data.get('bid_history', {})
                    self.competitor_patterns = state_data.get('competitor_patterns', {})
                    self.performance_stats = state_data.get('performance_stats', self.performance_stats)
                logger.info("📂 Bot state loaded from /tmp/")
        except Exception as e:
            logger.error(f"Load state error: {e}")

    def rotate_user_agent(self):
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        ]
        self.session.headers.update({'User-Agent': random.choice(user_agents)})

    def human_delay(self, min_seconds=2, max_seconds=5):
        delay = random.uniform(min_seconds, max_seconds)
        time.sleep(delay)
        return delay

    def force_login(self):
        try:
            logger.info("🔄 Attempting login...")
            self.human_delay(2, 4)
            
            login_url = "https://adsha.re/login"
            response = self.session.get(login_url, timeout=30)
            self.human_delay(1, 2)
            
            soup = BeautifulSoup(response.content, 'html.parser')
            form = soup.find('form', {'name': 'login'})
            if not form:
                logger.error("❌ Login form not found!")
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
                logger.error("❌ Could not find password field!")
                return False
            
            login_data = {
                'mail': self.email,
                password_field: self.password
            }
            
            response = self.session.post(post_url, data=login_data, allow_redirects=True)
            self.human_delay(1, 2)
            
            if self.check_session_valid():
                self.session_valid = True
                logger.info("✅ Login successful!")
                return True
            return False
        except Exception as e:
            logger.error(f"❌ Login error: {e}")
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
            logger.info("✅ Session still valid")
            self.session_valid = True
            return True
        
        logger.info("🔄 Session expired, re-logging in...")
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
            logger.error(f"Error getting traffic credits: {e}")
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
            logger.error(f"Error getting visitor credits: {e}")
            return 0

    def check_credit_safety(self):
        self.current_traffic_credits = self.get_traffic_credits()
        self.current_visitor_credits = self.get_visitor_credits()
        
        # Auto-conversion suggestion
        if self.current_traffic_credits >= 1000:
            if self.last_credit_alert != 'convert':
                self.send_telegram(f"💰 AUTO-CONVERT SUGGESTION: You have {self.current_traffic_credits} traffic credits - convert to visitors for better ROI!")
                self.last_credit_alert = 'convert'
        
        # Safety checks
        if self.current_visitor_credits < self.visitor_stop_threshold:
            if self.last_credit_alert != 'stop':
                self.send_telegram(f"🛑 CRITICAL: Only {self.current_visitor_credits} visitors left! Auto-bid stopped.")
                self.last_credit_alert = 'stop'
            return False
        elif self.current_visitor_credits < self.visitor_alert_threshold:
            if self.last_credit_alert != 'alert':
                self.send_telegram(f"⚠️ WARNING: Low visitors - {self.current_visitor_credits} left! Consider converting traffic credits.")
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
            logger.error(f"Telegram send error: {e}")
            return False

    def analyze_competitor_patterns(self, campaign_name):
        """Analyze competitor bidding patterns for smart timing"""
        if campaign_name not in self.competitor_activity:
            return None
            
        activity = self.competitor_activity[campaign_name]
        
        if not activity.get('bid_changes'):
            return None
            
        # Analyze most active hours
        active_hours = {}
        for change in activity['bid_changes']:
            hour = change['time'].hour
            active_hours[hour] = active_hours.get(hour, 0) + 1
        
        # Find quiet hours (least competitor activity)
        if active_hours:
            quiet_hours = sorted(active_hours.items(), key=lambda x: x[1])[:3]
            return {
                'most_active_hours': sorted([h for h, count in sorted(active_hours.items(), key=lambda x: x[1], reverse=True)[:3]]),
                'quiet_hours': [h for h, count in quiet_hours],
                'total_bid_changes': len(activity['bid_changes'])
            }
        
        return None

    def get_smart_bid_timing(self, campaign_name):
        """Determine optimal bid timing based on competitor patterns"""
        patterns = self.analyze_competitor_patterns(campaign_name)
        current_hour = datetime.now().hour
        
        if patterns and current_hour in patterns['quiet_hours']:
            return "optimal"  # Competitors are less active
        elif patterns and current_hour in patterns['most_active_hours']:
            return "competitive"  # High competition
        else:
            return "normal"

    def calculate_smart_bid(self, campaign_name, current_top_bid):
        """Enhanced bid calculation with competitor intelligence"""
        base_bid = current_top_bid + random.choice(self.minimal_bid_weights)
        
        # Apply timing strategy
        timing = self.get_smart_bid_timing(campaign_name)
        if timing == "optimal":
            # Be more aggressive in quiet hours
            base_bid += 1
        elif timing == "competitive":
            # Be conservative during high competition
            base_bid = max(base_bid, current_top_bid + 1)
        
        # Max bid protection
        if base_bid > self.max_bid_limit:
            self.send_telegram(f"🛑 MAX BID LIMIT REACHED: Would bid {base_bid} but max is {self.max_bid_limit} for {campaign_name}!")
            return None
        
        return base_bid

    def can_bid(self, campaign_name):
        """Rate limiting check"""
        current_time = time.time()
        last_bid = self.last_bid_time.get(campaign_name, 0)
        
        if current_time - last_bid < self.bid_cooldown:
            return False
        return True

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
            logger.error(f"Telegram command error: {e}")

    def handle_command(self, command, chat_id):
        command_lower = command.lower().strip()
        
        if command_lower == '/start':
            self.start_monitoring()
        elif command_lower == '/stop':
            self.stop_monitoring()
        elif command_lower == '/status':
            self.send_enhanced_status()
        elif command_lower.startswith('/auto'):
            self.handle_auto_command(command)
        elif command_lower == '/stats':
            self.send_performance_stats()
        elif command_lower == '/competitors':
            self.send_competitor_analysis()
        elif command_lower == '/credits':
            self.send_credit_status()
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
            self.save_bot_state()

    def toggle_all_auto_bid(self, enable):
        for campaign_name in self.campaigns:
            self.campaigns[campaign_name]['auto_bid'] = enable
        
        status = "enabled" if enable else "disabled"
        self.send_telegram(f"🔄 Auto-bid {status} for all campaigns")
        self.save_bot_state()

    def start_monitoring(self):
        self.is_monitoring = True
        logger.info("🚀 Smart monitoring started")
        self.send_telegram("🚀 Ultimate Smart Bidder ACTIVATED!\n\nMonitoring all campaigns with enhanced intelligence...")
        self.send_enhanced_status()

    def stop_monitoring(self):
        self.is_monitoring = False
        logger.info("🛑 Monitoring stopped")
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

        status_msg += "🤖 Bot is actively monitoring with smart bidding..."
        self.send_telegram(status_msg)

    def send_performance_stats(self):
        stats = self.performance_stats
        efficiency = (stats['successful_bids'] / stats['total_bids'] * 100) if stats['total_bids'] > 0 else 0
        
        stats_msg = f"""
📈 PERFORMANCE ANALYTICS

🎯 Bidding Stats:
Total Bids: {stats['total_bids']}
Successful: {stats['successful_bids']} ({efficiency:.1f}%)
Campaigns Won: {stats['campaigns_won']}
Credits Saved: {stats['credits_saved']}

💡 Intelligence:
Competitor Patterns: {len(self.competitor_patterns)} campaigns analyzed
Active Tracking: {len(self.competitor_activity)} campaigns
"""
        self.send_telegram(stats_msg)

    def send_competitor_analysis(self):
        if not self.competitor_activity:
            self.send_telegram("🕵️ No competitor data collected yet. Check back after some monitoring.")
            return
        
        analysis_msg = "🕵️ COMPETITOR INTELLIGENCE REPORT\n\n"
        
        for campaign, activity in self.competitor_activity.items():
            patterns = self.analyze_competitor_patterns(campaign)
            
            analysis_msg += f"<b>{campaign}</b>\n"
            
            if patterns:
                analysis_msg += f"✅ Smart Analysis Available\n"
                analysis_msg += f"   Quiet Hours: {', '.join([f'{h}:00' for h in patterns['quiet_hours']])}\n"
                analysis_msg += f"   Active Hours: {', '.join([f'{h}:00' for h in patterns['most_active_hours']])}\n"
            else:
                analysis_msg += f"📊 Collecting Data ({len(activity.get('bid_changes', []))} bid changes observed)\n"
            
            analysis_msg += "\n"
        
        analysis_msg += "💡 Use this data for strategic bidding timing!"
        self.send_telegram(analysis_msg)

    def send_credit_status(self):
        traffic_credits = self.get_traffic_credits()
        visitor_credits = self.get_visitor_credits()
        
        credit_msg = f"""
💰 CREDIT MANAGEMENT

Traffic Credits: {traffic_credits}
Visitor Credits: {visitor_credits:,}

"""
        
        if traffic_credits >= 1000:
            credit_msg += "💡 RECOMMENDATION: Convert traffic credits to visitors for better ROI!\n"
        
        if visitor_credits < 1000:
            credit_msg += "⚠️ WARNING: Visitor credits getting low. Monitor closely.\n"
        
        if visitor_credits < 500:
            credit_msg += "🛑 CRITICAL: Very low visitors. Auto-bid will stop soon.\n"
        
        credit_msg += f"\nAuto-bid status: {'✅ ACTIVE' if self.is_monitoring else '❌ PAUSED'}"
        
        self.send_telegram(credit_msg)

    def send_enhanced_help(self):
        help_msg = """
🤖 ULTIMATE SMART BIDDER - ENHANCED

📋 AVAILABLE COMMANDS:

/start - Start monitoring
/stop - Stop monitoring  
/status - Enhanced status with analytics
/stats - Performance statistics
/credits - Credit management overview
/competitors - Competitor intelligence report

⚙️ AUTO-BID CONTROL:
/auto all on/off - Toggle all campaigns
/auto [campaign] on/off - Toggle specific campaign

🎯 ENHANCED FEATURES:
• Smart competitor pattern analysis
• Optimal bid timing detection
• Performance analytics
• Rate limiting protection
• Session recovery
• Credit auto-management alerts

💡 TIP: Use /competitors to see optimal bidding times!
"""
        self.send_telegram(help_msg)

    # ... (keep all your existing methods like parse_campaigns, get_top_bid_from_bid_page, 
    # track_competitor_activity, check_completion_alerts the same as before)

    def execute_smart_auto_bid(self, campaign_name, campaign_data, current_top_bid):
        try:
            # Rate limiting check
            if not self.can_bid(campaign_name):
                logger.info(f"⏳ Rate limited: {campaign_name}")
                return
            
            if campaign_data['my_bid'] >= current_top_bid:
                return
            
            old_bid = campaign_data['my_bid']
            new_bid = self.calculate_smart_bid(campaign_name, current_top_bid)
            
            if new_bid is None:  # Max bid limit reached
                return
                
            if new_bid <= old_bid:
                return
            
            # Update rate limiting
            self.last_bid_time[campaign_name] = time.time()
            
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
                
                # Update performance stats
                self.performance_stats['total_bids'] += 1
                self.performance_stats['successful_bids'] += 1
                self.performance_stats['credits_saved'] += (new_bid - old_bid)
                
                if new_bid >= current_top_bid:
                    self.performance_stats['campaigns_won'] += 1
                
                logger.info(f"🚀 SMART BID: {campaign_name} {old_bid}→{new_bid}")
                
                success_msg = f"""
🚀 ENHANCED BID SUCCESS!

📊 Campaign: {campaign_name}
🎯 Bid: {old_bid} → {new_bid} credits
📈 Increase: +{new_bid - old_bid} credits
🏆 Position: #1 Achieved!
💡 Strategy: {self.get_smart_bid_timing(campaign_name).title()}
"""
                self.send_telegram(success_msg)
                
        except Exception as e:
            logger.error(f"Bid error: {e}")
            self.performance_stats['total_bids'] += 1

    def check_all_campaigns(self):
        if not self.is_monitoring:
            return
        
        if not self.smart_login():
            logger.error("❌ Cannot check campaigns - login failed")
            return
        
        try:
            adverts_url = "https://adsha.re/adverts"
            response = self.session.get(adverts_url, timeout=30)
            self.human_delay(1, 2)
            
            new_campaigns_data = self.parse_campaigns(response.content)
            
            for campaign_name, new_data in new_campaigns_data.items():
                if campaign_name in self.campaigns:
                    auto_bid = self.campaigns[campaign_name].get('auto_bid', False)
                    self.campaigns[campaign_name].update(new_data)
                    self.campaigns[campaign_name]['auto_bid'] = auto_bid
                else:
                    self.campaigns[campaign_name] = new_data
            
            if not self.campaigns:
                logger.info("📭 No campaigns found")
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
                    campaign_data['position'] = 1 if campaign_data['my_bid'] >= top_bid else 2
                    
                    # Track competitor activity
                    self.track_competitor_activity(campaign_name, old_top_bid, top_bid, current_time)
                    
                    # Update competitor patterns
                    if campaign_name not in self.competitor_patterns:
                        self.competitor_patterns[campaign_name] = self.analyze_competitor_patterns(campaign_name)
                    
                    # Check for bid changes alert
                    if old_top_bid > 0 and old_top_bid != top_bid:
                        if top_bid < old_top_bid:
                            self.send_telegram(f"🔔 BID DECREASE:\n\"{campaign_name}\" - Top bid dropped from {old_top_bid} to {top_bid}!")
                        elif top_bid > old_top_bid:
                            self.send_telegram(f"📈 BID INCREASE:\n\"{campaign_name}\" - Top bid rose from {old_top_bid} to {top_bid}!")
                    
                    # Check completion alerts
                    self.check_completion_alerts(campaign_name, campaign_data)
                    
                    logger.info(f"📊 {campaign_name}: Your {campaign_data['my_bid']}, Top {top_bid}, Position: {campaign_data['position']}")
                    
                    if credit_safe and campaign_data['auto_bid']:
                        self.execute_smart_auto_bid(campaign_name, campaign_data, top_bid)
                        
            self.save_bot_state()
                        
        except Exception as e:
            logger.error(f"Campaign check error: {e}")

    def run(self):
        logger.info("🤖 Starting Enhanced Ultimate Smart Bidder...")
        
        if not self.force_login():
            logger.error("❌ Initial login failed")
            return
        
        self.send_telegram("🚀 ENHANCED Ultimate Smart Bidder ACTIVATED!\nType /help for commands")
        
        last_command_check = 0
        last_campaign_check = 0
        last_save_time = time.time()
        last_hourly_status = time.time()
        last_health_check = time.time()
        
        while True:
            try:
                current_time = time.time()
                
                # Process Telegram commands every 3 seconds
                if current_time - last_command_check >= 3:
                    self.process_telegram_command()
                    last_command_check = current_time
                
                # Health check every 30 minutes
                if current_time - last_health_check >= 1800:
                    if not self.smart_login():
                        logger.warning("🔄 Health check failed, attempting re-login")
                        self.force_login()
                    last_health_check = current_time
                
                # Hourly status report
                if current_time - last_hourly_status >= 3600:
                    if self.is_monitoring:
                        self.send_hourly_status()
                    last_hourly_status = current_time
                
                # Save state every 5 minutes
                if current_time - last_save_time >= 300:
                    self.save_bot_state()
                    last_save_time = current_time
                
                # Campaign checks
                if self.is_monitoring:
                    if current_time - last_campaign_check >= self.check_interval:
                        self.check_all_campaigns()
                        last_campaign_check = current_time
                        logger.info(f"🔄 Enhanced check complete. Next in {self.check_interval//60}min")
                
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Main loop error: {e}")
                time.sleep(30)

@app.route('/')
def home():
    return "🤖 Enhanced Ultimate Smart Bidder - Active"

@app.route('/health')
def health():
    return "✅ Bot Healthy - Enhanced Version"

@app.route('/status')
def status():
    bot = getattr(app, 'bot_instance', None)
    if bot:
        return f"🤖 Enhanced Bot Status: Monitoring={bot.is_monitoring}, Campaigns={len(bot.campaigns)}"
    return "🤖 Bot instance not found"

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