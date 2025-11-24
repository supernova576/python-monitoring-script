import monitoring
import sys
import utils.log as log
import traceback
from sys import exit as adieu

def display_help() -> None:
    help_message = """
    Usage: python monitor.py [options]

    Options:
    --help          Display this help message
    --service       Run service monitoring
    --host          Run host monitoring
    --file          Run file monitoring
    --all           Run all monitoring modules
    """
    print(help_message)

def main():
    logger = log("monitoring.log")
    
    try:
        if len(sys.argv) < 2 or "--help" in sys.argv:
            display_help()
            return
        
        if "--service" in sys.argv or "--all" in sys.argv:
            logger.info("Starting service monitoring...")
            service_monitor = monitoring.serviceMonitoring()
            service_monitor.check_services()
        
        elif "--host" in sys.argv or "--all" in sys.argv:
            logger.info("Starting host monitoring...")
            host_monitor = monitoring.hostMonitoring()
            host_monitor.check_host()

        elif "--file" in sys.argv or "--all" in sys.argv:
            logger.info("Starting file monitoring...")
            file_monitor = monitoring.fileMonitoring()
            file_monitor.check_files()
        
        else:
            logger.error("No valid monitoring option provided. Use --help for usage information.")
            adieu(1)

        logger.info("Monitoring completed.")
    except Exception as e:
        logger.error(f"monitor.py/main: {traceback.format_exc()}")
        adieu(1)