# CDP Network Crawler

A multi-threaded CDP crawler for discovering and inventorying Cisco network infrastructure. The crawler recursively discovers devices via CDP, gathers structured information via CLI, and maintains a database of discovered devices.

## Features

- Multi-threaded device discovery
- CDP-based recursive network crawling
- Infrastructure device filtering (excludes phones/APs)
- Structured data collection via CLI
- SQLite database for device tracking
- Progress reporting and statistics
- CSV export of inventory
- Smart connection handling (hostname-first, IP fallback)

## Requirements

- Python 3.7+
- Required packages (see requirements.txt):
  - netmiko>=4.1.2
  - textfsm>=1.1.3
  - napalm>=4.1.0
  - pyyaml>=6.0.1
  - sqlalchemy>=2.0.0
  - python-dotenv>=1.0.0

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd crawler-rev-4
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

The crawler uses a `config.yaml` file for configuration. Default settings:

```yaml
# Threading Configuration
threading:
  max_workers: 4
  queue_timeout: 30  # seconds

# Database Configuration
database:
  path: "network_inventory.db"
  journal_mode: "WAL"  # Write-Ahead Logging for better concurrency

# Connection Settings
connection:
  timeout: 30  # seconds
  retry_attempts: 3
  retry_delay: 5  # seconds

# Logging Configuration
logging:
  level: "INFO"
  file: "crawler.log"
  max_size: 10485760  # 10MB
  backup_count: 5

# Output Configuration
output:
  directory: "outputs"
  inventory_file: "final_inventory.csv"

# Device Filtering
filtering:
  exclude_platforms:
    - "AIR-"
    - "CP-"
    - "Cisco IP Phone"
    - "SPA-"
    - "ATA-"
  include_platforms:
    - "switch"
    - "router"
    - "firewall"
    - "nexus"
```

## Usage

### Basic Usage

```bash
python main.py --username <username> --password <password> --seed-hostname <hostname> --seed-ip <ip-address>
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `--username` | Yes | SSH username for device access |
| `--password` | Yes | SSH password for device access |
| `--seed-hostname` | Yes | Hostname of the seed device |
| `--seed-ip` | Yes | IP address of the seed device |
| `--workers` | No | Number of worker threads (default: 4) |

### Example

```bash
python main.py --username admin --password secret123 --seed-hostname core-switch1 --seed-ip 192.168.1.1
```

### Connection Behavior

The crawler uses a smart connection strategy:

1. **Primary Connection Method**: Cleaned hostname
   - Hostnames are normalized (FQDN and serial numbers removed)
   - Attempts connection using the cleaned hostname first
   - Requires DNS resolution or hosts file entry

2. **Fallback Method**: Management IP from CDP
   - Only used if hostname connection fails
   - IP address is extracted from CDP neighbor detail output
   - Must be a valid management IP address

Example hostname normalization:
```
Original: Stephen-01-sw01.stephen.com (Serial: ABC123)
Cleaned: stephen-01-sw01
```

### Progress Reporting

The crawler provides progress reports every 30 seconds showing:
- Running time
- Number of devices discovered
- Number of devices processed
- Processing rate (devices/minute)
- Active devices
- Queue size

Example progress report:
```
Crawler Progress Report:
Running for: 0:05:30
Devices discovered: 15
Devices processed: 10
Processing rate: 1.82 devices/minute
Active devices: 2
Queue size: 5
Currently processing: switch1, router2
```

### Output

The crawler generates two main outputs:

1. **SQLite Database** (`network_inventory.db`):
   - Contains all discovered devices
   - Tracks processing queue
   - Maintains device relationships

2. **CSV Inventory** (`outputs/final_inventory.csv`):
   - Exported after crawl completion
   - Contains: hostname, IP, platform, serial number, device type

## Device Filtering

The crawler automatically filters out non-infrastructure devices based on platform strings:

### Excluded Devices
- Cisco IP phones
- Wireless access points
- Analog telephone adapters
- Other non-infrastructure endpoints

### Included Devices
- Switches
- Routers
- Firewalls
- Nexus devices

## Error Handling

The crawler includes robust error handling:
- Connection retries
- Command execution retries
- Thread-safe operations
- Comprehensive logging

## Logging

Logs are written to `crawler.log` with the following information:
- Connection attempts
- Command execution
- Device discovery
- Error messages
- Progress reports

## Notes

- The crawler uses CDP to discover neighbors
- Only devices with valid IP addresses are processed
- Hostnames are normalized (FQDN and serial numbers removed)
- The database prevents duplicate processing
- The crawler can be stopped with Ctrl+C and will complete current operations
- DNS resolution or hosts file entries are required for hostname-based connections 