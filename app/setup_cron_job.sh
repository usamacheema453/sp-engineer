#!/bin/bash
# setup_cron_job.sh - Setup automatic renewal cron job

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Setting up SuperEngineer Renewal Cron Job${NC}"

# Get the current directory (project root)
PROJECT_ROOT=$(pwd)
PYTHON_PATH=$(which python3 || which python)
CRON_SCRIPT="$PROJECT_ROOT/app/services/renewal_service.py"

# Verify Python and script exist
if [ ! -f "$PYTHON_PATH" ]; then
    echo -e "${RED}❌ Python not found. Please install Python 3.7+${NC}"
    exit 1
fi

if [ ! -f "$CRON_SCRIPT" ]; then
    echo -e "${RED}❌ Renewal script not found at: $CRON_SCRIPT${NC}"
    exit 1
fi

# Create log directory
LOG_DIR="$PROJECT_ROOT/logs"
mkdir -p "$LOG_DIR"

echo -e "${YELLOW}📍 Project Root: $PROJECT_ROOT${NC}"
echo -e "${YELLOW}🐍 Python Path: $PYTHON_PATH${NC}"
echo -e "${YELLOW}📜 Script Path: $CRON_SCRIPT${NC}"
echo -e "${YELLOW}📁 Log Directory: $LOG_DIR${NC}"

# Create the cron job command
CRON_COMMAND="cd $PROJECT_ROOT && $PYTHON_PATH -c \"from app.services.renewal_service import run_renewal_service; run_renewal_service()\" >> $LOG_DIR/renewal.log 2>&1"

# Cron job entries
DAILY_CRON="0 2 * * * $CRON_COMMAND"
HOURLY_CRON="0 * * * * $CRON_COMMAND"

echo -e "\n${GREEN}📋 Cron Job Options:${NC}"
echo "1. Daily at 2:00 AM (Recommended)"
echo "2. Every hour"
echo "3. Custom schedule"
echo "4. View current cron jobs"
echo "5. Remove existing renewal cron jobs"

read -p "Choose an option (1-5): " choice

case $choice in
    
        echo -e "\n${YELLOW}⏰ Setting up daily cron job (2:00 AM)...${NC}"
        (crontab -l 2>/dev/null | grep -v "renewal_service"; echo "$DAILY_CRON") | crontab -
        echo -e "${GREEN}✅ Daily cron job added successfully!${NC}"
        ;;
    
        echo -e "\n${YELLOW}⏰ Setting up hourly cron job...${NC}"
        (crontab -l 2>/dev/null | grep -v "renewal_service"; echo "$HOURLY_CRON") | crontab -
        echo -e "${GREEN}✅ Hourly cron job added successfully!${NC}"
        ;;
    
        echo -e "\n${YELLOW}📝 Enter custom cron schedule (e.g., '0 6 * * *' for 6:00 AM daily):${NC}"
        read -p "Cron schedule: " custom_schedule
        CUSTOM_CRON="$custom_schedule $CRON_COMMAND"
        (crontab -l 2>/dev/null | grep -v "renewal_service"; echo "$CUSTOM_CRON") | crontab -
        echo -e "${GREEN}✅ Custom cron job added successfully!${NC}"
        ;;
    
        echo -e "\n${GREEN}📋 Current cron jobs:${NC}"
        crontab -l 2>/dev/null || echo "No cron jobs found"
        ;;
    
        echo -e "\n${YELLOW}🗑️ Removing existing renewal cron jobs...${NC}"
        crontab -l 2>/dev/null | grep -v "renewal_service" | crontab -
        echo -e "${GREEN}✅ Renewal cron jobs removed!${NC}"
        ;;
    
        echo -e "${RED}❌ Invalid option${NC}"
        exit 1
        ;;
esac

if [ $choice -eq 1 ] || [ $choice -eq 2 ] || [ $choice -eq 3 ]; then
    echo -e "\n${GREEN}📊 Cron Job Details:${NC}"
    echo -e "Command: ${YELLOW}$CRON_COMMAND${NC}"
    echo -e "Logs: ${YELLOW}$LOG_DIR/renewal.log${NC}"
    
    echo -e "\n${GREEN}🔧 Additional Setup:${NC}"
    echo "1. Make sure your .env file is properly configured"
    echo "2. Test the renewal service manually first:"
    echo -e "   ${YELLOW}cd $PROJECT_ROOT && python -c \"from app.services.renewal_service import run_renewal_service; run_renewal_service()\"${NC}"
    echo "3. Monitor logs regularly:"
    echo -e "   ${YELLOW}tail -f $LOG_DIR/renewal.log${NC}"
    
    echo -e "\n${GREEN}✅ Cron job setup complete!${NC}"
fi