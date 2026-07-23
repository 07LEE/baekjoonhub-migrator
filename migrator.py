#!/usr/bin/env python3
"""BaekjoonHub Auto-push Repository Migration Tool.

This module provides functionality to rewrite Git commit history while preserving
all original commit timestamps, author metadata, and commit messages, reorganizing
auto-pushed problem solutions into a unified directory layout.
"""

import os
import re
import sys
import subprocess
import argparse
from typing import Dict, List, Tuple, Optional

# Reconfigure stdout and stderr to handle UTF-8 and special unicode characters (like \u2005) on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')


class PathMapper:
    """Handles path transformation rules for auto-pushed algorithm repositories."""

    LANGUAGE_EXTENSIONS = {
        '.py': 'Python',
        '.java': 'Java',
        '.cpp': 'C++',
        '.cc': 'C++',
        '.c': 'C',
        '.js': 'JavaScript',
        '.ts': 'TypeScript',
        '.kt': 'Kotlin',
        '.swift': 'Swift',
        '.rb': 'Ruby',
        '.go': 'Go',
        '.rs': 'Rust',
        '.sql': 'SQL',
        '.oracle': 'Oracle',
        '.mysql': 'MySQL',
        '.cs': 'C#',
        '.sh': 'Bash',
        '.gs': 'Golfscript',
    }


    PLATFORMS = {'백준', '프로그래머스', 'SWEA', 'goormlevel', 'LEETCODE'}

    @classmethod
    def detect_language(cls, filename: str) -> str:
        """Detect programming language based on file extension.

        Args:
            filename: Name of the code file.

        Returns:
            Language folder name or 'Unknown'.
        """
        _, ext = os.path.splitext(filename.lower())
        return cls.LANGUAGE_EXTENSIONS.get(ext, 'Misc')


    SQL_CACHE: Dict[str, str] = {}

    @classmethod
    def detect_sql_dialect(cls, content: str) -> str:
        """Detect whether SQL content is Oracle or MySQL based on syntax keywords.

        Args:
            content: Source code text of the SQL file.

        Returns:
            'Oracle' or 'MySQL'.
        """
        upper_content = content.upper()
        oracle_keywords = ['NVL', 'SYSDATE', 'TO_CHAR', 'TO_DATE', 'DECODE', 'ROWNUM', 'VARCHAR2', 'NUMBER', 'CONNECT BY']
        mysql_keywords = ['IFNULL', 'DATE_FORMAT', 'NOW()', 'LIMIT', 'CONCAT', 'GROUP_CONCAT']

        if any(kw in upper_content for kw in oracle_keywords):
            return 'Oracle'
        if any(kw in upper_content for kw in mysql_keywords):
            return 'MySQL'
        return 'MySQL'

    @classmethod
    def transform_path(cls, path: str, mode: str, content_getter=None, blob_sha: str = None) -> str:
        """Transform a file path according to the selected migration mode.

        Args:
            path: Original relative file path in the repository.
            mode: Migration mode ('platform_first', 'language_first', 'flat').
            content_getter: Optional callable to fetch blob content by sha.
            blob_sha: Git blob SHA of the file.

        Returns:
            Transformed relative file path.
        """
        # Normalize slashes
        parts = [p for p in path.replace('\\', '/').split('/') if p]
        if not parts:
            return path

        top_dir = parts[0]
        # Normalize legacy 'Python3' directory name to 'Python'
        if top_dir == 'Python3':
            top_dir = 'Python'
        sub_parts = parts[1:]


        # Helper to detect exact language from code file extension
        code_file = next(
            (p for p in reversed(parts) if p.lower() != 'readme.md' and os.path.splitext(p)[1]),
            None
        )
        detected_lang = None
        if code_file:
            _, ext = os.path.splitext(code_file.lower())
            if ext == '.sql':
                if blob_sha and blob_sha in cls.SQL_CACHE:
                    detected_lang = cls.SQL_CACHE[blob_sha]
                elif content_getter and blob_sha:
                    try:
                        content = content_getter(blob_sha)
                        detected_lang = cls.detect_sql_dialect(content)
                        cls.SQL_CACHE[blob_sha] = detected_lang
                    except Exception:
                        detected_lang = 'MySQL'
                else:
                    detected_lang = 'MySQL'
            else:
                detected_lang = cls.LANGUAGE_EXTENSIONS.get(ext)


        # Case A: Top directory is language, sub directory is platform
        if top_dir not in cls.PLATFORMS and len(sub_parts) >= 1 and sub_parts[0] in cls.PLATFORMS:
            lang = detected_lang if detected_lang else top_dir
            platform = sub_parts[0]
            rel_path_parts = sub_parts[1:]
        # Case B: Top directory is platform (e.g. 백준/Bronze/...)
        elif top_dir in cls.PLATFORMS:
            platform = top_dir
            lang = detected_lang if detected_lang else 'Python'
            rel_path_parts = sub_parts

        else:
            # Unrecognized pattern, return unchanged
            return path




        # Normalize Programmers level folders to strictly match BaekjoonHub's actual behavior (e.g., 'lv1' -> '1')
        if platform == '프로그래머스' and rel_path_parts:
            level_dir = rel_path_parts[0]
            if level_dir.lower().startswith('lv'):
                digits = level_dir[2:]
                if digits.isdigit():
                    rel_path_parts[0] = digits


        if mode == 'platform_first':
            # Format: <Platform>/<Remaining_Path>
            new_parts = [platform] + rel_path_parts
        elif mode == 'language_first':
            # Format: <Language>/<Platform>/<Remaining_Path>
            new_parts = [lang, platform] + rel_path_parts
        elif mode == 'flat':
            # Simplifies folder names by removing invisible spaces or extra nesting
            clean_rel_parts = [re.sub(r'[\u2000-\u200f\u205f\u3000]', '', p) for p in rel_path_parts]
            new_parts = [platform] + clean_rel_parts
        else:
            new_parts = parts


        return '/'.join(new_parts)


