from pathlib import Path
from datetime import datetime
import shutil


DATABASE_PATH = Path("data/database/f1_fantasy.duckdb")
BACKUP_DIR = Path("data/database")


def create_backup(label="pre_barcelona"):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    backup_name = f"f1_fantasy_{label}_{timestamp}.duckdb"
    backup_path = BACKUP_DIR / backup_name

    shutil.copy2(DATABASE_PATH, backup_path)

    print(f"Backup created:")
    print(backup_path)

    return backup_path


if __name__ == "__main__":
    create_backup()