import logging
import re
from typing import Dict, List, Optional
import yaml

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load configuration
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

class NetworkDevice:
    def __init__(self, hostname: str, ip_address: str):
        self.hostname = self._normalize_hostname(hostname)
        self.ip_address = ip_address
        self.platform = None
        self.serial_number = None
        self.device_type = None
        self.raw_data = {}
        
    @staticmethod
    def _normalize_hostname(hostname: str) -> str:
        """Normalize hostname by removing FQDN and serial number annotations"""
        # Remove FQDN
        hostname = hostname.split('.')[0]
        
        # Remove serial number annotations
        hostname = re.sub(r'\s*\(Serial:.*\)', '', hostname)
        
        return hostname.strip().lower()
    
    def update_from_show_version(self, data: Dict) -> None:
        """Update device information from show version output"""
        self.platform = data.get('platform', '')
        self.device_type = self._determine_device_type()
        self.raw_data['version'] = data
        
    def update_from_show_inventory(self, data: Dict) -> None:
        """Update device information from show inventory output"""
        self.serial_number = data.get('serial_number', '')
        self.raw_data['inventory'] = data
        
    def update_from_cdp_neighbors(self, data: List[Dict]) -> None:
        """Update device information from CDP neighbors output"""
        self.raw_data['cdp_neighbors'] = data
        
    def _determine_device_type(self) -> str:
        """Determine device type based on platform string"""
        platform_lower = self.platform.lower()
        
        # Check exclude patterns first
        for pattern in config['filtering']['exclude_platforms']:
            if pattern.lower() in platform_lower:
                return 'excluded'
                
        # Check for specific Cisco platforms
        if 'nx-os' in platform_lower or 'nexus' in platform_lower:
            return 'cisco_nxos'
        elif 'ios-xe' in platform_lower or 'ios xe' in platform_lower:
            return 'cisco_xe'
        elif 'ios' in platform_lower:
            return 'cisco_ios'
            
        # Check include patterns
        for pattern in config['filtering']['include_platforms']:
            if pattern.lower() in platform_lower:
                return pattern
                
        return 'unknown'
    
    def is_infrastructure_device(self) -> bool:
        """Check if this is an infrastructure device based on platform"""
        return self.device_type != 'excluded' and self.device_type != 'unknown'
    
    def to_dict(self) -> Dict:
        """Convert device information to dictionary"""
        return {
            'hostname': self.hostname,
            'ip_address': self.ip_address,
            'platform': self.platform,
            'serial_number': self.serial_number,
            'device_type': self.device_type
        }
    
    def get_cdp_neighbors(self) -> List[Dict]:
        """Get list of CDP neighbors that should be processed"""
        neighbors = []
        if 'cdp_neighbors' not in self.raw_data:
            return neighbors
            
        for neighbor in self.raw_data['cdp_neighbors']:
            # Skip if no IP address
            if not neighbor.get('ip_address'):
                continue
                
            # Create temporary device to check if it's infrastructure
            temp_device = NetworkDevice(
                hostname=neighbor.get('hostname', ''),
                ip_address=neighbor.get('ip_address', '')
            )
            temp_device.platform = neighbor.get('platform', '')
            temp_device.device_type = temp_device._determine_device_type()
            
            if temp_device.is_infrastructure_device():
                neighbors.append({
                    'hostname': temp_device.hostname,
                    'ip_address': temp_device.ip_address
                })
                
        return neighbors 