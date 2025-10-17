import requests
from bs4 import BeautifulSoup
import time
import re
import logging
import random
from datetime import datetime
import os

# Standard logging setup (Simplified: Removed EnhancedFormatter)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger()

class UltimateSmartBidder:
    def __init__(self):
        # ✅ Core settings from environment variables (Keep)
        self.bot_token = os.environ.get('BOT_TOKEN', "8439342017:AAEmRrBp-AKzVK6cbRdHekDGSpbgi7aH5Nc")
        self.chat_id = os.environ.get('CHAT_ID', "2052085789")
        self.email = os.environ.get('EMAIL', "loginallapps@gmail.com")
        self.password = os.environ.get('PASSWORD', "@Sd2007123")
        self.last_update_id = 0
        
        self.session = requests.Session()
        self.rotate_user_agent()
        self.session_valid = False
        
        self.is_monitoring = False
        # State is not persistent, so campaigns start fresh
        self.campaigns = {} 
        self.last_bid_time = {} # For rate-limiting bids
        
        # ✅ Configurable bidding parameters (Keep)
        self.minimal_bid_weights = [1, 2]
        self.check_interval = int(os.environ.get('CHECK_INTERVAL', '180'))
        self.max_bid_limit = int(os.environ.get('MAX_BID_LIMIT', '369'))
        self.bid_cooldown = 60 # Cooldown in seconds between bids
        
        # ✅ Credit Protection Settings (Feature 5 - Keep)
        self.visitor_alert_threshold = int(os.environ.get('VISITOR_ALERT_THRESHOLD', '1000'))
        self.visitor_stop_threshold = int(os.environ.get('VISITOR_STOP_THRESHOLD', '500'))
        self.current_traffic_credits = 0
        self.current_visitor_credits = 0
        self.last_credit_alert = None
        
        logger.info(f"BOT_INITIALIZED - Check interval: {self.check_interval}s, Max bid: {self.max_bid_limit}")

    # --- Utilities (Keep) ---
    def rotate_user_agent(self):
        user_agents = ['Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36']
        self.session.headers.update({'User-Agent': random.choice(user_agents)})

    def human_delay(self, min_seconds=2, max_seconds=5):
        time.sleep(random.uniform(min_seconds, max_seconds))

    # --- Login & Session (Keep) ---
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
            
            password_field = next((field.get('name') for field in form.find_all('input') if field.get('value') == 'Password' and field.get('name')), None)
            
            if not password_field:
                logger.error("LOGIN_FAILED - Password field not found")
                return False
            
            login_data = {'mail': self.email, password_field: self.password}
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

    # --- Credit Protection (Feature 5 - Keep) ---
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

    # --- Telegram Communication & Commands (Feature 7 - Keep) ---
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
        elif command_lower == '/credits':
            self.send_credit_status()
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
            
        # Simplified auto-handling since no state saving is used.
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
            
            found_campaign = next((name for name in self.campaigns if name.lower() == campaign_name.lower()), None)
            
            if found_campaign:
                self.toggle_auto_bid(found_campaign, action == 'on')
            else:
                self.send_telegram(f"❌ Campaign '{campaign_name}' not found.")

    def toggle_auto_bid(self, campaign_name, enable):
        if campaign_name in self.campaigns:
            self.campaigns[campaign_name]['auto_bid'] = enable
            status = "enabled" if enable else "disabled"
            self.send_telegram(f"🔄 Auto-bid {status} for '{campaign_name}' (Note: Setting will be lost on restart)")
            logger.info(f"AUTO_BID_TOGGLE - {campaign_name} | {status}")

    def toggle_all_auto_bid(self, enable):
        for campaign_name in self.campaigns:
            self.campaigns[campaign_name]['auto_bid'] = enable
        
        status = "enabled" if enable else "disabled"
        self.send_telegram(f"🔄 Auto-bid {status} for all campaigns (Note: Settings will be lost on restart)")
        logger.info(f"AUTO_BID_ALL_TOGGLE - All campaigns | {status}")

    def start_monitoring(self):
        self.is_monitoring = True
        logger.info("BOT_STARTED - Monitoring activated")
        self.send_telegram("🚀 Smart Bidder ACTIVATED!\nMonitoring all campaigns...")
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
📊 STATUS REPORT

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
            
            status_msg += f"{position} <b>{name}</b>\n"
            status_msg += f"   💰 Bid: {data['my_bid']} | Top: {data.get('top_bid', 'N/A')} | {status}{views_info}\n\n"

        status_msg += "🤖 Bot is actively monitoring..."
        self.send_telegram(status_msg)

    def send_campaigns_list(self):
        if not self.campaigns:
            self.send_telegram("📊 No campaigns found yet.")
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
        
        if visitor_credits < self.visitor_alert_threshold:
            credit_msg += "⚠️ WARNING: Visitor credits getting low.\n"
        
        if visitor_credits < self.visitor_stop_threshold:
            credit_msg += "🛑 CRITICAL: Very low visitors. Auto-bid will stop soon.\n"
        
        credit_msg += f"\nAuto-bid status: {'✅ ACTIVE' if self.is_monitoring else '❌ PAUSED'}"
        
        self.send_telegram(credit_msg)

    def send_enhanced_help(self):
        help_msg = """
🤖 SMART BIDDER - HELP

/start - Start monitoring
/stop - Stop monitoring  
/status - Get current status
/campaigns - List all campaigns
/credits - Credit management overview
/help - Show this message

⚙️ AUTO-BID CONTROL:
/auto all on/off - Toggle all campaigns
/auto [campaign] on/off - Toggle specific campaign

⚠️ NOTE: Since you disabled state saving, campaign settings (like auto-bid status) will be lost on bot restart/redeploy.
"""
        self.send_telegram(help_msg)

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
        
        status_msg += "\n🤖 Bot is actively monitoring..."
        
        self.send_telegram(status_msg)
        logger.info("HOURLY_STATUS_SENT - Automatic report delivered")

    # --- Campaign Logic (Feature 1 - Keep) ---
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
                
                if not campaign_name: continue
                
                text_content = div.get_text()
                bid_match = re.search(r'Campaign Bid:\s*(\d+)', text_content)
                my_bid = int(bid_match.group(1)) if bid_match else 0
                
                views_match = re.search(r'(\d+)\s*/\s*(\d+)\s*visitors', text_content)
                
                current_views = int(views_match.group(1)) if views_match else 0
                total_views = int(views_match.group(2)) if views_match else 0
                
                if campaign_name and my_bid > 0:
                    # Auto-bid status is not loaded, defaults to False or inherited if running
                    auto_bid = self.campaigns.get(campaign_name, {}).get('auto_bid', False)
                    
                    new_campaigns[campaign_name] = {
                        'my_bid': my_bid,
                        'top_bid': my_bid,
                        'auto_bid': auto_bid,
                        'views': {'current': current_views, 'total': total_views}
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
        
        # Max Bid Limit Alert (Feature 3 - Keep)
        if new_bid > self.max_bid_limit:
            self.send_telegram(f"🛑 MAX BID LIMIT: Would bid {new_bid} but max is {self.max_bid_limit}!")
            return None
        
        return new_bid

    def execute_smart_auto_bid(self, campaign_name, campaign_data, current_top_bid):
        try:
            if campaign_data['my_bid'] >= current_top_bid:
                return
            
            # Bid Cooldown / Rate Limiting (Feature 1 - Keep)
            current_time = time.time()
            last_bid = self.last_bid_time.get(campaign_name, 0)
            if current_time - last_bid < self.bid_cooldown:
                logger.info(f"RATE_LIMITED - {campaign_name} | Cooldown active")
                return
            
            old_bid = campaign_data['my_bid']
            new_bid = self.calculate_minimal_bid(current_top_bid)
            
            if new_bid is None or new_bid <= old_bid:
                return
            
            # --- Bid Execution Sequence ---
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
            
            if not bid_url: return
            
            response = self.session.get(bid_url, timeout=30)
            self.human_delay(1, 2)
            
            soup = BeautifulSoup(response.content, 'html.parser')
            form = soup.find('form', {'name': 'bid'})
            if not form: return
            
            action = form.get('action', '')
            if not action.startswith('http'):
                action = f"https://adsha.re{action}"
            
            bid_data = {'bid': str(new_bid), 'vis': '0'}
            self.human_delay(2, 4)
            
            response = self.session.post(action, data=bid_data, allow_redirects=True)
            
            if response.status_code == 200:
                campaign_data['my_bid'] = new_bid
                self.last_bid_time[campaign_name] = time.time()
                
                logger.info(f"AUTO_BID_SUCCESS - {campaign_name} | {old_bid} → {new_bid} | Regained #1")
                
                # Auto-Bid Success Alert (Feature 3 - Keep)
                success_msg = f"""
🚀 AUTO-BID SUCCESS!

📊 Campaign: <b>{campaign_name}</b>
🎯 Bid: {old_bid} → {new_bid} credits
📈 Increase: +{new_bid - old_bid} credits
🏆 Position: #1 Achieved!
"""
                self.send_telegram(success_msg)
                
        except Exception as e:
            logger.error(f"AUTO_BID_ERROR - {campaign_name} | {e}")

    # --- Main Check Loop (Feature 1, 4, 5 - Keep) ---
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
            
            # Update existing campaigns and add new ones
            for campaign_name, new_data in new_campaigns_data.items():
                if campaign_name not in self.campaigns:
                    self.campaigns[campaign_name] = new_data
                else:
                    auto_bid = self.campaigns[campaign_name].get('auto_bid', False)
                    self.campaigns[campaign_name].update(new_data)
                    self.campaigns[campaign_name]['auto_bid'] = auto_bid # Retain current auto_bid status

            # Remove campaigns no longer on the page
            campaigns_to_delete = [name for name in self.campaigns if name not in new_campaigns_data]
            for name in campaigns_to_delete:
                 logger.warning(f"CAMPAIGN_REMOVED - '{name}' not found on page. Removing from tracking.")
                 del self.campaigns[name]
            
            if not self.campaigns:
                logger.info("NO_CAMPAIGNS - No campaigns found")
                return
            
            credit_safe = self.check_credit_safety()
            current_time = datetime.now()
            
            for campaign_name, campaign_data in self.campaigns.items():
                
                # Fetch top bid
                top_bid = self.get_top_bid_from_bid_page(campaign_name)
                
                if top_bid is not None:
                    old_top_bid = campaign_data.get('top_bid', 0)
                    campaign_data['top_bid'] = top_bid
                    campaign_data['last_checked'] = current_time
                    
                    position = 1 if campaign_data['my_bid'] >= top_bid else 2
                    campaign_data['position'] = position
                    
                    # 🔔 BID CHANGE ALERT (Feature 4 - Keep)
                    if old_top_bid > 0 and top_bid != old_top_bid:
                        if top_bid < old_top_bid:
                            self.send_telegram(f"🔔 BID DECREASE:\n\"{campaign_name}\" - Top bid dropped from {old_top_bid} to {top_bid}!")
                        elif top_bid > old_top_bid:
                            self.send_telegram(f"📈 BID INCREASE:\n\"{campaign_name}\" - Top bid rose from {old_top_bid} to {top_bid}!")
                        logger.warning(f"BID_CHANGE - {campaign_name} | {old_top_bid} → {top_bid}")
                    
                    logger.info(f"CAMPAIGN_CHECK - {campaign_name} | Your: {campaign_data['my_bid']} | Top: {top_bid} | Position: #{position}")
                    
                    # Auto Bid Execution (Feature 1)
                    if credit_safe and campaign_data['auto_bid']:
                        self.execute_smart_auto_bid(campaign_name, campaign_data, top_bid)
                        
                else:
                    logger.warning(f"CAMPAIGN_REMOVED - '{campaign_name}' no longer found on bid page. Removing.")
                    del self.campaigns[campaign_name]
                        
        except Exception as e:
            logger.error(f"CHECK_ALL_CAMPAIGNS_ERROR - {e}")

    # --- Main Loop (Simplified) ---
    def run(self):
        logger.info("BOT_STARTING - Initializing Smart Bidder...")
        
        if not self.force_login():
            logger.error("FATAL - Initial login failed. Bot cannot start.")
            return
        
        self.send_telegram("🚀 Smart Bidder is now ONLINE.\nType /help for commands.")
        
        last_command_check = 0
        last_campaign_check = 0
        last_hourly_status = time.time()
        
        while True:
            try:
                current_time = time.time()
                
                # Process Telegram commands every 3 seconds
                if current_time - last_command_check >= 3:
                    self.process_telegram_command()
                    last_command_check = current_time
                
                # Hourly status report (every 60 minutes)
                if current_time - last_hourly_status >= 3600:
                    if self.is_monitoring:
                        self.send_hourly_status()
                    last_hourly_status = current_time
                
                # Campaign checks every check_interval (3 minutes default)
                if self.is_monitoring:
                    if current_time - last_campaign_check >= self.check_interval:
                        self.check_all_campaigns()
                        last_campaign_check = current_time
                        logger.info(f"CHECK_CYCLE_COMPLETE - Next check in {self.check_interval//60}min")
                
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"MAIN_LOOP_ERROR - {e}")
                time.sleep(30)

if __name__ == "__main__":
    bot = UltimateSmartBidder()
    bot.run()
