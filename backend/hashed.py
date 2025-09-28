from pathlib import Path
import hashlib
from datetime import datetime
import os
from typing import Dict

import typer
from typing_extensions import Annotated

from sqlalchemy import create_engine, Column, Integer, String, DateTime, BigInteger, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from platformdirs import user_data_dir

from PIL import Image
import imagehash
import cProfile

from models import FileMeta, Base, FileData
app = typer.Typer()

# --- DB Setup ---

APP_NAME = "fileindexer"
APP_AUTHOR = "scott.sargent61@gmail.com"
db_path = os.path.join(user_data_dir(APP_NAME, APP_AUTHOR), "files.db")
os.makedirs(os.path.dirname(db_path), exist_ok=True)

engine = create_engine(f"sqlite:///{db_path}", echo=False)
Session = sessionmaker(bind=engine)

db_exists = os.path.exists(db_path)
# If database file didn’t exist, create schema
if not db_exists:
    print("Database not found. Creating new one...")
    Base.metadata.create_all(engine)

# --- Hash Functions ---
def sha256_file(path: Path, blocksize=65536) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(blocksize), b""):
            h.update(chunk)
    return h.hexdigest()


def phash_image(path: Path):
    try:
        img = Image.open(path)
        return str(imagehash.phash(img))
    except Exception:
        return None


