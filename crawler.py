import logging
import threading
import queue
import time
from typing import List, Dict
import yaml
from devices import NetworkDevice
from connect import DeviceConnection
from data import DatabaseManager
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load configuration
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

class NetworkCrawler:
    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.db = DatabaseManager()
        self.work_queue = queue.Queue()
        self.threads = []
        self.stop_event = threading.Event()
        self.stats = {
            'start_time': datetime.now(),
            'devices_processed': 0,
            'devices_discovered': 0,
            'processing_rate': 0,
            'active_devices': set(),
            'last_report_time': datetime.now()
        }
        self.stats_lock = threading.Lock()
        
    def _update_stats(self, device_processed: bool = False, device_discovered: bool = False,
                     active_device: str = None, remove_active: bool = False) -> None:
        """Update crawler statistics in a thread-safe manner"""
        with self.stats_lock:
            if device_processed:
                self.stats['devices_processed'] += 1
            if device_discovered:
                self.stats['devices_discovered'] += 1
            if active_device:
                if remove_active:
                    self.stats['active_devices'].discard(active_device)
                else:
                    self.stats['active_devices'].add(active_device)
                    
            # Calculate processing rate (devices per minute)
            elapsed_minutes = (datetime.now() - self.stats['start_time']).total_seconds() / 60
            if elapsed_minutes > 0:
                self.stats['processing_rate'] = self.stats['devices_processed'] / elapsed_minutes
                
    def _report_progress(self) -> None:
        """Report current progress and statistics"""
        with self.stats_lock:
            now = datetime.now()
            if (now - self.stats['last_report_time']).total_seconds() >= 30:  # Report every 30 seconds
                elapsed = now - self.stats['start_time']
                logger.info(f"\nCrawler Progress Report:")
                logger.info(f"Running for: {str(elapsed).split('.')[0]}")
                logger.info(f"Devices discovered: {self.stats['devices_discovered']}")
                logger.info(f"Devices processed: {self.stats['devices_processed']}")
                logger.info(f"Processing rate: {self.stats['processing_rate']:.2f} devices/minute")
                logger.info(f"Active devices: {len(self.stats['active_devices'])}")
                logger.info(f"Queue size: {self.work_queue.qsize()}")
                if self.stats['active_devices']:
                    logger.info(f"Currently processing: {', '.join(self.stats['active_devices'])}")
                self.stats['last_report_time'] = now
                
    def add_seed_device(self, hostname: str, ip_address: str) -> None:
        """Add a seed device to start the crawl"""
        session = self.db.get_session()
        try:
            if not self.db.device_exists(session, hostname, ip_address):
                self.db.add_to_queue(session, hostname, ip_address)
                self.work_queue.put((hostname, ip_address))
                self._update_stats(device_discovered=True)
        finally:
            session.close()
            
    def worker(self) -> None:
        """Worker thread that processes devices from the queue"""
        session = self.db.get_session()
        try:
            while not self.stop_event.is_set():
                try:
                    hostname, ip_address = self.work_queue.get(timeout=config['threading']['queue_timeout'])
                    
                    # Check if device is already being processed or processed
                    if self.db.device_exists(session, hostname, ip_address):
                        self.work_queue.task_done()
                        continue
                        
                    # Mark device as processing
                    self.db.mark_processing(session, hostname)
                    self._update_stats(active_device=hostname)
                    
                    # Create and process device
                    device = NetworkDevice(hostname, ip_address)
                    connection = DeviceConnection(device, self.username, self.password)
                    
                    if connection.process_device():
                        # Add device to database
                        self.db.add_device(session, device.to_dict())
                        self._update_stats(device_processed=True)
                        
                        # Add neighbors to queue
                        for neighbor in device.get_cdp_neighbors():
                            if not self.db.device_exists(session, neighbor['hostname'], neighbor['ip_address']):
                                self.db.add_to_queue(session, neighbor['hostname'], neighbor['ip_address'])
                                self.work_queue.put((neighbor['hostname'], neighbor['ip_address']))
                                self._update_stats(device_discovered=True)
                                
                    # Mark device as processed
                    self.db.mark_processed(session, hostname)
                    self._update_stats(active_device=hostname, remove_active=True)
                    
                    # Report progress
                    self._report_progress()
                    
                except queue.Empty:
                    continue
                except Exception as e:
                    logger.error(f"Error in worker thread: {str(e)}")
                finally:
                    self.work_queue.task_done()
                    
        finally:
            session.close()
            
    def start(self, num_workers: int = None) -> None:
        """Start the crawler with specified number of worker threads"""
        if num_workers is None:
            num_workers = config['threading']['max_workers']
            
        # Start worker threads
        for _ in range(num_workers):
            thread = threading.Thread(target=self.worker)
            thread.daemon = True
            thread.start()
            self.threads.append(thread)
            
        logger.info(f"Started crawler with {num_workers} worker threads")
        
    def stop(self) -> None:
        """Stop the crawler and wait for all threads to complete"""
        self.stop_event.set()
        
        # Wait for all threads to complete
        for thread in self.threads:
            thread.join()
            
        # Final progress report
        self._report_progress()
        logger.info("Crawler stopped")
        
    def wait_for_completion(self) -> None:
        """Wait for all queued work to be completed"""
        self.work_queue.join()
        
    def export_inventory(self) -> None:
        """Export device inventory to CSV"""
        session = self.db.get_session()
        try:
            devices = session.query(Device).all()
            
            # Create output directory if it doesn't exist
            output_dir = config['output']['directory']
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
                
            # Write to CSV
            output_file = os.path.join(output_dir, config['output']['inventory_file'])
            with open(output_file, 'w') as f:
                # Write header
                f.write("hostname,ip_address,platform,serial_number,device_type\n")
                
                # Write device data
                for device in devices:
                    f.write(f"{device.hostname},{device.ip_address},{device.platform},"
                           f"{device.serial_number},{device.device_type}\n")
                           
            logger.info(f"Inventory exported to {output_file}")
            
        finally:
            session.close() 