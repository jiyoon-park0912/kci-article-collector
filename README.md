# KCI 논문 수집기 (Streamlit)

학술지명과 발행연도를 기준으로 KCI Open API를 호출하고, 반환된 학술지명을 검증한 후 국문 초록을 CSV/Excel로 저장하는 웹앱입니다.

## 시작하기 (내 컴퓨터)

1. Python 3.10 이상을 설치합니다.
2. 이 폴더에서 `pip install -r requirements.txt` 실행
3. `.streamlit/secrets.toml.example` 파일을 복사해 `.streamlit/secrets.toml`로 저장하고 `KCI_API_KEY` 값을 본인 인증키로 설정합니다. **secrets.toml을 GitHub에 업로드하지 마세요.**
4. `streamlit run app.py` 실행
5. 브라우저에서 표시된 로컬 주소로 접속합니다.

로컬 secrets 파일 없이 앱에서 인증키를 직접 입력할 수도 있지만, 공유 배포에서는 서버 비밀정보로 설정하는 것을 권장합니다.

## Streamlit Community Cloud에 배포

1. GitHub 저장소에 `app.py`, `kci_client.py`, `requirements.txt`, `.gitignore`를 업로드합니다. **인증키가 들어 있는 파일은 업로드하지 않습니다.**
2. https://share.streamlit.io 에서 **Create app**을 선택한 다음 저장소와 `app.py`를 지정합니다.
3. 배포 설정의 **Secrets** 항목에 아래 값을 등록합니다.

```toml
KCI_API_KEY = "YOUR_NEW_PRIVATE_KEY"
```

4. 앱 배포 후 링크를 연구실 구성원과 공유합니다. 이용 약관, 호출 제한, 재배포 범위 및 공유키 사용 허용 여부를 먼저 확인하세요.

## 데이터 수집 규칙

- `journal`, `dateFrom`(YYYYMM), `dateTo`(YYYYMM), `page`, `displayCount=100`으로 API 호출
- XML의 `journal-name`이 사용자가 입력한 이름과 **정확히 일치**해야 다운로드 가능
- 국문 초록은 `abstract lang="original"` 텍스트에 한글 완성형이 포함된 경우로 임시 판별; 혼합/비표준 초록은 후속 검토 필요
- 논문 ID 기준 중복 제거, 발행연도 이중 검증
- API가 전체 검색 건수를 반환하더라도 해당 학술지의 **전수 보장 아님**
- '전체 검색 결과 조회 완료'는 API가 응답한 해당 검색어의 페이지를 모두 확인했다는 뜻이지 특정 학술지의 전체 논문 확보를 뜻하지 않습니다.

## 주의 사항

- KCI Open API 공식 서비스가 아닙니다.
- 인증키를 코드에 넣거나 GitHub에 올리지 마세요. 기존에 대화·로그로 노출한 인증키는 재발급을 권장합니다.
- 연구실 공유 전 API 호출량/동시접속/초록의 저장 및 재배포 가능 범위를 확인하세요.
- 검색어가 유사한 학술지의 논문을 함께 반환할 수 있으며, 사후 필터링으로 검색 누락 문제까지 해결되는 것은 아닙니다.
- 서버 키를 설정한 공개 웹앱은 제3자가 같은 키로 요청을 유발할 수 있습니다. 연구실 내부 전용 또는 인증·사용량 제한을 갖춘 환경에서만 운영하세요.
