# 백준허브 오토푸시 마이그레이션 도구 (BaekjoonHub Migration Tool)

[언어: [English](../README.md) | [한국어](README.ko.md)]

[BaekjoonHub](https://github.com/BaekjoonHub/BaekjoonHub)로 자동 푸시된 리포지토리의 파편화된 디렉토리 구조(`Python3/프로그래머스`, `백준/...` 등)를 표준 통일 기준으로 재정렬하는 도구입니다.

커밋 날짜, 시간, 작성자, 커밋 메시지를 유지하면서 디렉토리 경로를 재배치합니다.

## 주요 기능

1. Git 히스토리 메타데이터 보존
   - 제출 일시(`Author Date`, `Committer Date`), 작성자, 커밋 메시지를 유지합니다.

2. 디렉토리 레이아웃 지원
   - 플랫폼 중심: `백준/...`, `프로그래머스/...`, `SWEA/...`
   - 언어 중심: `Python/백준/...`, `Java/프로그래머스/...`

3. 프로그래머스 난이도 폴더명 통일
   - 백준허브 동작 규격에 맞추어 `lv1` 형태의 폴더명을 숫자(`1`, `2`, `3`) 형태로 정규화합니다.

4. 실행 환경 (Python / C++)
   - Python 스크립트(`migrator.py`) 및 C++ 바이너리(`baekjoonhub-migrator`) 제공
   - 안전장치: Dry-Run 모드 및 실행 전 백업 브랜치(`backup-before-migration`) 자동 생성

## 사용법

### 1. C++ 바이너리 실행 (Releases 제공)

GitHub Release 페이지에서 OS별 실행 바이너리를 다운로드하여 실행합니다.

Linux:
```bash
chmod +x baekjoonhub-migrator-linux
./baekjoonhub-migrator-linux --repo /path/to/your/repository
```

macOS:
```bash
chmod +x baekjoonhub-migrator-macos
./baekjoonhub-migrator-macos --repo /path/to/your/repository
```

Windows:
```cmd
baekjoonhub-migrator-windows.exe --repo C:\path\to\your\repository
```

C++ 소스 직접 빌드 (CMake):
```bash
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release
./build/baekjoonhub-migrator --repo /path/to/your/repository
```

### 2. Python 스크립트 실행 (`migrator.py`)

Python 3 환경에서 스크립트를 직접 실행합니다.

#### 미리보기 (Dry-Run 모드)
```bash
python3 src/migrator.py --repo /path/to/your/repository --mode platform_first --dry-run
```

#### 마이그레이션 실행
```bash
python3 src/migrator.py --repo /path/to/your/repository
```

### 3. 원격 리포지토리 반영

Git 히스토리가 재작성되었으므로 원격 리포지토리에 반영하려면 강제 푸시(`force push`)가 필요합니다.

```bash
git push origin main --force
```

> [!CAUTION]
> 강제 푸시는 원격 히스토리를 덮어씁니다. 실행 전 로컬에서 결과를 충분히 확인하세요.