# --- File Scanner ---
def scan_file(path: Path) -> FileMeta:
    stat = path.stat()
    meta = FileMeta(
        path=str(path.resolve()),
        size=stat.st_size,
        modified=datetime.fromtimestamp(stat.st_mtime),
    )

    if path.suffix.lower() not in [".tar"]:
        meta.hash = sha256_file(path)
    else:
        meta.hash = "0"

    if path.suffix.lower() in [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp"]:
        meta.perceptual_hash = phash_image(path)
    return meta

def index_directory(root: Path, follow_symlinks: bool = False):
    session = Session()
    for file in root.rglob("*"):
        try:
            if file.is_symlink() and not follow_symlinks:
                continue
            if file.is_file():
                meta = scan_file(file)
                existing = session.query(FileMeta).filter_by(path=meta.path).first()
                if existing:
                    if existing.size != meta.size or existing.modified != meta.modified:
                        existing.size = meta.size
                        existing.modified = meta.modified
                        existing.hash = meta.hash
                        existing.perceptual_hash = meta.perceptual_hash
                else:
                    session.add(meta)
        except Exception as e:
            typer.echo(f"⚠️ Skipped {file}: {e}")
    session.commit()
    session.close()

def test_all_folders(root: Path, follow_symlinks: bool = False):
    # from cleaner import Folder
    folders = {}  # Dictionary of path parts
    for file in root.rglob("*"):
        #if file.is_symlink() and not follow_symlinks:   # 6 seconds ?
        #    print(f'File:{file} is a symlink')
        if file.is_dir():
            folder = Folder(file, root)
            if folder.dates['date']:
                print(f'Score: {folder.score} Date: {folder.dates["date"].year} {folder.dates["date"].month} Description: {folder.description} Path:{folder.path}')
            elif folder.description and not folder.dates['date']:
                print(f'Score: {folder.score} No Date - Description: {folder.description} Path:{folder.path}')

        else:
            print('Hashing', file)
            hash = sha256_file(file)
            #if folder.dates:
            #    if folder.dates['month']:
            #        pass



import os, sys
from stat import *

def walktree(top, base, callback):
    '''recursively descend the directory tree rooted at top,
       calling the callback function for each regular file'''
    for f in os.listdir(top):
        pathname = os.path.join(top, f)
        stat = os.lstat(pathname)
        mode = stat.st_mode
        if S_ISDIR(mode):
            # It's a directory, recurse into it
            #print (top, f, int(stat.st_mtime), stat.st_size)
            f = Folder(Path(pathname), base)
            walktree(pathname, base, callback)
        elif S_ISREG(mode):
            # It's a file, call the callback function
            callback(pathname)
        else:
            # Unknown file type, print a message
            print('Skipping %s' % pathname)

def visitfile(file):
    pass
    # print('visiting', count, file)



def test_all_files(root: Path, follow_symlinks: bool = False):
    from cleaner import Folder
    folders = {}  # Dictionary of path parts
    for file in root.rglob("*"):
        if file.is_symlink() and not follow_symlinks:
            print(f'File:{file} is a symlink')
        if file.is_dir():
            folder = Folder(file, root)
            if folder.dates:
                if folder.dates['month']:
                    pass




def index_directory2(root: Path, follow_symlinks: bool = False):
    """
    Build a dictionary of lists of FileObjs with the file as key (internal DB)


    :keyword
    :param root:
    :param follow_symlinks:
    :return:
    """
    indexed = {}
    for file in root.rglob("*"):
        if file.is_symlink() and not follow_symlinks:
            continue
        if file.is_file():
            try:
                fileobj = FileData(file)
                lower_name = fileobj.name.lower()
                if lower_name in indexed:
                    indexed[lower_name].append(fileobj)
                else:
                    indexed[lower_name] = [fileobj,]
            except ValueError as e:
                print(f'Ignoring {e}: {file}')
    return indexed

def find_exact_duplicates():
    session = Session()
    dups = {}
    for row in session.query(FileMeta).all():
        key = (row.size, row.hash)
        dups.setdefault(key, []).append(row.path)
    session.close()
    return [paths for paths in dups.values() if len(paths) > 1]


def find_similar_images(threshold=5):
    session = Session()
    images = session.query(FileMeta).filter(FileMeta.perceptual_hash.isnot(None)).all()
    discovered = []
    similar_pairs = []
    for i, img1 in enumerate(images):
        print(i)
        if img1.id not in discovered:
            h1 = imagehash.hex_to_hash(img1.perceptual_hash)
            for img2 in images[i+1:]:
                # print ("   ", i, img2)
                h2 = imagehash.hex_to_hash(img2.perceptual_hash)
                dist = h1 - h2
                if dist <= threshold and dist != 0:
                    # print(f'Similar {img1.path} and {img2.path} score:{dist}')
                    similar_pairs.append((img1.path, img2.path, dist))
                    discovered.append(img2.id)
    session.close()
    return similar_pairs


# --- Typer CLI Commands ---

@app.command()
def hi_city(ctx: typer.Context,
            name: str = typer.Option(..., "--name", "-n", prompt=True, help="Name of person to say hi to")):
    """Say hello."""
    kwargs = ctx.params
    print(f"Hello, {name}. Welcome from {kwargs['city']}, {kwargs['state']}!")

@app.command()
def index(path: Path, follow_symlinks: int = typer.Option(None, help="Follow symlinks")):
    """Index all files under PATH recursively."""
    typer.echo(f"Indexing {path} ...")
    index_directory(path, follow_symlinks=follow_symlinks)
    typer.echo(f"Done. DB stored at: {db_path}")

@app.command()
def readdir(path: Path, follow_symlinks: bool = typer.Option(False, help="Follow symlinks")):
    """Index all files under PATH recursively."""
    typer.echo(f"Indexing {path} ...")
    index_directory2(path, follow_symlinks=follow_symlinks)

@app.command()
def testfolders(path: Path, follow_symlinks: bool = typer.Option(False, help="Follow symlinks")):
    """Index all files under PATH recursively."""
    typer.echo(f"Testing Folders {path} ...")
    test_all_folders(path, follow_symlinks=follow_symlinks)


@app.command()
def dupes():
    """Find and show exact duplicate files."""
    groups = find_exact_duplicates()
    if groups:
        typer.echo("\nExact duplicates found:")
        for group in groups:
            typer.echo(" - " + "\n   ".join(group))
    else:
        typer.echo("No exact duplicates found.")


@app.command()
def similar(threshold: int = typer.Option(5, help="Maximum Hamming distance")):
    """Find and show visually similar images."""
    pairs = find_similar_images(threshold)
    if pairs:
        typer.echo("\nVisually similar images found:")
        for img1, img2, dist in pairs:
            typer.echo(f" - {img1}\n   {img2}\n   (distance={dist})")
    else:
        typer.echo("No visually similar images found.")


if __name__ == "__main__":
    app()
