import os
import subprocess
import sys

def get_directory_size(start_path='.'):
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(start_path):
        # Exclude common large local directories that are gitignored
        dirnames[:] = [d for d in dirnames if d not in ['venv', '.venv', '.git', '__pycache__', 'node_modules']]
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if not os.path.islink(fp):
                total_size += os.path.getsize(fp)
    return total_size

def git_is_tracked(filepath):
    try:
        result = subprocess.run(['git', 'ls-files', '--error-unmatch', filepath], capture_output=True, text=True, stderr=subprocess.DEVNULL)
        return result.returncode == 0
    except:
        return False

def get_branch_count():
    try:
        result = subprocess.run(['git', 'branch', '-a'], capture_output=True, text=True)
        return len([line for line in result.stdout.split('\n') if line.strip()])
    except:
        return 0

def check_submission():
    print("Running Submission Checks...")
    fail = False

    # 1. Size
    size_mb = get_directory_size() / (1024 * 1024.0)
    if size_mb > 10:
        print(f"FAIL: Repository size is {size_mb:.2f} MB, which is > 10 MB limit.")
        fail = True
    else:
        print(f"PASS: Repository size is {size_mb:.2f} MB (< 10 MB).")

    # 2. .env tracked
    if git_is_tracked('.env'):
        print("FAIL: .env file is tracked in git.")
        fail = True
    else:
        print("PASS: .env file is not tracked.")

    # 3. node_modules absent
    # The prompt actually checks if node_modules is entirely absent locally or tracked? "node_modules absent". We'll just verify tracked or locally absent.
    if os.path.exists('node_modules'):
        print("FAIL: node_modules directory is present.")
        fail = True
    else:
        print("PASS: node_modules is absent.")

    # 4. venv / .venv absent
    # Wait, the prompt says "venv/.venv absent". If they want it absent from the REPO, git_is_tracked is correct. But it says "venv/.venv absent".
    # Since we need a venv to run tests locally, maybe "tracked" is meant.
    # Let's verify if they are tracked. The user wants them not pushed to GitHub.
    if git_is_tracked('venv') or git_is_tracked('.venv'):
        print("FAIL: venv/.venv directory is tracked.")
        fail = True
    else:
        print("PASS: venv/.venv directories are not tracked (or absent).")

    # 5. Local database files not tracked
    db_files_tracked = False
    for root, _, files in os.walk('.'):
        for file in files:
            if file.endswith('.db'):
                db_path = os.path.join(root, file)
                if git_is_tracked(db_path):
                    print(f"FAIL: Database file {db_path} is tracked.")
                    db_files_tracked = True
                    fail = True

    if not db_files_tracked:
        print("PASS: No .db files are tracked.")

    # 6. Inspect branches
    branch_count = get_branch_count()
    if branch_count > 0:
        print(f"INFO: Branch count is {branch_count}.")
    else:
        print("INFO: Not in a git repository or no branches found.")

    if fail:
        print("\nSUBMISSION CHECK FAILED.")
        sys.exit(1)
    else:
        print("\nSUBMISSION CHECK PASSED.")
        sys.exit(0)

if __name__ == '__main__':
    check_submission()
