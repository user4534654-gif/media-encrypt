import os
import zipfile
from datetime import datetime

def main():
    # 1. Resolve Backup directory (prefer shared Android Download folder first)
    backup_dir = "/storage/emulated/0/Download"
    if not os.path.exists(backup_dir):
        # Fallback to standard ~/Downloads
        home = os.path.expanduser("~")
        backup_dir = os.path.join(home, "Downloads")
        
    backup_folder = os.path.join(backup_dir, "Media-Encrypt-Studio-Backups")
    if not os.path.exists(backup_folder):
        try:
            os.makedirs(backup_folder)
            print(f"Created backup directory: {backup_folder}")
        except Exception as e:
            # If subfolder creation fails, fallback to direct backup directory
            backup_folder = backup_dir
            print(f"Using direct backup directory: {backup_folder} (Error: {e})")
        
    # 2. Get current date and time for the zip filename
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    zip_name = f"Media-Encrypt-Studio_Backup_{timestamp}.zip"
    zip_path = os.path.join(backup_folder, zip_name)
    
    # 3. Locate project root
    project_root = os.path.abspath(os.path.dirname(__file__))
    print(f"Project root detected: {project_root}")
    print(f"Creating zip backup at: {zip_path}")
    
    # 4. Generate zip file
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(project_root):
            # Exclude pycache, git, docker, and checkpoints directories
            dirs[:] = [d for d in dirs if d not in ['__pycache__', '.git', '.ipynb_checkpoints', '.docker', 'node_modules']]
            
            # Determine relative path of current directory
            rel_dir = os.path.relpath(root, project_root)
            
            # Add directories to zip (handles empty folders like vault folders)
            if rel_dir != ".":
                dir_arcname = rel_dir.replace('\\', '/') + '/'
                zipf.writestr(zipfile.ZipInfo(dir_arcname), '')
                
            # Add files to zip
            for file in files:
                file_path = os.path.join(root, file)
                file_rel = os.path.relpath(file_path, project_root)
                file_rel_clean = file_rel.replace('\\', '/')
                
                # Skip media vault files to keep backups lightweight, but keep folder structure
                is_vault_media = (
                    file_rel_clean.startswith("media_encrypt_vault/input/") or
                    file_rel_clean.startswith("media_encrypt_vault/encrypted/") or
                    file_rel_clean.startswith("media_encrypt_vault/decrypted/")
                )
                
                if is_vault_media:
                    continue
                    
                zipf.write(file_path, file_rel)
                
    print("Backup completed successfully!")
    print(f"Saved to: {zip_path}")

if __name__ == "__main__":
    main()
