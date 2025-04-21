import argparse
import logging
import os
import sys
from crawler import NetworkCrawler
import yaml

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description='CDP Network Crawler')
    parser.add_argument('--username', required=True, help='SSH username')
    parser.add_argument('--password', required=True, help='SSH password')
    parser.add_argument('--seed-hostname', required=True, help='Seed device hostname')
    parser.add_argument('--seed-ip', required=True, help='Seed device IP address')
    parser.add_argument('--workers', type=int, help='Number of worker threads')
    
    args = parser.parse_args()
    
    try:
        # Create crawler instance
        crawler = NetworkCrawler(args.username, args.password)
        
        # Add seed device
        crawler.add_seed_device(args.seed_hostname, args.seed_ip)
        
        # Start crawler
        crawler.start(args.workers)
        
        try:
            # Wait for completion
            crawler.wait_for_completion()
            
            # Export inventory
            crawler.export_inventory()
            
        except KeyboardInterrupt:
            logger.info("Received interrupt signal, stopping crawler...")
        finally:
            crawler.stop()
            
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        sys.exit(1)
        
if __name__ == '__main__':
    main() 