class GitRewriter:
    """Rewrites Git history using plumbing commands to preserve commit metadata."""

    def __init__(self, repo_dir: str):
        """Initialize GitRewriter with target repository directory.

        Args:
            repo_dir: Absolute path to the Git repository.
        """
        self.repo_dir = repo_dir

    def _run_git(self, args: List[str], env: Optional[Dict[str, str]] = None, input_str: Optional[str] = None) -> str:
        """Execute a git plumbing command and return output.

        Args:
            args: Command arguments for git.
            env: Custom environment variables.
            input_str: Input text to send to stdin.

        Returns:
            Command stdout output as string.

        Raises:
            subprocess.CalledProcessError: If git command fails.
        """
        full_env = os.environ.copy()
        full_env['LC_ALL'] = 'C.UTF-8'
        full_env['GIT_OPTIONAL_LOCKS'] = '0'
        if env:
            full_env.update(env)

        cmd = ['git', '-C', self.repo_dir] + args
        res = subprocess.run(
            cmd,
            input=input_str,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='replace',
            env=full_env,
            check=True
        )
        return res.stdout

    def create_backup_branch(self, branch_name: str = 'backup-before-migration') -> None:
        """Create a safety backup branch before starting history rewrite.

        Args:
            branch_name: Name of the backup branch.
        """
        try:
            self._run_git(['branch', '-D', branch_name])
        except subprocess.CalledProcessError:
            pass
        self._run_git(['branch', branch_name])
        print(f"[+] Backup branch created: '{branch_name}'")

    def get_commit_list(self) -> List[str]:
        """Fetch list of all commits in chronological order (oldest first).

        Returns:
            List of commit SHAs.
        """
        out = self._run_git(['log', '--reverse', '--format=%H'])
        return [line.strip() for line in out.splitlines() if line.strip()]

    def get_commit_meta(self, commit_sha: str) -> Dict[str, str]:
        """Extract exact author, committer, and message metadata for a commit.

        Args:
            commit_sha: SHA of the target commit.

        Returns:
            Dictionary containing commit metadata.
        """
        # Format specifiers: %an, %ae, %at, %cn, %ce, %ct, %B
        sep = '---COMMIT_META_SEP---'
        fmt = f'%an{sep}%ae{sep}%at{sep}%cn{sep}%ce{sep}%ct{sep}%B'
        raw = self._run_git(['log', '-1', f'--format={fmt}', commit_sha])
        parts = raw.split(sep)
        return {
            'an': parts[0],
            'ae': parts[1],
            'at': parts[2],
            'cn': parts[3],
            'ce': parts[4],
            'ct': parts[5],
            'msg': parts[6] if len(parts) > 6 else ''
        }

    def get_ls_tree(self, commit_sha: str) -> List[Tuple[str, str, str, str]]:
        """List all files in the given commit tree.

        Args:
            commit_sha: SHA of the target commit.

        Returns:
            List of tuples (mode, type, sha, path).
        """
        raw = self._run_git(['ls-tree', '-r', '-z', commit_sha])
        entries = []
        for line in raw.split('\0'):
            if not line:
                continue
            # Format: <mode> <type> <sha>\t<path>
            meta, path = line.split('\t', 1)
            mode, item_type, sha = meta.split()
            entries.append((mode, item_type, sha, path))
        return entries

    def get_blob_content(self, blob_sha: str) -> str:
        """Fetch content of a blob by its SHA.

        Args:
            blob_sha: Git blob SHA.

        Returns:
            Content string.
        """
        return self._run_git(['cat-file', '-p', blob_sha])

    def preview_migration(self, mode: str) -> None:
        """Preview path changes for the latest commit tree.

        Args:
            mode: Migration mode.
        """
        commits = self.get_commit_list()
        if not commits:
            print("[-] No commits found in repository.")
            return

        latest_sha = commits[-1]
        entries = self.get_ls_tree(latest_sha)
        
        print("\n" + "=" * 60)
        print(f" DRY-RUN PREVIEW (Mode: {mode})")
        print("=" * 60)
        changed_count = 0
        for _, item_type, blob_sha, path in entries[:20]:  # Show first 20 sample files
            new_path = PathMapper.transform_path(path, mode, content_getter=self.get_blob_content, blob_sha=blob_sha)
            if new_path != path:
                print(f" [MOVE] {path}\n     -> {new_path}")
                changed_count += 1
            else:
                print(f" [KEEP] {path}")

        total_files = len(entries)
        print(f"\nSample preview completed. ({changed_count} files moved out of first 20 shown, {total_files} total files)")
        print("=" * 60 + "\n")

    def execute_rewrite(self, mode: str, target_branch: str = 'main') -> None:
        """Execute history rewrite preserving original timestamps and commit messages.

        Args:
            mode: Migration mode selected by user.
            target_branch: Target branch to update after rewriting.
        """
        commits = self.get_commit_list()
        if not commits:
            print("[-] No commits to process.")
            return

        print(f"[+] Starting Git history rewrite for {len(commits)} commits...")
        self.create_backup_branch()

        commit_map: Dict[str, str] = {}  # old_commit_sha -> new_commit_sha
        parent_new_sha: Optional[str] = None
        tmp_index_file = os.path.join(self.repo_dir, '.git', 'migrator_tmp_index')

        try:
            for idx, old_sha in enumerate(commits, start=1):
                meta = self.get_commit_meta(old_sha)
                ls_entries = self.get_ls_tree(old_sha)

                # Clean up temporary index file
                if os.path.exists(tmp_index_file):
                    os.remove(tmp_index_file)

                index_env = {'GIT_INDEX_FILE': tmp_index_file}

                # Build batch input for git update-index -z --index-info
                # Format: <mode> SP <sha> TAB <path> NUL
                index_info_lines = []
                for item_mode, item_type, blob_sha, old_path in ls_entries:
                    if item_type != 'blob':
                        continue
                    new_path = PathMapper.transform_path(old_path, mode, content_getter=self.get_blob_content, blob_sha=blob_sha)
                    index_info_lines.append(f"{item_mode} {blob_sha}\t{new_path}")

                if index_info_lines:
                    batch_input = '\0'.join(index_info_lines) + '\0'
                    self._run_git(['update-index', '-z', '--index-info'], env=index_env, input_str=batch_input)




                # Generate new tree sha from temporary index
                new_tree_sha = self._run_git(['write-tree'], env=index_env).strip()

                # Environment variables for commit creation (preserving original dates and authors)
                commit_env = {
                    'GIT_AUTHOR_NAME': meta['an'],
                    'GIT_AUTHOR_EMAIL': meta['ae'],
                    'GIT_AUTHOR_DATE': meta['at'],
                    'GIT_COMMITTER_NAME': meta['cn'],
                    'GIT_COMMITTER_EMAIL': meta['ce'],
                    'GIT_COMMITTER_DATE': meta['ct'],
                }

                # Build commit-tree arguments
                cmd_args = ['commit-tree', new_tree_sha]
                if parent_new_sha:
                    cmd_args.extend(['-p', parent_new_sha])

                new_commit_sha = self._run_git(cmd_args, env=commit_env, input_str=meta['msg']).strip()

                commit_map[old_sha] = new_commit_sha
                parent_new_sha = new_commit_sha

                if idx % 50 == 0 or idx == len(commits):
                    print(f" Progress: [{idx}/{len(commits)}] commits processed.")


        finally:
            if os.path.exists(tmp_index_file):
                try:
                    os.remove(tmp_index_file)
                except OSError:
                    pass

        # Point target branch to the newly rewritten commit chain
        current_branch = self._run_git(['rev-parse', '--abbrev-ref', 'HEAD']).strip()
        if current_branch == 'HEAD':
            current_branch = target_branch

        self._run_git(['update-ref', f'refs/heads/{current_branch}', parent_new_sha])
        self._run_git(['checkout', '-f', current_branch])

        print(f"\n[+] Migration successfully finished! Branch '{current_branch}' now points to rewritten history.")
        print("[+] Original history backed up in 'backup-before-migration'.")



