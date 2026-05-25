"""
현대모비스 부품 가격 조회 스크립트 (프로토타입)

Playwright stealth 모드로 봇 감지를 우회하여 부품 가격을 조회한다.

사용법:
    python lookup_mobis.py --part-name "브레이크패드" --maker H --model 1544637
    python lookup_mobis.py --part-number "58101-1RA00" --maker H

파라미터:
    --maker: H(현대) 또는 K(기아)
    --vtyp: P(승용) 또는 C(상용). 기본값 P
    --model: catSeq 모델 코드 (일반검색 시 필수)
    --part-name: 한글 부품명 (일반검색)
    --part-number: 부품번호 (부품번호 검색)
"""

import re
import json
import sys
import time
import argparse
from playwright.sync_api import sync_playwright

# 요청 간 최소 대기 시간 (초) — 2초 이하면 실시간 봇 감지 발동
REQUEST_DELAY = 3.0


class MobisBlacklistError(Exception):
    """IP가 모비스 블랙리스트에 등록되었을 때 발생"""
    pass


def create_stealth_browser(playwright):
    """봇 감지를 우회하는 브라우저 컨텍스트 생성"""
    browser = playwright.chromium.launch(
        headless=True,
        args=[
            '--disable-blink-features=AutomationControlled',
            '--no-sandbox'
        ]
    )
    context = browser.new_context(
        user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        viewport={'width': 1920, 'height': 1080},
        locale='ko-KR'
    )
    page = context.new_page()
    page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'plugins', {
            get: () => [
                { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
                { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
                { name: 'Native Client', filename: 'internal-nacl-plugin' }
            ]
        });
        Object.defineProperty(navigator, 'languages', { get: () => ['ko-KR', 'ko', 'en-US', 'en'] });
        window.chrome = { runtime: {} };
    """)
    return browser, page


def check_blacklist(page) -> bool:
    """
    현재 세션이 블랙리스트 상태인지 확인. True면 차단됨.
    검색 AJAX를 한 번 보내서 응답의 black 필드로 판단한다.
    (메인 페이지 DOM의 layer_black은 항상 존재하는 템플릿이므로 사용하지 않는다)
    """
    try:
        # 가벼운 테스트 검색으로 블랙리스트 여부 확인
        resp = page.evaluate("""
            async () => {
                const resp = await fetch(
                    "/simple_search_partLoad_v2.do?pageIndex=1&hkgb=H&vtyp=P&catSeq=&srchType=ptno&inText=00000TEST",
                    { credentials: "same-origin", headers: { "X-Requested-With": "XMLHttpRequest" } }
                );
                return await resp.text();
            }
        """)
        is_blocked = check_blacklist_from_html(resp)
        # 테스트 쿼리 후 딜레이 (다음 요청의 실시간 봇 감지 방지)
        time.sleep(REQUEST_DELAY)
        return is_blocked
    except Exception:
        return False


def check_blacklist_from_html(html: str) -> bool:
    """검색 응답 HTML에서 블랙리스트 상태 확인.
    JS 코드의 'Y' 문자열과 구분하기 위해 hidden input의 value만 정확히 매칭한다."""
    return bool(re.search(r'<input[^>]*id="black"[^>]*value="Y"', html))


_last_request_time = 0.0


def search_parts(page, maker="H", vtyp="P", cat_seq="", srch_type="normal", search_term=""):
    """모비스 부품 검색 실행. 블랙리스트 감지 시 MobisBlacklistError 발생."""
    global _last_request_time
    import urllib.parse
    encoded_term = urllib.parse.quote(search_term)

    # 요청 전 딜레이 (실시간 봇 감지 방지)
    elapsed = time.time() - _last_request_time
    if elapsed < REQUEST_DELAY:
        time.sleep(REQUEST_DELAY - elapsed)

    url = (
        f"https://www.mobis-as.com/simple_search_partLoad_v2.do"
        f"?pageIndex=1&hkgb={maker}&vtyp={vtyp}"
        f"&catSeq={cat_seq}&srchType={srch_type}&inText={encoded_term}"
    )

    resp = page.evaluate(f"""
        async () => {{
            const resp = await fetch('{url}', {{
                credentials: 'same-origin',
                headers: {{ 'X-Requested-With': 'XMLHttpRequest' }}
            }});
            return await resp.text();
        }}
    """)
    _last_request_time = time.time()

    # 블랙리스트 감지
    if check_blacklist_from_html(resp):
        raise MobisBlacklistError(
            "모비스 IP 블랙리스트 감지. "
            "브라우저에서 https://www.mobis-as.com/simple_search_part.do 접속 후 "
            "휴대폰 인증으로 해제하세요."
        )

    return resp


def parse_parts_html(html):
    """검색 결과 HTML에서 부품 데이터 추출"""
    if '검색된 부품이 없습니다' in html:
        return {"total": 0, "parts": []}

    # 총 건수
    total_match = re.search(r'총\s*<span[^>]*>(\d+)</span>\s*건', html)
    total = int(total_match.group(1)) if total_match else 0

    # 부품 데이터 추출
    parts = re.findall(
        r'href="/simple_search_inventory\.do\?hkgb=\w+&ptno=(\w+)".*?'
        r'한글 부품명</span>\s*<span[^>]*>([^<]+)</span>.*?'
        r'영문 부품명</span>\s*<span[^>]*>([^<]+)</span>.*?'
        r'가격[^<]*</span>\s*<span[^>]*>\s*([\d,]+)\s*원',
        html, re.DOTALL
    )

    return {
        "total": total,
        "parts": [
            {
                "part_number": ptno,
                "name_kr": name_kr.strip(),
                "name_en": name_en.strip(),
                "price_krw": int(price.replace(",", ""))
            }
            for ptno, name_kr, name_en, price in parts
        ]
    }


def get_models(page, maker="H", vtyp="1"):
    """차량 모델 목록 조회"""
    resp = page.evaluate(f"""
        async () => {{
            const resp = await fetch('/getCarModel.ajax', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
                body: 'hkgb={maker}&vtyp={vtyp}',
                credentials: 'same-origin'
            }});
            return await resp.text();
        }}
    """)
    models = re.findall(r'<option value="(\d+)"[^>]*>([^<]+)</option>', resp)
    return [{"id": v, "name": t} for v, t in models]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="현대모비스 부품 가격 조회")
    parser.add_argument("--maker", default="H", choices=["H", "K"], help="제조사: H(현대), K(기아)")
    parser.add_argument("--vtyp", default="P", help="차량구분: P(승용), C(상용)")
    parser.add_argument("--model", default="", help="모델 코드 (catSeq)")
    parser.add_argument("--part-name", default="", help="한글 부품명 (일반검색)")
    parser.add_argument("--part-number", default="", help="부품번호 (부품번호검색)")
    parser.add_argument("--list-models", action="store_true", help="모델 목록 조회")
    args = parser.parse_args()

    with sync_playwright() as p:
        browser, page = create_stealth_browser(p)

        # 세션 확보를 위해 메인 페이지 먼저 방문
        page.goto("https://www.mobis-as.com/simple_search_part.do", timeout=15000)
        page.wait_for_load_state("networkidle", timeout=10000)

        if args.list_models:
            vtyp_map = {"P": "1", "C": "2"}
            models = get_models(page, args.maker, vtyp_map.get(args.vtyp, "1"))
            print(f"=== {args.maker} 모델 목록 ===")
            for m in models:
                print(f"  [{m['id']}] {m['name']}")

        elif args.part_number:
            html = search_parts(page, maker=args.maker, srch_type="ptno", search_term=args.part_number)
            result = parse_parts_html(html)
            print(json.dumps(result, ensure_ascii=False, indent=2))

        elif args.part_name:
            if not args.model:
                print("일반검색에는 --model 이 필요합니다. --list-models 로 모델 코드를 확인하세요.")
                sys.exit(1)
            html = search_parts(
                page, maker=args.maker, vtyp=args.vtyp,
                cat_seq=args.model, srch_type="normal", search_term=args.part_name
            )
            result = parse_parts_html(html)
            print(json.dumps(result, ensure_ascii=False, indent=2))

        else:
            print("--part-name, --part-number, 또는 --list-models 중 하나를 지정하세요.")

        browser.close()
