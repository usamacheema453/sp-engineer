#!/bin/bash
# setup_5min_cron.sh - Setup 5-minute renewal cron job

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${GREEN}🚀 Setting up 5-Minute Renewal Cron Job${NC}"
echo -e "${YELLOW}⚠️  This is for TESTING/DEVELOPMENT only!${NC}"

# Get project details
PROJECT_ROOT=$(pwd)
PYTHON_PATH=$(which python3 || which python)
LOG_DIR="$PROJECT_ROOT/logs"

echo -e "\n${BLUE}📍 Project Setup:${NC}"
echo -e "Project Root: ${YELLOW}$PROJECT_ROOT${NC}"
echo -e "Python Path: ${YELLOW}$PYTHON_PATH${NC}"
echo -e "Log Directory: ${YELLOW}$LOG_DIR${NC}"

# Verify requirements
if [ ! -f "$PYTHON_PATH" ]; then
    echo -e "${RED}❌ Python not found. Please install Python 3.7+${NC}"
    exit 1
fi

# Create logs directory
mkdir -p "$LOG_DIR"
echo -e "${GREEN}✅ Logs directory created${NC}"

# Test Python imports
echo -e "\n${BLUE}🧪 Testing Python imports...${NC}"
$PYTHON_PATH -c "
try:
    from app.utils.renewal_service_5min import run_5_minute_renewal_service
    print('✅ Import successful')
except ImportError as e:
    print(f'❌ Import failed: {e}')
    exit(1)
except Exception as e:
    print(f'❌ Error: {e}')
    exit(1)
" || {
    echo -e "${RED}❌ Python import test failed. Check your environment.${NC}"
    exit 1
}

# Create cron job command
CRON_COMMAND="cd $PROJECT_ROOT && $PYTHON_PATH -c \"from app.utils.renewal_service_5min import run_5_minute_renewal_service; run_5_minute_renewal_service()\" >> $LOG_DIR/renewal_5min.log 2>&1"

# 5-minute cron job
FIVE_MIN_CRON="*/5 * * * * $CRON_COMMAND"

echo -e "\n${BLUE}📋 Cron Job Details:${NC}"
echo -e "Schedule: ${YELLOW}Every 5 minutes (*/5 * * * *)${NC}"
echo -e "Command: ${YELLOW}$CRON_COMMAND${NC}"
echo -e "Log File: ${YELLOW}$LOG_DIR/renewal_5min.log${NC}"

echo -e "\n${GREEN}🎯 Setup Options:${NC}"
echo "1. Install 5-minute cron job"
echo "2. Test renewal service manually"
echo "3. View current cron jobs"
echo "4. Remove existing renewal cron jobs"
echo "5. Monitor logs in real-time"
echo "6. Exit"

read -p "Choose option (1-6): " choice

case $choice in
    1)
        echo -e "\n${YELLOW}⏰ Installing 5-minute cron job...${NC}"
        
        # Remove existing renewal crons
        crontab -l 2>/dev/null | grep -v "renewal_service" | crontab -
        
        # Add new 5-minute cron
        (crontab -l 2>/dev/null; echo "$FIVE_MIN_CRON") | crontab -
        
        echo -e "${GREEN}✅ 5-minute cron job installed successfully!${NC}"
        echo -e "\n${BLUE}📊 Verification:${NC}"
        crontab -l | grep renewal
        
        echo -e "\n${GREEN}🎉 Setup Complete!${NC}"
        echo -e "${YELLOW}📈 Your renewal service will run every 5 minutes${NC}"
        echo -e "${YELLOW}📝 Monitor logs: tail -f $LOG_DIR/renewal_5min.log${NC}"
        echo -e "${YELLOW}⏰ First run in maximum 5 minutes${NC}"
        ;;
        
    2)
        echo -e "\n${YELLOW}🧪 Testing renewal service manually...${NC}"
        $PYTHON_PATH -c "from app.utils.renewal_service_5min import run_5_minute_renewal_service; run_5_minute_renewal_service()"
        echo -e "${GREEN}✅ Manual test completed${NC}"
        ;;
        
    3)
        echo -e "\n${BLUE}📋 Current cron jobs:${NC}"
        crontab -l 2>/dev/null | grep -n ".*" || echo "No cron jobs found"
        echo -e "\n${BLUE}📋 Renewal-related cron jobs:${NC}"
        crontab -l 2>/dev/null | grep renewal || echo "No renewal cron jobs found"
        ;;
        
    4)
        echo -e "\n${YELLOW}🗑️ Removing existing renewal cron jobs...${NC}"
        crontab -l 2>/dev/null | grep -v "renewal_service" | crontab -
        echo -e "${GREEN}✅ Renewal cron jobs removed!${NC}"
        ;;
        
    5)
        echo -e "\n${BLUE}📊 Monitoring logs in real-time...${NC}"
        echo -e "${YELLOW}Press Ctrl+C to stop monitoring${NC}"
        touch "$LOG_DIR/renewal_5min.log"
        tail -f "$LOG_DIR/renewal_5min.log"
        ;;
        
    6)
        echo -e "${GREEN}👋 Goodbye!${NC}"
        exit 0
        ;;
        
    *)
        echo -e "${RED}❌ Invalid option${NC}"
        exit 1
        ;;
esac

echo -e "\n${GREEN}📋 Next Steps:${NC}"
echo -e "1. Monitor logs: ${YELLOW}tail -f $LOG_DIR/renewal_5min.log${NC}"
echo -e "2. Check cron status: ${YELLOW}crontab -l | grep renewal${NC}"
echo -e "3. Test manually: ${YELLOW}$PYTHON_PATH -c \"from app.utils.renewal_service_5min import run_5_minute_renewal_service; run_5_minute_renewal_service()\"${NC}"
echo -e "4. Remove later: ${YELLOW}crontab -l | grep -v renewal_service | crontab -${NC}"

echo -e "\n${YELLOW}⚠️  Remember: This runs every 5 minutes!${NC}"
echo -e "${YELLOW}⚠️  For production, use daily schedule instead${NC}"