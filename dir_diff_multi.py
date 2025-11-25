import os
import sys
import json
import hashlib
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

################################################################################
# Multi-Thread detection
################################################################################

def auto_threads(multiplier=4, minimum=4, maximum=64):
    # Auto-tune thread count based on CPU count.
    # multiplier: how many threads per CPU core
    # minimum: minimum thread count
    # maximum: hard thread cap
    cores = os.cpu_count() or 4
    threads = cores * multiplier
    return max(minimum, min(threads, maximum))

################################################################################
# HASHING
################################################################################

def hash_file(path, block_size=65536):
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(block_size)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()

################################################################################
# MANIFEST GENERATION (MULTI-THREADED)
################################################################################

def _hash_file_task(directory, full_path):
    ## Worker task for hashing a single file
    rel_path = full_path.relative_to(directory)
    return str(rel_path), {
        "hash": hash_file(full_path),
        "size": os.path.getsize(full_path)
    }

def build_manifest(directory, threads=None):
    directory = Path(directory)
    manifest = {}

    # Collect file list first
    file_paths = []
    for root, _, files in os.walk(directory):
        for file in files:
            file_paths.append(Path(root) / file)

    #Auto threading
    if threads is None:
        threads = auto_threads()

    # Parallel hashing
    with ThreadPoolExecutor(max_workers=threads) as executor:
        futures = [
            executor.submit(_hash_file_task, directory, fp)
            for fp in file_paths
        ]

        for fut in as_completed(futures):
            rel_path, data = fut.result()
            manifest[rel_path] = data

    return manifest

################################################################################
# MANIFEST SAVE / LOAD
################################################################################

def save_manifest(manifest, manifest_file):
    with open(manifest_file, "w") as f:
        json.dump(manifest, f, indent=2)

def load_manifest(manifest_file):
    with open(manifest_file, "r") as f:
        return json.load(f)

################################################################################
# COMPARISON LOGIC
################################################################################

def diff_manifests(man1, man2):
    added = []
    removed = []
    changed = []

    files1 = set(man1.keys())
    files2 = set(man2.keys())

    added.extend(files2 - files1)
    removed.extend(files1 - files2)

    for f in files1 & files2:
        if man1[f]["hash"] != man2[f]["hash"]:
            changed.append(f)

    return added, removed, changed

################################################################################
# COPY FILES (MULTI-THREADED)
################################################################################

def _copy_file_task(src, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return str(dest)

def copy_files(file_list, source_dir, output_dir, threads=None):
    source_dir = Path(source_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    #Auto thread detection
    if threads is None:
        threads = auto_threads()

    with ThreadPoolExecutor(max_workers=threads) as executor:
        futures = []
        for rel_path in file_list:
            src = source_dir / rel_path
            dest = output_dir / rel_path
            futures.append(executor.submit(_copy_file_task, src, dest))

        # Optional: progress output
        for fut in as_completed(futures):
            _ = fut.result()

################################################################################
# MAIN FUNCTIONS
################################################################################

def generate_manifest(src_dir, save_new_manifest=None):
    print("Building current manifest (multi-threaded)...")
    new_manifest = build_manifest(src_dir)

    if save_new_manifest:
        save_manifest(new_manifest, save_new_manifest)
        print(f"New manifest saved to: {save_new_manifest}")

def extract_differential(src_dir, old_manifest_file, output_dir=None, save_new_manifest=None):
    print("Loading old manifest...")
    old_manifest = load_manifest(old_manifest_file)

    print("Building current manifest (multi-threaded)...")
    new_manifest = build_manifest(src_dir)

    print("Comparing directories...")
    added, removed, changed = diff_manifests(old_manifest, new_manifest)

    print("\nDIFF RESULTS:")
    print(f"  Added:   {len(added)}")
    print(f"  Removed: {len(removed)}")
    print(f"  Changed: {len(changed)}")

    if output_dir:
        print(f"\nCopying differential files to: {output_dir} (multi-threaded)")
        to_copy = added + changed
        copy_files(to_copy, src_dir, output_dir)
        print("Copy complete.")

    if save_new_manifest:
        save_manifest(new_manifest, save_new_manifest)
        print(f"New manifest saved to: {save_new_manifest}")

    return added, removed, changed

################################################################################
# CLI
################################################################################

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Directory differential extractor (multi-threaded)")
    parser.add_argument("directory", help="Directory to analyze")
    parser.add_argument("--build", help="Only build the manifest for target directory", action="store_true")
    parser.add_argument("--old", help="Old manifest file")
    parser.add_argument("--out", help="Directory where differential files will be copied")
    parser.add_argument("--save", help="Where to save the new manifest")

    args = parser.parse_args()

    if args.build:
        generate_manifest(args.directory, args.save)
        sys.exit()

    extract_differential(
        args.directory,
        args.old,
        output_dir=args.out,
        save_new_manifest=args.save
    )
