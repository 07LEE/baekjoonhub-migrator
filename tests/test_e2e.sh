#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TEST_TMP_DIR=$(mktemp -d)

cleanup() {
    rm -rf "${TEST_TMP_DIR}"
}
trap cleanup EXIT

echo "[+] Compiling C++ migration engine..."
BUILD_DIR="${TEST_TMP_DIR}/build"
mkdir -p "${BUILD_DIR}"
g++ -std=c++17 -O2 "${PROJECT_ROOT}/src/migrator.cpp" -o "${BUILD_DIR}/migrator"

MIGRATOR_BIN="${BUILD_DIR}/migrator"
FIXTURE_REPO="${TEST_TMP_DIR}/fixture_repo"

echo "[+] Constructing Git test fixture repository..."
mkdir -p "${FIXTURE_REPO}"
git -C "${FIXTURE_REPO}" init -q
git -C "${FIXTURE_REPO}" config user.name "Test User"
git -C "${FIXTURE_REPO}" config user.email "test@example.com"

# Commit 1: Initial commit with root README.md
echo "# Fixture Repo" > "${FIXTURE_REPO}/README.md"
git -C "${FIXTURE_REPO}" add README.md
git -C "${FIXTURE_REPO}" commit -m "Initial commit" -q

# Commit 2: Korean folder name with Unicode space (EN SPACE \u2005) & split README + CPP file
PROBLEM_DIR="${FIXTURE_REPO}/Python/백준/Bronze/2753. 윤년"
mkdir -p "${PROBLEM_DIR}"
echo "# 윤년 2753" > "${PROBLEM_DIR}/README.md"
git -C "${FIXTURE_REPO}" add "${PROBLEM_DIR}/README.md"
git -C "${FIXTURE_REPO}" commit -m "docs: add README for 2753" -q

echo "print('leap year')" > "${PROBLEM_DIR}/윤년.py"
echo "int main() { return 0; }" > "${PROBLEM_DIR}/윤년.cpp"
git -C "${FIXTURE_REPO}" add "${PROBLEM_DIR}/윤년.py" "${PROBLEM_DIR}/윤년.cpp"
git -C "${FIXTURE_REPO}" commit -m "feat: add solution for 2753" -q

# Commit 3: SQL Oracle & MySQL files
SQL_DIR="${FIXTURE_REPO}/Oracle/프로그래머스/1/131112. 강원도에 위치한 생산공장 목록 출력하기"
mkdir -p "${SQL_DIR}"
echo "SELECT FACTORY_ID FROM FOOD_FACTORY WHERE ADDRESS LIKE '강원도%';" > "${SQL_DIR}/강원도에 위치한 생산공장 목록 출력하기.sql"
echo "# SQL Factory List" > "${SQL_DIR}/README.md"
git -C "${FIXTURE_REPO}" add "${SQL_DIR}"
git -C "${FIXTURE_REPO}" commit -m "feat: add SQL solution" -q

# Commit 4: Large blob > 1MB
LARGE_FILE="${FIXTURE_REPO}/Python/백준/Silver/1000. A＋B/large_data.txt"
mkdir -p "$(dirname "${LARGE_FILE}")"
python3 -c "print('A' * (1024 * 1024 + 512))" > "${LARGE_FILE}"
git -C "${FIXTURE_REPO}" add "${LARGE_FILE}"
git -C "${FIXTURE_REPO}" commit -m "feat: add large data file" -q

echo "[+] Running C++ migration engine in language_first mode..."
"${MIGRATOR_BIN}" --repo "${FIXTURE_REPO}" --mode language_first -y

echo "[+] Verifying migration output integrity..."

# 1. Verify no literal backslashes in paths
PATHS=$(git -C "${FIXTURE_REPO}" ls-tree -r -z --name-only HEAD | tr '\0' '\n')
BAD_PATHS=$(echo "${PATHS}" | grep -F '\\355' || true)
if [ -n "${BAD_PATHS}" ]; then
    echo "[-] FAIL: Found literal escaped backslashes in paths:"
    echo "${BAD_PATHS}"
    exit 1
fi

# 2. Verify 2-pass README pairing (README.md must be placed in C++/ and Python/ alongside code)
ORPHAN_READMES=0
while IFS= read -r path; do
    if [[ "${path}" =~ /README\.md$ ]]; then
        dir_name=$(dirname "${path}")
        code_count=$(echo "${PATHS}" | grep "^${dir_name}/" | grep -v "/README\.md$" | wc -l)
        if [ "${code_count}" -eq 0 ]; then
            echo "[-] WARNING: Orphaned README found at ${path}"
            ORPHAN_READMES=$((ORPHAN_READMES + 1))
        fi
    fi
done <<< "${PATHS}"

if [ "${ORPHAN_READMES}" -gt 0 ]; then
    echo "[-] FAIL: Found ${ORPHAN_READMES} orphaned README files after migration."
    exit 1
fi

# 3. Verify Korean paths exist cleanly in UTF-8
if ! echo "${PATHS}" | grep -q "2753. 윤년"; then
    echo "[-] FAIL: Korean directory name with Unicode space missing or corrupted."
    exit 1
fi

echo "[+] E2E Test Passed Successfully! All checks clean."
