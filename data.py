import os
import logging
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Boolean, DateTime, Integer, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import yaml

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load configuration
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

Base = declarative_base()

class Device(Base):
    __tablename__ = 'devices'
    
    id = Column(Integer, primary_key=True)
    hostname = Column(String, unique=True, nullable=False)
    ip_address = Column(String, unique=True, nullable=False)
    platform = Column(String)
    serial_number = Column(String)
    device_type = Column(String)
    discovered_at = Column(DateTime, default=datetime.utcnow)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<Device(hostname='{self.hostname}', ip='{self.ip_address}')>"

class Queue(Base):
    __tablename__ = 'queue'
    
    id = Column(Integer, primary_key=True)
    hostname = Column(String, unique=True, nullable=False)
    ip_address = Column(String, unique=True, nullable=False)
    is_processing = Column(Boolean, default=False)
    is_processed = Column(Boolean, default=False)
    added_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime)

class DatabaseManager:
    def __init__(self):
        db_path = config['database']['path']
        self.engine = create_engine(f'sqlite:///{db_path}', 
                                  connect_args={'timeout': 30})
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        
    def get_session(self):
        return self.Session()
    
    def add_device(self, session, device_data):
        """Add a new device to the database"""
        device = Device(**device_data)
        session.add(device)
        session.commit()
        return device
    
    def add_to_queue(self, session, hostname, ip_address):
        """Add a device to the processing queue"""
        queue_item = Queue(
            hostname=hostname,
            ip_address=ip_address
        )
        session.add(queue_item)
        session.commit()
        return queue_item
    
    def mark_processing(self, session, hostname):
        """Mark a device as being processed"""
        queue_item = session.query(Queue).filter_by(hostname=hostname).first()
        if queue_item:
            queue_item.is_processing = True
            session.commit()
            return True
        return False
    
    def mark_processed(self, session, hostname):
        """Mark a device as processed"""
        queue_item = session.query(Queue).filter_by(hostname=hostname).first()
        if queue_item:
            queue_item.is_processed = True
            queue_item.is_processing = False
            queue_item.processed_at = datetime.utcnow()
            session.commit()
            return True
        return False
    
    def get_next_device(self, session):
        """Get the next unprocessed device from the queue"""
        return session.query(Queue).filter_by(
            is_processed=False,
            is_processing=False
        ).first()
    
    def device_exists(self, session, hostname=None, ip_address=None):
        """Check if a device exists in either the devices or queue table"""
        if hostname:
            device = session.query(Device).filter_by(hostname=hostname).first()
            if device:
                return True
            queue_item = session.query(Queue).filter_by(hostname=hostname).first()
            if queue_item:
                return True
        if ip_address:
            device = session.query(Device).filter_by(ip_address=ip_address).first()
            if device:
                return True
            queue_item = session.query(Queue).filter_by(ip_address=ip_address).first()
            if queue_item:
                return True
        return False 