import logging
import os
import time
from typing import Dict, List, Optional
from netmiko import ConnectHandler
import textfsm
import yaml
from devices import NetworkDevice

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load configuration
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

class DeviceConnection:
    def __init__(self, device: NetworkDevice, username: str, password: str):
        self.device = device
        self.username = username
        self.password = password
        self.connection = None
        self.template_dir = os.path.join(os.path.dirname(__file__), 'templates')
        
    def _load_template(self, template_name: str) -> textfsm.TextFSM:
        """Load a TextFSM template"""
        template_path = os.path.join(self.template_dir, template_name)
        try:
            with open(template_path) as f:
                return textfsm.TextFSM(f)
        except Exception as e:
            logger.error(f"Error loading template {template_name}: {str(e)}")
            raise
            
    def connect(self) -> bool:
        """Establish connection to the device with retry logic"""
        for attempt in range(config['connection']['retry_attempts']):
            try:
                device_params = {
                    'device_type': 'cisco_ios',  # Default, will be updated after show version
                    'host': self.device.ip_address,
                    'username': self.username,
                    'password': self.password,
                    'timeout': config['connection']['timeout'],
                    'fast_cli': True
                }
                
                # Try hostname first if it's different from IP
                if self.device.hostname != self.device.ip_address:
                    try:
                        device_params['host'] = self.device.hostname
                        self.connection = ConnectHandler(**device_params)
                        return True
                    except Exception as e:
                        logger.warning(f"Failed to connect via hostname {self.device.hostname}: {str(e)}")
                        # Fall back to IP
                        device_params['host'] = self.device.ip_address
                
                self.connection = ConnectHandler(**device_params)
                return True
                
            except Exception as e:
                if attempt < config['connection']['retry_attempts'] - 1:
                    logger.warning(f"Connection attempt {attempt + 1} failed: {str(e)}")
                    time.sleep(config['connection']['retry_delay'])
                else:
                    logger.error(f"Failed to connect to {self.device.hostname} ({self.device.ip_address}): {str(e)}")
                    return False
                    
    def disconnect(self) -> None:
        """Close the connection"""
        if self.connection:
            try:
                self.connection.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting from {self.device.hostname}: {str(e)}")
                
    def execute_command(self, command: str) -> Optional[str]:
        """Execute a command and return the output with retry logic"""
        if not self.connection:
            return None
            
        for attempt in range(config['connection']['retry_attempts']):
            try:
                return self.connection.send_command(command)
            except Exception as e:
                if attempt < config['connection']['retry_attempts'] - 1:
                    logger.warning(f"Command '{command}' attempt {attempt + 1} failed: {str(e)}")
                    time.sleep(config['connection']['retry_delay'])
                else:
                    logger.error(f"Error executing command '{command}' on {self.device.hostname}: {str(e)}")
                    return None
                    
    def process_device(self) -> bool:
        """Process the device by executing required commands"""
        if not self.connect():
            return False
            
        try:
            # Get show version output
            version_output = self.execute_command('show version')
            if not version_output:
                return False
                
            # Parse version output and update device type
            version_data = self._parse_show_version(version_output)
            self.device.update_from_show_version(version_data)
            
            # Update device type for connection
            if 'iosxe' in self.device.platform.lower():
                self.connection.device_type = 'cisco_xe'
            elif 'nx-os' in self.device.platform.lower():
                self.connection.device_type = 'cisco_nxos'
                
            # Get show inventory output
            inventory_output = self.execute_command('show inventory')
            if inventory_output:
                inventory_data = self._parse_show_inventory(inventory_output)
                self.device.update_from_show_inventory(inventory_data)
                
            # Get CDP neighbors
            cdp_output = self.execute_command('show cdp neighbors detail')
            if cdp_output:
                cdp_data = self._parse_cdp_neighbors(cdp_output)
                self.device.update_from_cdp_neighbors(cdp_data)
                
            return True
            
        except Exception as e:
            logger.error(f"Error processing device {self.device.hostname}: {str(e)}")
            return False
        finally:
            self.disconnect()
            
    def _parse_show_version(self, output: str) -> Dict:
        """Parse show version output using TextFSM"""
        try:
            template = self._load_template('cisco_ios_show_version.template')
            results = template.ParseText(output)
            
            if not results:
                logger.warning(f"No data parsed from show version output for {self.device.hostname}")
                return {}
                
            # Get the first (and should be only) record
            result = results[0]
            
            return {
                'platform': result.get('PLATFORM', ''),
                'version': result.get('VERSION', ''),
                'uptime': result.get('UPTIME', ''),
                'serial': result.get('SERIAL', '')
            }
            
        except Exception as e:
            logger.error(f"Error parsing show version output for {self.device.hostname}: {str(e)}")
            return {}
            
    def _parse_show_inventory(self, output: str) -> Dict:
        """Parse show inventory output using TextFSM"""
        try:
            template = self._load_template('cisco_ios_show_inventory.template')
            results = template.ParseText(output)
            
            if not results:
                logger.warning(f"No data parsed from show inventory output for {self.device.hostname}")
                return {}
                
            # Find the chassis entry (usually first entry)
            for result in results:
                if 'chassis' in result.get('NAME', '').lower():
                    return {
                        'serial_number': result.get('SN', ''),
                        'part_number': result.get('PID', ''),
                        'description': result.get('DESCR', '')
                    }
                    
            return {}
            
        except Exception as e:
            logger.error(f"Error parsing show inventory output for {self.device.hostname}: {str(e)}")
            return {}
            
    def _parse_cdp_neighbors(self, output: str) -> List[Dict]:
        """Parse CDP neighbors detail output using TextFSM"""
        try:
            template = self._load_template('cisco_ios_show_cdp_neighbors_detail.template')
            results = template.ParseText(output)
            
            if not results:
                logger.warning(f"No data parsed from CDP neighbors output for {self.device.hostname}")
                return []
                
            neighbors = []
            for result in results:
                if result.get('IP_ADDRESS'):  # Only include neighbors with IP addresses
                    neighbors.append({
                        'hostname': result.get('DEVICE_ID', ''),
                        'platform': result.get('PLATFORM', ''),
                        'ip_address': result.get('IP_ADDRESS', ''),
                        'local_interface': result.get('LOCAL_INTERFACE', ''),
                        'remote_interface': result.get('PORT_ID', ''),
                        'capabilities': result.get('CAPABILITY', '')
                    })
                    
            return neighbors
            
        except Exception as e:
            logger.error(f"Error parsing CDP neighbors output for {self.device.hostname}: {str(e)}")
            return [] 