"""Version bumping script for Cyber-Lighthouse."""
import re
import sys
import subprocess
from pathlib import Path
from enum import Enum


class BumpType(Enum):
    """Version bump types."""
    MAJOR = "major"
    MINOR = "minor"
    PATCH = "patch"


class VersionManager:
    """Manage version bumping across project files."""

    VERSION_PATTERN = re.compile(r"(\d+)\.(\d+)\.(\d+)")
    FILES_TO_UPDATE = [
        "pyproject.toml",
        "server.py",
    ]

    def __init__(self):
        """Initialize version manager."""
        self.current_version = self._get_current_version()
        print(f"Current version: {self.current_version}")

    def _get_current_version(self) -> str:
        """Get current version from pyproject.toml."""
        pyproject_path = Path("pyproject.toml")

        if not pyproject_path.exists():
            # Try reading from a version file or return default
            return "0.0.1"

        try:
            with open(pyproject_path, "r", encoding="utf-8") as f:
                content = f.read()
                match = self.VERSION_PATTERN.search(content)
                if match:
                    return f"{match.group(1)}.{match.group(2)}.{match.group(3)}"
        except Exception as e:
            print(f"Warning: Could not read version: {e}")

        return "0.0.1"

    def parse_version(self, version: str) -> tuple:
        """Parse version string into (major, minor, patch)."""
        match = self.VERSION_PATTERN.match(version)
        if not match:
            raise ValueError(f"Invalid version format: {version}")
        return (int(match.group(1)), int(match.group(2)), int(match.group(3)))

    def bump_version(self, bump_type: BumpType) -> str:
        """Calculate new version based on bump type."""
        major, minor, patch = self.parse_version(self.current_version)

        if bump_type == BumpType.MAJOR:
            major += 1
            minor = 0
            patch = 0
        elif bump_type == BumpType.MINOR:
            minor += 1
            patch = 0
        elif bump_type == BumpType.PATCH:
            patch += 1

        return f"{major}.{minor}.{patch}"

    def update_file(self, filepath: str, old_version: str, new_version: str) -> bool:
        """Update version in a specific file."""
        file_path = Path(filepath)

        if not file_path.exists():
            print(f"⚠️  File not found: {filepath}")
            return False

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Replace version pattern
            updated_content = self.VERSION_PATTERN.sub(
                new_version, content, count=1
            )

            if updated_content == content:
                print(f"⚠️  No version found in {filepath}")
                return False

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(updated_content)

            print(f"✅ Updated {filepath}: {old_version} → {new_version}")
            return True

        except Exception as e:
            print(f"❌ Error updating {filepath}: {e}")
            return False

    def create_git_tag(self, version: str) -> bool:
        """Create a git tag for the new version."""
        try:
            subprocess.run(
                ["git", "tag", "-a", f"v{version}", "-m", f"Release version {version}"],
                check=True,
                capture_output=True,
            )
            print(f"✅ Created git tag: v{version}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Error creating git tag: {e}")
            return False

    def commit_version_bump(self, version: str) -> bool:
        """Commit version bump changes."""
        try:
            subprocess.run(["git", "add", "-A"], check=True, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", f"Bump version to {version}"],
                check=True,
                capture_output=True,
            )
            print(f"✅ Committed version bump: {version}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Error committing version bump: {e}")
            return False


def confirm_action(message: str) -> bool:
    """Ask user to confirm an action."""
    response = input(f"\n{message} (yes/no): ").strip().lower()
    return response == "yes"


def main():
    """Main entry point for version bumping."""
    print("\n" + "=" * 70)
    print("🔄 Cyber-Lighthouse Version Bumper")
    print("=" * 70 + "\n")

    # Parse arguments
    if len(sys.argv) < 2:
        print("Usage: python bump_version.py [major|minor|patch]")
        print("\nExamples:")
        print("  python bump_version.py major  # 1.0.0 → 2.0.0")
        print("  python bump_version.py minor  # 1.0.0 → 1.1.0")
        print("  python bump_version.py patch  # 1.0.0 → 1.0.1")
        sys.exit(1)

    bump_type_str = sys.argv[1].lower()

    try:
        bump_type = BumpType(bump_type_str)
    except ValueError:
        print(f"❌ Invalid bump type: {bump_type_str}")
        print("Valid options: major, minor, patch")
        sys.exit(1)

    # Initialize manager
    manager = VersionManager()

    # Calculate new version
    new_version = manager.bump_version(bump_type)

    print(f"📊 Version Bump: {bump_type.value.upper()}")
    print(f"   {manager.current_version} → {new_version}\n")

    # Show what will be updated
    print("📝 Files to update:")
    for filepath in manager.FILES_TO_UPDATE:
        if Path(filepath).exists():
            print(f"   ✓ {filepath}")
        else:
            print(f"   ⊘ {filepath} (not found)")

    # Confirm action
    if not confirm_action("\nProceed with version bump?"):
        print("❌ Version bump cancelled")
        sys.exit(1)

    # Update files
    print("\n🔧 Updating files...\n")
    files_updated = 0
    for filepath in manager.FILES_TO_UPDATE:
        if manager.update_file(filepath, manager.current_version, new_version):
            files_updated += 1

    if files_updated == 0:
        print("❌ Error: No files were updated. Check that pyproject.toml exists.")
        sys.exit(1)

    print(f"\n✅ Successfully updated {files_updated} file(s)")

    # Commit changes
    if confirm_action("Commit these changes to git?"):
        if not manager.commit_version_bump(new_version):
            print("⚠️  Files updated but git commit failed")
            sys.exit(1)

        # Create tag
        if confirm_action("Create git tag for this release?"):
            if not manager.create_git_tag(new_version):
                print("⚠️  Version committed but git tag creation failed")
                sys.exit(1)
    else:
        print("⚠️  Changes made but not committed")
        print("   You can manually commit with: git add -A && git commit -m 'Bump version to {}'".format(new_version))

    # Final summary
    print("\n" + "=" * 70)
    print("✅ Version Bump Complete!")
    print("=" * 70)
    print(f"\nNew version: {new_version}")
    print(f"Tag: v{new_version}")
    print("\nNext steps:")
    print(f"  1. Verify changes: git log -1")
    print(f"  2. Push changes: git push origin master")
    print(f"  3. Push tag: git push origin v{new_version}")
    print()


if __name__ == "__main__":
    main()
