#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TEST_TMP_DIR=$(mktemp -d)

cleanup() {
    rm -rf "${TEST_TMP_DIR}"
}
trap cleanup EXIT

echo "[+] Compiling C++ migration engine with C++20 standard..."
BUILD_DIR="${TEST_TMP_DIR}/build"
mkdir -p "${BUILD_DIR}"
g++ -std=c++20 -O2 "${PROJECT_ROOT}/src/migrator.cpp" -o "${BUILD_DIR}/migrator"

MIGRATOR_BIN="${BUILD_DIR}/migrator"
FIXTURE_REPO="${TEST_TMP_DIR}/fixture_repo"

echo "[+] Constructing Git test fixture repository..."
mkdir -p "${FIXTURE_REPO}"
git -C "${FIXTURE_REPO}" init -q -b main
git -C "${FIXTURE_REPO}" config user.name "Test User"
git -C "${FIXTURE_REPO}" config user.email "test@example.com"

# Commit 1: Initial commit with root README.md
echo "# Fixture Repo" > "${FIXTURE_REPO}/README.md"
git -C "${FIXTURE_REPO}" add README.md
GIT_COMMITTER_DATE="1666201641 +0900" GIT_AUTHOR_DATE="1666201641 +0900" \
git -C "${FIXTURE_REPO}" commit -m "Initial commit" -q

# Commit 2: Korean folder name with Unicode space (EN SPACE \u2005) & split README + CPP + PY files
PROBLEM_DIR="${FIXTURE_REPO}/Python/백준/Bronze/2753. 윤년"
mkdir -p "${PROBLEM_DIR}"
echo "# 윤년 2753" > "${PROBLEM_DIR}/README.md"
git -C "${FIXTURE_REPO}" add "${PROBLEM_DIR}/README.md"
GIT_COMMITTER_DATE="1666201700 +0900" GIT_AUTHOR_DATE="1666201700 +0900" \
git -C "${FIXTURE_REPO}" commit -m "docs: add README for 2753" -q

echo "print('leap year')" > "${PROBLEM_DIR}/윤년.py"
echo "int main() { return 0; }" > "${PROBLEM_DIR}/윤년.cpp"
git -C "${FIXTURE_REPO}" add "${PROBLEM_DIR}/윤년.py" "${PROBLEM_DIR}/윤년.cpp"
GIT_COMMITTER_DATE="1666201800 +0900" GIT_AUTHOR_DATE="1666201800 +0900" \
git -C "${FIXTURE_REPO}" commit -m "feat: add solution for 2753" -q

# Commit 3: Oracle SQL file (generic query, should preserve top_dir Oracle)
SQL_DIR="${FIXTURE_REPO}/Oracle/프로그래머스/1/131112. 강원도에 위치한 생산공장 목록 출력하기"
mkdir -p "${SQL_DIR}"
echo "SELECT FACTORY_ID FROM FOOD_FACTORY WHERE ADDRESS LIKE '강원도%';" > "${SQL_DIR}/강원도에 위치한 생산공장 목록 출력하기.sql"
echo "# SQL Factory List" > "${SQL_DIR}/README.md"
git -C "${FIXTURE_REPO}" add "${SQL_DIR}"
GIT_COMMITTER_DATE="1666201900 +0900" GIT_AUTHOR_DATE="1666201900 +0900" \
git -C "${FIXTURE_REPO}" commit -m "feat: add Oracle SQL solution" -q

# Commit 4: Large blob > 1MB
LARGE_FILE="${FIXTURE_REPO}/Python/백준/Silver/1000. A＋B/large_data.txt"
mkdir -p "$(dirname "${LARGE_FILE}")"
python3 -c "print('A' * (1024 * 1024 + 512))" > "${LARGE_FILE}"
git -C "${FIXTURE_REPO}" add "${LARGE_FILE}"
GIT_COMMITTER_DATE="1666202000 +0900" GIT_AUTHOR_DATE="1666202000 +0900" \
git -C "${FIXTURE_REPO}" commit -m "feat: add large data file" -q

