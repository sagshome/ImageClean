from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime, BigInteger, Text
from sqlalchemy.orm import declarative_base
from pathlib import Path
Base = declarative_base()
from PIL import Image, UnidentifiedImageError
import imagehash


class FileMeta(Base):
    __tablename__ = "files"
    id = Column(Integer, primary_key=True)
    path = Column(String, unique=True, nullable=False)
    size = Column(BigInteger, nullable=False)
    modified = Column(DateTime, nullable=False)
    hash = Column(String, nullable=False)   # SHA256
    perceptual_hash = Column(Text, nullable=True)
    # similar_to = Column(Integer, ForeignKey('files.id'), nullable=True)

class FileData:
    """
    Object to deal with individual files
    """
    def __init__(self, filepath:Path):
        if filepath.is_file():
            self.path = filepath.parent
            self.name = filepath.name
            self.stat = filepath.stat()
            if filepath.suffix.lower() in [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp"]:
                try:
                    img = Image.open(filepath)
                    self.hash = imagehash.phash(img)
                    img.close()
                except UnidentifiedImageError:
                    raise ValueError("cannot identify image file")
        else:
            raise ValueError("not a file")


