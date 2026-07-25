# 백준허브 오토푸시 마이그레이션 도구 (BaekjoonHub Migration Tool)

[BaekjoonHub](https://github.com/BaekjoonHub/BaekjoonHub)는 백준, 프로그래머스, SWEA 등의 알고리즘 문제 풀이를 해결하면 GitHub 리포지토리에 자동으로 소스코드와 문제 설명을 푸시해 주는 브라우저 확장 프로그램입니다.

본 도구는 BaekjoonHub를 사용하면서 오토푸시 설정이 변경되거나 시간이 지남에 따라 파편화된 디렉토리 구조(`Python3/프로그래머스`, `백준/...` 등)를 하나의 일관된 백준허브 표준 기준으로 통합 재정렬해 줍니다.

과거 커밋의 날짜, 시간, 작성자 및 커밋 메시지를 100% 보존하면서 파일 경로만 완벽하게 재정렬합니다.

## 주요 기능

1. Git 히스토리 타임라인 100% 보존
   - 과거 커밋의 제출 일시(`Author Date`, `Committer Date`), 작성자, 커밋 메시지 본문을 변경 없이 유지합니다.

2. 다양한 통합 디렉토리 레이아웃 지원
   - 플랫폼 중심 (Platform-first): `백준/...`, `프로그래머스/...`, `SWEA/...`로 흡수 통합
   - 언어 중심 (Language-first): `Python3/백준/...`, `Java/프로그래머스/...`로 통합

3. 프로그래머스 난이도 폴더명 백준허브 실제 표준(숫자 0, 1, 2, 3)으로 통합
   - BaekjoonHub 확장 프로그램의 실제 동작 규격인 단순 숫자 형태(`0`, `1`, `2`, `3`, `unrated`)로 100% 일치시켜 통일합니다.

4. 안전장치 (Dry-Run & 자동 백업)
   - 실행 전 변경 예정 목록을 미리 볼 수 있는 Dry-Run (시뮬레이션 모드) 지원
   - 실행 직전 원본 히스토리를 보관하는 백업 브랜치(`backup-before-migration`) 자동 생성

## 사용법

로컬 저장소 경로 외에 GitHub 등 원격 저장소 URL을 직접 지정하여 마이그레이션을 실행할 수도 있습니다. 원격 저장소를 지정할 경우, 자동으로 임시 폴더에 프로젝트를 복제하여 마이그레이션을 처리한 뒤 원격지에 강제 푸시할지 여부를 묻습니다.

### 1. 미리보기 (Dry-Run 모드)

실제 Git 히스토리를 변경하기 전에 어떤 파일이 어떻게 이동하는지 확인합니다.

로컬 저장소:

```bash
python migrator.py --repo /path/to/your/repository --mode platform_first --dry-run
```

원격 저장소:

```bash
python migrator.py --repo <원격 저장소 URL> --mode platform_first --dry-run
```

### 2. 마이그레이션 실행

대화형 메뉴에서 모드를 선택하고 실행합니다.

로컬 저장소:

```bash
python migrator.py --repo /path/to/your/repository
```

원격 저장소:

```bash
python migrator.py --repo <원격 저장소 URL>
```

### 3. GitHub 등 원격 리포지토리에 반영 (선택 사항)

Git 히스토리가 재작성되었으므로 원격 리포지토리(GitHub)에 반영할 때는 강제 푸시(`force push`)를 수행해야 합니다.

```bash
git push origin main --force
```

원격 저장소 URL로 실행한 경우에는 마이그레이션 완료 단계에서 나타나는 강제 푸시 확인 프롬프트(`y/N`)를 통해 자동으로 원격지에 반영되므로 이 단계를 건너뜁니다.

> [!CAUTION]
> 강제 푸시는 원격 리포지토리의 커밋 히스토리를 덮어씁니다. 마이그레이션 결과가 만족스러운지 local에서 충분히 확인한 후 진행하세요.
