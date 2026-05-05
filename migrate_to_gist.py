"""
Migration script to transfer data from local JSON files to GitHub Gists.
Run this script once to migrate your existing data.
"""

import asyncio
import json
import os
import sys

from dotenv import load_dotenv

load_dotenv()

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import init_database, close_database


async def migrate():
    """Migrate data from local JSON files to GitHub Gists."""
    print("=" * 60)
    print("Atom Bot - Local to GitHub Gist Migration Tool")
    print("=" * 60)
    print()

    # Check required environment variables
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("❌ Error: GITHUB_TOKEN environment variable is not set")
        print("   Please create a GitHub token with 'gist' scope and add it to your .env file")
        return False

    # Initialize database
    print("🔧 Initializing database connection...")
    try:
        db = await init_database()
        print("✅ Database initialized successfully")
    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        return False

    # Determine data directory
    data_dir = "/data" if os.path.exists("/data") else "data"
    print(f"📁 Using data directory: {data_dir}")

    # Migration map: (local_file, gist_filename, description)
    migration_map = [
        ("hourly_cats.json", "cats.json", "Cat channel settings"),
        ("qotd.json", "qotd.json", "Question of the Day data"),
        ("sticky.json", "sticky.json", "Sticky message configurations"),
        ("trap.json", "trap.json", "Trap channel settings"),
    ]

    migrated_count = 0
    skipped_count = 0
    error_count = 0

    print()
    print("🔄 Starting migration...")
    print()

    for local_file, gist_file, description in migration_map:
        local_path = os.path.join(data_dir, local_file)
        
        if not os.path.exists(local_path):
            print(f"⏭️  Skipping {description} - {local_file} not found")
            skipped_count += 1
            continue

        try:
            # Read local file
            with open(local_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not data:
                print(f"⏭️  Skipping {description} - {local_file} is empty")
                skipped_count += 1
                continue

            # Save to gist
            await db.set_all(gist_file, data)
            
            # Count entries
            entry_count = len(data) if isinstance(data, dict) else len(data)
            print(f"✅ Migrated {description}: {entry_count} entries")
            migrated_count += 1

        except json.JSONDecodeError as e:
            print(f"❌ Error reading {local_file}: Invalid JSON - {e}")
            error_count += 1
        except Exception as e:
            print(f"❌ Error migrating {description}: {e}")
            error_count += 1

    print()
    print("=" * 60)
    print("📊 Migration Summary")
    print("=" * 60)
    print(f"✅ Successfully migrated: {migrated_count} files")
    print(f"⏭️  Skipped: {skipped_count} files")
    print(f"❌ Errors: {error_count} files")
    print()

    if migrated_count > 0:
        print("🎉 Migration completed successfully!")
        print()
        print("📝 Next steps:")
        print("   1. Verify your data in the GitHub Gist")
        print("   2. Restart your bot to use the new database")
        print("   3. (Optional) Remove or backup your local data/ directory")
        print()
        print(f"🔗 Your gist ID: {db.gist_id}")
        print(f"🔗 Gist URL: https://gist.github.com/{db.gist_id}")
    else:
        print("⚠️  No data was migrated. Check the messages above for details.")

    # Clean up
    await close_database()
    return migrated_count > 0


def main():
    """Main entry point."""
    print()
    print("This script will migrate your local JSON data to GitHub Gists.")
    print("Make sure you have set up your .env file with GITHUB_TOKEN before proceeding.")
    print()
    
    response = input("Continue? (yes/no): ").strip().lower()
    if response not in ("yes", "y"):
        print("Migration cancelled.")
        return

    # Run migration
    success = asyncio.run(migrate())
    
    if success:
        print("Migration completed successfully! 🎉")
        sys.exit(0)
    else:
        print("Migration failed or no data was migrated. ❌")
        sys.exit(1)


if __name__ == "__main__":
    main()