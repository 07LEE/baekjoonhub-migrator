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
import tempfile
import shutil
from datetime import datetime
from typing import Dict, List, Tuple, Optional


def is_remote_url(path: str) -> bool:
    """Check if the provided path is a remote Git repository URL.

    Supports HTTP, HTTPS, SSH, and git protocols.
    """
    return path.startswith(('http://', 'https://', 'git@', 'ssh://'))


def is_git_repo(path: str) -> bool:
    """Check if the directory is a valid Git repository (supports bare repos & worktrees)."""
    try:
        res = subprocess.run(
            ['git', '-C', path, 'rev-parse', '--git-dir'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True
        )
        return res.returncode == 0
    except Exception:
        return False


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
            Language folder name or 'Misc'.
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
        oracle_keywords = [
            r'\bNVL\b', r'\bSYSDATE\b', r'\bTO_CHAR\b', r'\bTO_DATE\b',
            r'\bDECODE\b', r'\bROWNUM\b', r'\bVARCHAR2\b', r'\bCONNECT\s+BY\b'
        ]
        mysql_keywords = [
            r'\bIFNULL\b', r'\bDATE_FORMAT\b', r'\bNOW\s*\(', r'\bLIMIT\b',
            r'\bCONCAT\b', r'\bGROUP_CONCAT\b'
        ]

        for kw in oracle_keywords:
            if re.search(kw, upper_content):
                return 'Oracle'
        for kw in mysql_keywords:
            if re.search(kw, upper_content):
                return 'MySQL'
        return 'MySQL'

    @classmethod
    def transform_path(cls, path: str, mode: str, content_getter=None, blob_sha: str = None, folder_lang_map: Optional[Dict[str, str]] = None) -> str:
        """Transform a file path according to the selected migration mode.

        Args:
            path: Original relative file path in the repository.
            mode: Migration mode ('platform_first', 'language_first', 'flat').
            content_getter: Optional callable to fetch blob content by sha.
            blob_sha: Git blob SHA of the file.
            folder_lang_map: Optional map of parent_directory -> detected_language.

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

        # Helper to detect exact language from code file extension (inspect ONLY the filename, not parent directories)
        filename = parts[-1]
        code_file = filename if (filename.lower() != 'readme.md' and os.path.splitext(filename)[1]) else None

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

        # Fallback to folder_lang_map if language isn't directly detected from this file
        if not detected_lang and folder_lang_map and len(parts) > 1:
            if top_dir not in cls.PLATFORMS and len(sub_parts) >= 1 and sub_parts[0] in cls.PLATFORMS:
                problem_key = '/'.join(sub_parts[:-1])
            else:
                problem_key = '/'.join(parts[:-1])
            detected_lang = folder_lang_map.get(problem_key)

        # Case A: Top directory is language, sub directory is platform
        if top_dir not in cls.PLATFORMS and len(sub_parts) >= 1 and sub_parts[0] in cls.PLATFORMS:
            lang = detected_lang if detected_lang else top_dir
            platform = sub_parts[0]
            rel_path_parts = sub_parts[1:]

        # Case B: Top directory is platform (e.g. 백준/Bronze/...)
        elif top_dir in cls.PLATFORMS:
            platform = top_dir
            lang = detected_lang if detected_lang else 'Misc'
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
            new_parts = [platform] + rel_path_parts
        else:
            new_parts = parts

        return '/'.join(new_parts)


def unescape_path(path_str: str) -> str:
    """Unescape C-style quoted git fast-export path strings."""
    if len(path_str) >= 2 and path_str.startswith('"') and path_str.endswith('"'):
        inner = path_str[1:-1]
        res = bytearray()
        i = 0
        n = len(inner)
        while i < n:
            if inner[i] == '\\' and i + 1 < n:
                nxt = inner[i + 1]
                if nxt.isdigit() and i + 3 < n and inner[i + 2].isdigit() and inner[i + 3].isdigit():
                    oct_val = int(inner[i + 1:i + 4], 8)
                    res.append(oct_val)
                    i += 4
                else:
                    escapes = {'n': 10, 't': 9, 'v': 11, 'b': 8, 'r': 13, 'f': 12, 'a': 7, '\\': 92, '"': 34}
                    res.append(escapes.get(nxt, ord(nxt)))
                    i += 2
            else:
                res.append(ord(inner[i]))
                i += 1
        return res.decode('utf-8', errors='replace')
    return path_str


def escape_path(path_str: str) -> str:
    """Escape path for Git fast-import stream format following C-style escaping rules."""
    path_bytes = path_str.encode('utf-8')
    needs_quoting = any(b <= 32 or b >= 127 or b in (34, 92) for b in path_bytes)
    if not needs_quoting:
        return path_str

    escaped = '"'
    for b in path_bytes:
        if b == 34:  # quote "
            escaped += '\\"'
        elif b == 92:  # backslash \
            escaped += '\\\\'
        elif b == 10:  # newline \n
            escaped += '\\n'
        elif b == 9:  # tab \t
            escaped += '\\t'
        elif b <= 32 or b >= 127:
            escaped += f'\\{b:03o}'
        else:
            escaped += chr(b)
    escaped += '"'
    return escaped




def read_exact(stream, size: int) -> bytes:
    """Read exactly size bytes from a stream.

    Args:
        stream: Stream object.
        size: Number of bytes to read.

    Returns:
        Exact bytes read.

    Raises:
        EOFError: If EOF is reached before size bytes are read.
    """
    buf = bytearray()
    while len(buf) < size:
        chunk = stream.read(size - len(buf))
        if not chunk:
            raise EOFError(f"Unexpected EOF while reading {size} bytes (read {len(buf)} bytes)")
        buf.extend(chunk)
    return bytes(buf)


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

    def create_backup_branch(self, base_name: str = 'backup-before-migration') -> str:
        """Create a safety backup branch before starting history rewrite, preserving old backups.

        Args:
            base_name: Base name for the backup branch.

        Returns:
            The created backup branch name.
        """
        branch_name = base_name
        existing_branches = self._run_git(['branch', '--list', base_name]).strip()
        if existing_branches:
            timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
            branch_name = f"{base_name}-{timestamp}"

        self._run_git(['branch', branch_name])
        print(f"[+] Backup branch created: '{branch_name}'")
        return branch_name

    def get_commit_list(self) -> List[str]:
        """Fetch list of all commits in chronological order (oldest first).

        Returns:
            List of commit SHAs.
        """
        out = self._run_git(['log', '--reverse', '--format=%H'])
        return [line.strip() for line in out.splitlines() if line.strip()]

    def get_commit_meta(self, commit_sha: str) -> Dict[str, str]:
        """Extract exact author, committer, dates (with raw offset), parents, and message metadata.

        Args:
            commit_sha: SHA of the target commit.

        Returns:
            Dictionary containing commit metadata.
        """
        sep = '---COMMIT_META_SEP---'
        fmt = f'%an{sep}%ae{sep}%ad{sep}%cn{sep}%ce{sep}%cd{sep}%P{sep}%B'
        raw = self._run_git(['log', '-1', '--date=raw', f'--format={fmt}', commit_sha])
        parts = raw.split(sep)
        msg = parts[7] if len(parts) > 7 else ''
        return {
            'an': parts[0],
            'ae': parts[1],
            'ad': parts[2],
            'cn': parts[3],
            'ce': parts[4],
            'cd': parts[5],
            'parents': parts[6].split() if parts[6].strip() else [],
            'msg': msg.rstrip('\r\n') + '\n'
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

    def detect_collisions(self, entries: List[Tuple[str, str, str, str]], mode: str) -> Dict[str, List[str]]:
        """Detect path collisions where multiple old paths map to the same target path.

        Returns:
            Mapping of target_path -> list of original_paths.
        """
        folder_lang_map = self.build_folder_lang_map(entries, content_getter=self.get_blob_content)
        mapped: Dict[str, List[str]] = {}
        for item_mode, item_type, blob_sha, old_path in entries:
            if item_type != 'blob':
                continue
            new_path = PathMapper.transform_path(
                old_path, mode,
                content_getter=self.get_blob_content,
                blob_sha=blob_sha,
                folder_lang_map=folder_lang_map
            )
            mapped.setdefault(new_path, []).append(old_path)

        return {k: v for k, v in mapped.items() if len(v) > 1}

    def build_folder_lang_map(self, entries: List[Tuple[str, str, str, str]], content_getter=None) -> Dict[str, str]:
        """Build mapping of normalized problem_directory -> detected_language from tree entries."""
        folder_map: Dict[str, str] = {}
        for item_mode, item_type, blob_sha, old_path in entries:
            if item_type != 'blob':
                continue
            parts = [p for p in old_path.replace('\\', '/').split('/') if p]
            if len(parts) <= 1:
                continue
            filename = parts[-1]
            if filename.lower() == 'readme.md':
                continue
            _, ext = os.path.splitext(filename.lower())
            if not ext:
                continue

            top_dir = parts[0]
            sub_parts = parts[1:]
            if top_dir not in PathMapper.PLATFORMS and len(sub_parts) >= 1 and sub_parts[0] in PathMapper.PLATFORMS:
                problem_key = '/'.join(sub_parts[:-1])
            else:
                problem_key = '/'.join(parts[:-1])

            lang = None
            if ext == '.sql':
                if blob_sha and blob_sha in PathMapper.SQL_CACHE:
                    lang = PathMapper.SQL_CACHE[blob_sha]
                elif content_getter and blob_sha:
                    try:
                        content = content_getter(blob_sha)
                        lang = PathMapper.detect_sql_dialect(content)
                        PathMapper.SQL_CACHE[blob_sha] = lang
                    except Exception:
                        lang = 'MySQL'
                else:
                    lang = 'MySQL'
            else:
                lang = PathMapper.LANGUAGE_EXTENSIONS.get(ext)

            if lang and problem_key not in folder_map:
                folder_map[problem_key] = lang
        return folder_map


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
        folder_lang_map = self.build_folder_lang_map(entries, content_getter=self.get_blob_content)

        collisions = self.detect_collisions(entries, mode)
        if collisions:
            print("\n[!] WARNING: PATH COLLISIONS DETECTED!")
            for target_path, orig_paths in collisions.items():
                print(f"    Target: '{target_path}' <= {orig_paths}")
            print("    (Note: During rewrite, git update-index will overwrite colliding paths with the last entry.)\n")

        print("\n" + "=" * 60)
        print(f" DRY-RUN PREVIEW (Mode: {mode})")
        print("=" * 60)
        changed_count = 0
        for _, item_type, blob_sha, path in entries[:20]:  # Show first 20 sample files
            new_path = PathMapper.transform_path(
                path, mode,
                content_getter=self.get_blob_content,
                blob_sha=blob_sha,
                folder_lang_map=folder_lang_map
            )
            if new_path != path:
                print(f" [MOVE] {path}\n     -> {new_path}")
                changed_count += 1
            else:
                print(f" [KEEP] {path}")

        total_files = len(entries)
        print(f"\nSample preview completed. ({changed_count} files moved out of first 20 shown, {total_files} total files)")
        print("=" * 60 + "\n")

    def execute_rewrite(self, mode: str, target_branch: str = 'main') -> None:
        """Execute history rewrite using fast-export / fast-import pipeline, matching C++ implementation.

        Args:
            mode: Migration mode selected by user.
            target_branch: Target branch to update after rewriting.
        """
        current_branch = self._run_git(['rev-parse', '--abbrev-ref', 'HEAD']).strip()
        if current_branch == 'HEAD' or not current_branch:
            current_branch = target_branch

        print(f"[+] Starting Git history rewrite for branch '{current_branch}'...")
        backup_branch = self.create_backup_branch()

        export_cmd = ['git', '-C', self.repo_dir, 'fast-export', current_branch]
        import_cmd = ['git', '-C', self.repo_dir, 'fast-import', '--force', '--quiet']

        proc_export = subprocess.Popen(export_cmd, stdout=subprocess.PIPE, bufsize=-1)
        proc_import = subprocess.Popen(import_cmd, stdin=subprocess.PIPE, bufsize=-1)

        exp_stdout = proc_export.stdout
        imp_stdin = proc_import.stdin

        sql_blob_cache: Dict[str, str] = {}
        path_dialect_cache: Dict[str, str] = {}
        folder_lang_map: Dict[str, str] = {}
        commit_file_lines: List[Tuple[str, str, str, str, bytes]] = []
        state = 'FREE'
        blob_mark = ''
        pending_bytes = b''

        def get_blob_content_from_cache(ref: str) -> str:
            return sql_blob_cache.get(ref, '')

        def flush_commit_file_lines() -> None:
            nonlocal commit_file_lines
            if not commit_file_lines:
                return

            # Pass 1: Scan all code files in this commit to update folder_lang_map
            for action_type, fmode, dataref, orig_path, line_bytes in commit_file_lines:
                if action_type == 'M' and orig_path:
                    parts = [p for p in orig_path.replace('\\', '/').split('/') if p]
                    if len(parts) > 1 and parts[-1].lower() != 'readme.md':
                        filename = parts[-1]
                        _, ext = os.path.splitext(filename.lower())
                        if ext:
                            top_dir = parts[0]
                            sub_parts = parts[1:]
                            if top_dir not in PathMapper.PLATFORMS and len(sub_parts) >= 1 and sub_parts[0] in PathMapper.PLATFORMS:
                                problem_key = '/'.join(sub_parts[:-1])
                            else:
                                problem_key = '/'.join(parts[:-1])

                            if ext == '.sql':
                                c_text = get_blob_content_from_cache(dataref)
                                l_found = PathMapper.detect_sql_dialect(c_text) if c_text else 'MySQL'
                            else:
                                l_found = PathMapper.LANGUAGE_EXTENSIONS.get(ext)
                            if l_found:
                                folder_lang_map[problem_key] = l_found

            # Pass 2: Transform and write buffered lines using updated folder_lang_map
            for action_type, fmode, dataref, orig_path, line_bytes in commit_file_lines:
                if action_type == 'M':
                    new_path = PathMapper.transform_path(
                        orig_path, mode,
                        content_getter=get_blob_content_from_cache,
                        blob_sha=dataref,
                        folder_lang_map=folder_lang_map
                    )
                    if orig_path.lower().endswith('.sql') and dataref in PathMapper.SQL_CACHE:
                        path_dialect_cache[orig_path] = PathMapper.SQL_CACHE[dataref]

                    escaped_new = escape_path(new_path)
                    new_line = f"M {fmode} {dataref} {escaped_new}\n"
                    imp_stdin.write(new_line.encode('utf-8'))
                elif action_type == 'D':
                    cached_dialect = path_dialect_cache.get(orig_path)
                    if cached_dialect:
                        PathMapper.SQL_CACHE['__path__' + orig_path] = cached_dialect
                        new_path = PathMapper.transform_path(
                            orig_path, mode,
                            blob_sha='__path__' + orig_path,
                            folder_lang_map=folder_lang_map
                        )
                    else:
                        new_path = PathMapper.transform_path(
                            orig_path, mode,
                            folder_lang_map=folder_lang_map
                        )
                    escaped_new = escape_path(new_path)
                    new_line = f"D {escaped_new}\n"
                    imp_stdin.write(new_line.encode('utf-8'))
                else:
                    imp_stdin.write(line_bytes)

            commit_file_lines.clear()

        def read_next_line() -> bytes:
            nonlocal pending_bytes
            if pending_bytes:
                line = pending_bytes + exp_stdout.readline()
                pending_bytes = b''
                return line
            return exp_stdout.readline()


        try:
            while True:
                line_bytes = read_next_line()
                if not line_bytes:
                    break
                line_str = line_bytes.decode('utf-8', errors='replace')

                if state == 'FREE':
                    if line_str.startswith('blob\n'):
                        imp_stdin.write(line_bytes)
                        state = 'BLOB_MARK'
                    elif line_str.startswith('commit '):
                        imp_stdin.write(line_bytes)
                        state = 'COMMIT'
                    else:
                        imp_stdin.write(line_bytes)

                elif state == 'BLOB_MARK':
                    imp_stdin.write(line_bytes)
                    if line_str.startswith('mark '):
                        blob_mark = line_str[5:].strip()
                        state = 'BLOB_DATA_HEADER'
                    else:
                        blob_mark = ''
                        state = 'FREE'

                elif state == 'BLOB_DATA_HEADER':
                    imp_stdin.write(line_bytes)
                    if line_str.startswith('data '):
                        size = int(line_str[5:].strip())
                        content_bytes = read_exact(exp_stdout, size)
                        imp_stdin.write(content_bytes)
                        nl = exp_stdout.read(1)
                        if nl:
                            if nl == b'\n':
                                imp_stdin.write(nl)
                            else:
                                pending_bytes = nl
                        if blob_mark and size < 1024 * 1024:
                            sql_blob_cache[blob_mark] = content_bytes.decode('utf-8', errors='replace')
                        blob_mark = ''
                        state = 'FREE'
                    else:
                        state = 'FREE'

                elif state == 'COMMIT':
                    if line_str.startswith('data '):
                        imp_stdin.write(line_bytes)
                        size = int(line_str[5:].strip())
                        msg_bytes = read_exact(exp_stdout, size)
                        imp_stdin.write(msg_bytes)
                        nl = exp_stdout.read(1)
                        if nl:
                            if nl == b'\n':
                                imp_stdin.write(nl)
                            else:
                                pending_bytes = nl
                    elif line_str.startswith('M '):
                        rest = line_str[2:]
                        sp1 = rest.find(' ')
                        sp2 = rest.find(' ', sp1 + 1)
                        if sp1 != -1 and sp2 != -1:
                            fmode = rest[:sp1]
                            dataref = rest[sp1 + 1:sp2]
                            raw_path = rest[sp2 + 1:].strip()
                            orig_path = unescape_path(raw_path)
                            commit_file_lines.append(('M', fmode, dataref, orig_path, line_bytes))
                        else:
                            commit_file_lines.append(('RAW', '', '', '', line_bytes))
                    elif line_str.startswith('D '):
                        raw_path = line_str[2:].strip()
                        orig_path = unescape_path(raw_path)
                        commit_file_lines.append(('D', '', '', orig_path, line_bytes))
                    elif line_str.startswith('blob\n'):
                        flush_commit_file_lines()
                        imp_stdin.write(line_bytes)
                        state = 'BLOB_MARK'
                    elif line_str.startswith('commit '):
                        flush_commit_file_lines()
                        imp_stdin.write(line_bytes)
                        state = 'COMMIT'
                    elif line_str.startswith(('reset ', 'tag ', 'checkpoint\n')):
                        flush_commit_file_lines()
                        imp_stdin.write(line_bytes)
                        state = 'FREE'
                    elif line_str == '\n':
                        # Ignore trailing blank lines inside commit block until commit is flushed
                        pass
                    else:
                        imp_stdin.write(line_bytes)

            flush_commit_file_lines()
        finally:
            exp_stdout.close()

            imp_stdin.close()
            ret_exp = proc_export.wait()
            ret_imp = proc_import.wait()
            if ret_exp != 0 or ret_imp != 0:
                raise RuntimeError(
                    f"Git fast-export/import failed (export exit code: {ret_exp}, import exit code: {ret_imp})"
                )

        self._run_git(['checkout', '-f', current_branch])
        print(f"\n[+] Migration successfully finished! Branch '{current_branch}' now points to rewritten history.")
        print(f"[+] Original history backed up in '{backup_branch}'.")


def main():
    """Main CLI entry point for BaekjoonHub Migration Tool."""
    parser = argparse.ArgumentParser(
        description="BaekjoonHub Repository Migration Tool (Preserving Commit History & Timestamps)"
    )
    parser.add_argument(
        '--repo',
        type=str,
        default=os.getcwd(),
        help="Path or remote URL to the target Git repository (default: current directory)"
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
    parser.add_argument(
        '-y', '--yes',
        action='store_true',
        help="Skip interactive confirmation prompts"
    )

    args = parser.parse_args()

    repo_input = args.repo
    is_remote = False

    if is_remote_url(repo_input):
        is_remote = True
    else:
        repo_dir = os.path.abspath(repo_input)
        if not is_git_repo(repo_dir):
            if args.yes:
                print(f"[-] Error: '{repo_dir}' is not a valid Git repository.")
                sys.exit(1)
            print(f"[*] Note: '{repo_dir}' is not a Git repository.")
            user_repo = input("Please enter the path or URL to target Git repository: ").strip().strip('"').strip("'")
            if user_repo:
                if is_remote_url(user_repo):
                    is_remote = True
                    repo_input = user_repo
                else:
                    repo_dir = os.path.abspath(user_repo)

    if not is_remote and not is_git_repo(repo_dir):
        print(f"[-] Error: '{repo_dir}' is not a valid Git repository.")
        sys.exit(1)

    temp_dir_obj = None
    if is_remote:
        print(f"[+] Cloning remote repository from '{repo_input}'...")
        try:
            temp_dir_obj = tempfile.TemporaryDirectory(prefix='bjhub_migrator_')
            repo_dir = temp_dir_obj.name
            subprocess.run(['git', 'clone', repo_input, repo_dir], check=True)
            print("[+] Clone successfully completed.")
        except Exception as e:
            print(f"[-] Failed to clone remote repository: {e}")
            if temp_dir_obj:
                temp_dir_obj.cleanup()
            sys.exit(1)

    try:
        rewriter = GitRewriter(repo_dir)

        selected_mode = args.mode
        if not selected_mode:
            if args.yes:
                selected_mode = 'platform_first'
            else:
                print("=" * 60)
                print(" BaekjoonHub Migration Tool ")
                print("=" * 60)
                print("Select target migration layout:")
                print("  1. Platform-first (e.g. 백준/Bronze/..., 프로그래머스/lv1/...)")
                print("  2. Language-first (e.g. Python/백준/..., Java/프로그래머스/...)")
                print("=" * 60)

                choice = input("Enter choice (1-2): ").strip()
                mode_map = {'1': 'platform_first', '2': 'language_first'}
                selected_mode = mode_map.get(choice, 'platform_first')

        if args.dry_run:
            rewriter.preview_migration(selected_mode)
            return

        rewriter.preview_migration(selected_mode)
        if args.yes:
            confirm = 'y'
        else:
            confirm = input("Do you want to proceed with rewriting Git history? (y/N): ").strip().lower()

        if confirm == 'y':
            rewriter.execute_rewrite(selected_mode)

            if is_remote:
                if args.yes:
                    push_confirm = 'n'
                else:
                    print("\n" + "=" * 60)
                    print(" REMOTE PUSH CONFIRMATION")
                    print("=" * 60)
                    print("WARNING: Force pushing will overwrite the remote repository history.")
                    push_confirm = input("Do you want to force push the changes to remote? (y/N): ").strip().lower()

                if push_confirm == 'y':
                    try:
                        current_branch = rewriter._run_git(['rev-parse', '--abbrev-ref', 'HEAD']).strip()
                        print(f"[+] Force pushing rewritten branch '{current_branch}' to origin...")
                        rewriter._run_git(['push', '-f', 'origin', current_branch])
                        print("[+] Push completed successfully!")
                    except Exception as e:
                        print(f"[-] Failed to push to remote: {e}")
                else:
                    print("[-] Force push cancelled. Migrated repository remains in temporary directory:")
                    print(f"    {repo_dir}")
                    print("    (Note: This directory will be deleted when program exits)")
        else:
            print("[-] Operation cancelled by user.")

    finally:
        if temp_dir_obj:
            print("[+] Cleaning up temporary directory...")
            temp_dir_obj.cleanup()


if __name__ == '__main__':
    main()