# Commit 5: Create a feature branch & merge commit
git -C "${FIXTURE_REPO}" checkout -q -b feature-branch
echo "feature work" > "${FIXTURE_REPO}/feature.txt"
git -C "${FIXTURE_REPO}" add feature.txt
GIT_COMMITTER_DATE="1666202100 +0900" GIT_AUTHOR_DATE="1666202100 +0900" \
git -C "${FIXTURE_REPO}" commit -m "feat: add feature file" -q

git -C "${FIXTURE_REPO}" checkout -q main
GIT_COMMITTER_DATE="1666202200 +0900" GIT_AUTHOR_DATE="1666202200 +0900" \
git -C "${FIXTURE_REPO}" merge -q --no-ff feature-branch -m "Merge branch 'feature-branch'"

# Record pre-migration log & commit count
PRE_COMMIT_COUNT=$(git -C "${FIXTURE_REPO}" rev-list --count HEAD)
PRE_LOG_RAW=$(git -C "${FIXTURE_REPO}" log --date=raw --pretty=format:"%an <%ae> %ad | %cn <%ce> %cd | %s")

echo "[+] Running C++ migration engine in language_first mode with 120s timeout..."
timeout 120 "${MIGRATOR_BIN}" --repo "${FIXTURE_REPO}" --mode language_first -y

echo "[+] Verifying migration output integrity..."

# 1. Verify Commit Count & Metadata Raw Timestamps
POST_COMMIT_COUNT=$(git -C "${FIXTURE_REPO}" rev-list --count HEAD)
if [ "${PRE_COMMIT_COUNT}" -ne "${POST_COMMIT_COUNT}" ]; then
    echo "[-] FAIL: Commit count mismatch (pre: ${PRE_COMMIT_COUNT}, post: ${POST_COMMIT_COUNT})"
    exit 1
fi

POST_LOG_RAW=$(git -C "${FIXTURE_REPO}" log --date=raw --pretty=format:"%an <%ae> %ad | %cn <%ce> %cd | %s")
if [ "${PRE_LOG_RAW}" != "${POST_LOG_RAW}" ]; then
    echo "[-] FAIL: Commit author/committer timestamps or messages corrupted!"
    echo "Expected:"
    echo "${PRE_LOG_RAW}"
    echo "Got:"
    echo "${POST_LOG_RAW}"
    exit 1
fi

# 2. Verify Exact Expected Directory Tree 1-to-1
ACTUAL_TREE=$(git -C "${FIXTURE_REPO}" ls-tree -r -z --name-only HEAD | tr '\0' '\n' | sort)
EXPECTED_TREE=$(cat << 'EOF' | sort
C++/백준/Bronze/2753. 윤년/README.md
C++/백준/Bronze/2753. 윤년/윤년.cpp
Oracle/프로그래머스/1/131112. 강원도에 위치한 생산공장 목록 출력하기/README.md
Oracle/프로그래머스/1/131112. 강원도에 위치한 생산공장 목록 출력하기/강원도에 위치한 생산공장 목록 출력하기.sql
Python/백준/Bronze/2753. 윤년/README.md
Python/백준/Bronze/2753. 윤년/윤년.py
Python/백준/Silver/1000. A＋B/large_data.txt
README.md
feature.txt
EOF
)

if [ "${ACTUAL_TREE}" != "${EXPECTED_TREE}" ]; then
    echo "[-] FAIL: Actual directory tree does not match expected tree 1-to-1!"
    echo "=== EXPECTED TREE ==="
    echo "${EXPECTED_TREE}"
    echo "=== ACTUAL TREE ==="
    echo "${ACTUAL_TREE}"
    exit 1
fi

# 3. Verify no literal escaped backslashes in paths
BAD_PATHS=$(echo "${ACTUAL_TREE}" | grep -F '\\355' || true)
if [ -n "${BAD_PATHS}" ]; then
    echo "[-] FAIL: Found literal escaped backslashes in paths:"
    echo "${BAD_PATHS}"
    exit 1
fi

echo "[+] E2E Test Passed Successfully! All checks 100% clean."
