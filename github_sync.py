
import os
import subprocess
import datetime

# ==================== CONFIGURATION ====================
# ==================== CONFIGURATION ====================
GITHUB_TOKEN = "your_github_token_here"
GITHUB_REPO = "username/repository"  # e.g., "Drics/dev-media-encrypt"
BRANCH = "main"                     # e.g., "main" or "master"
# =======================================================

def run_cmd(cmd, check=True):
    print(f"Running: {cmd}")
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if res.returncode != 0 and check:
        print(f"Error executing command: {cmd}")
        print(f"Stdout:\n{res.stdout}")
        print(f"Stderr:\n{res.stderr}")
        raise RuntimeError(res.stderr)
    return res.stdout

def setup_gitignore():
    gitignore_path = ".gitignore"
    content = """# Byte-compiled / optimized / DLL files
__pycache__/
*.py[cod]
*$py.class

# IPynb Checkpoints
.ipynb_checkpoints/

# Media Encrypt Vault (Ignore actual media files, keep directory structure)
media_encrypt_vault/input/*
media_encrypt_vault/encrypted/*
media_encrypt_vault/decrypted/*
!media_encrypt_vault/input/.gitkeep
!media_encrypt_vault/encrypted/.gitkeep
!media_encrypt_vault/decrypted/.gitkeep

# Operating system files
.DS_Store
Thumbs.db
"""
    if not os.path.exists(gitignore_path):
        with open(gitignore_path, "w") as f:
            f.write(content)
        print("Created default .gitignore to exclude vault media and temporary files.")

def main():
    if GITHUB_TOKEN == "your_github_token_here" or GITHUB_REPO == "username/repository":
        print("="*60)
        print("⚠️  PLEASE CONFIGURATION FIRST!")
        print("Edit 'github_sync.py' and fill in your GITHUB_TOKEN, GITHUB_REPO, and BRANCH.")
        print("="*60)
        return

    print("=== Starting Automated GitHub Sync ===")
    
    # 1. Setup .gitignore
    setup_gitignore(),
    
    # Ensure .gitkeep files exist in vault directories so folders are tracked
    for folder in ['input', 'encrypted', 'decrypted']:
        folder_path = os.path.join('media_encrypt_vault', folder)
        os.makedirs(folder_path, exist_ok=True)
        gitkeep_path = os.path.join(folder_path, '.gitkeep')
        if not os.path.exists(gitkeep_path):
            with open(gitkeep_path, 'w') as f:
                f.write('')

    # 2. Initialize Git if not already done
    if not os.path.exists(".git"):
        print("Initializing local Git repository...")
        run_cmd("git init")
        run_cmd(f"git checkout -b {BRANCH}", check=False)
    
    # 3. Configure temporary Git identity if not set globally
    run_cmd("git config user.name \"Media-Encrypt Sync\"")
    run_cmd("git config user.email \"sync@media-encrypt.local\"")

    # 4. Configure authenticated remote URL
    # Handle repo input (extract username/repo if full URL is passed)
    clean_repo = GITHUB_REPO.replace("https://github.com/", "").replace(".git", "").strip("/")
    auth_url = f"https://{GITHUB_TOKEN}@github.com/{clean_repo}.git"
    
    # Set remote 'origin'
    run_cmd("git remote remove origin", check=False)
    run_cmd(f"git remote add origin {auth_url}")

    # 5. Add all changes (additions, modifications, deletions)
    print("Staging all changes (including additions, changes, and deletions)...")
    run_cmd("git add -A")

    # Check if there are changes to commit
    status_out = run_cmd("git status --porcelain")
    if not status_out.strip():
        print("No changes detected. Repository is already up to date!")
        return

    # 6. Commit changes
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    commit_msg = f"Auto-sync update: {timestamp}"
    print(f"Committing changes with message: '{commit_msg}'")
    run_cmd(f"git commit -m \"{commit_msg}\"")

    # 7. Push to GitHub
    print(f"Pushing updates to GitHub repository ({clean_repo}) on branch '{BRANCH}'...")
    # Force push is recommended to keep local as the absolute source of truth
    run_cmd(f"git push -u origin {BRANCH} --force")
    
    print("=== GitHub Synchronization Complete! ===")

if __name__ == "__main__":
    main()
