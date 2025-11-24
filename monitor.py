import monitoring.serviceMonitoring as service_module
import monitoring.hostMonitoring as host_module
import monitoring.fileMonitoring as file_module
from utils.log import log
from utils.report_generator import reportGenerator

import sys
import traceback
from sys import exit as adieu

def display_help() -> None:
    help_message = """
    Usage: python monitor.py [options]

    Help:
    --help          Display this help message

    Monitoring Options:
    --service       Run service monitoring
    --host          Run host monitoring
    --file          Run file monitoring
    --all           Run all monitoring modules

    Export Options:
    --generate-report   Generate a Markdown-report from the collected data

    """
    print(help_message)

def main():
    logger = log()

    logger.info("monitor.py: Starting monitoring script...")
    
    try:
        if len(sys.argv) < 2 or "--help" in sys.argv:
            logger.info("Displaying help information...")
            display_help()
            return
        
        if "--service" in sys.argv or "--all" in sys.argv:
            logger.info("Starting service monitoring...")
            service_monitor = service_module.serviceMonitoring()
            service_monitor.check_services()
        
        if "--host" in sys.argv or "--all" in sys.argv:
            logger.info("Starting host monitoring...")
            host_monitor = host_module.hostMonitoring()
            host_monitor.check_host_params()

        if "--file" in sys.argv or "--all" in sys.argv:
            logger.info("Starting file monitoring...")
            file_monitor = file_module.fileMonitoring()
            file_monitor.check_files()
        
        if "--generate-report" in sys.argv:
            logger.info("Generating report from collected data...")
            report_gen = reportGenerator()
            report_gen.generate_report()

        if not any(arg in sys.argv for arg in ["--service", "--host", "--file", "--all", "--generate-report"]):
            logger.error("No valid monitoring option provided. Use --help for usage information.")
            display_help()
            adieu(1)

        logger.info("Monitoring completed.")
    except Exception as e:
        logger.error(f"monitor.py/main: {traceback.format_exc()}")
        adieu(1)

if __name__ == "__main__":
    main()