def main():
    """Main CLI entry point for BaekjoonHub Migration Tool."""
    parser = argparse.ArgumentParser(
        description="BaekjoonHub Repository Migration Tool (Preserving Commit History & Timestamps)"
    )
    parser.add_argument(
        '--repo',
        type=str,
        default=os.getcwd(),
        help="Path to the target Git repository (default: current directory)"
    )
    parser.add_argument(
        '--mode',
        type=str,
        choices=['platform_first', 'language_first', 'flat'],
        help="Migration mode: 'platform_first', 'language_first', or 'flat'"
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help="Preview changes without Modifying Git history"
    )

    args = parser.parse_args()

    repo_dir = os.path.abspath(args.repo)
    if not os.path.exists(os.path.join(repo_dir, '.git')):
        print(f"[*] Note: '{repo_dir}' is not a Git repository.")
        user_repo = input("Please enter the path to target Git repository: ").strip().strip('"').strip("'")
        if user_repo:
            repo_dir = os.path.abspath(user_repo)

    if not os.path.exists(os.path.join(repo_dir, '.git')):
        print(f"[-] Error: '{repo_dir}' is not a valid Git repository.")
        sys.exit(1)


    rewriter = GitRewriter(repo_dir)

    # Interactive mode if arguments are missing
    selected_mode = args.mode
    if not selected_mode:
        print("=" * 60)
        print(" BaekjoonHub Migration Tool ")
        print("=" * 60)
        print("Select target migration layout:")
        print("  1. Platform-first (e.g. 백준/Bronze/..., 프로그래머스/lv1/...)")
        print("  2. Language-first (e.g. Python3/백준/..., Java/프로그래머스/...)")
        print("  3. Flat custom (Clean invisible space characters)")
        print("=" * 60)

        choice = input("Enter choice (1-3): ").strip()
        mode_map = {'1': 'platform_first', '2': 'language_first', '3': 'flat'}
        selected_mode = mode_map.get(choice, 'platform_first')

    if args.dry_run:
        rewriter.preview_migration(selected_mode)
        return

    # Interactive confirmation if dry-run wasn't specified via CLI
    rewriter.preview_migration(selected_mode)
    confirm = input("Do you want to proceed with rewriting Git history? (y/N): ").strip().lower()
    if confirm == 'y':
        rewriter.execute_rewrite(selected_mode)
    else:
        print("[-] Operation cancelled by user.")


if __name__ == '__main__':
    main()
