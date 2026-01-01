from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
import datetime

# The Base class is used by SQLAlchemy to map your Python class to a database table
Base = declarative_base()

class Farmer(Base):
    """
    This model defines the 'farmers' table in your SQLite database.
    It stores all information collected during the survey.
    """
    __tablename__ = 'farmers'

    # Primary Key: Unique ID for every farmer
    id = Column(Integer, primary_key=True, autocat_increment=True)
    
    # Automatically records the date and time of registration
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Farmer Personal Info
    name = Column(String, nullable=False)
    woreda = Column(String, nullable=False)
    kebele = Column(String)
    phone = Column(String)
    
    # Audio Storage: Stores the recording as a Base64 encoded string
    audio_data = Column(Text) 
    
    # Editor Tracking: Stores the name of the person who logged in to register this farmer
    registered_by = Column(String)

def create_tables(engine):
    """
    Utility function to create the table in the database file
    """
    Base.metadata.create_all(bind=engine)
