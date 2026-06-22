<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>스마트 가계부</title>
    <script src="https://cdn.jsdelivr.net/npm/xlsx/dist/xlsx.full.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/echarts/dist/echarts.min.js"></script>
    
    <style>
        :root {
            --primary: #4a90e2; --bg: #f4f7fb; --card: #ffffff;
            --text-main: #333; --text-sub: #888;
            --safe: #2ecc71; --warn: #f1c40f; --danger: #e74c3c;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        body { background-color: var(--bg); color: var(--text-main); padding-bottom: 70px; }
        header { background: var(--card); padding: 15px; text-align: center; box-shadow: 0 2px 5px rgba(0,0,0,0.05); font-weight: bold; color: var(--primary); }
        main { padding: 15px; max-width: 600px; margin: 0 auto; }
        
        .card { background: var(--card); border-radius: 12px; padding: 20px; margin-bottom: 15px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); }
        h3 { font-size: 1.05rem; margin-bottom: 15px; border-bottom: 1px solid #eee; padding-bottom: 8px; color: #555; }
        
        /* 업로드 UI */
        .upload-btn { display: block; width: 100%; padding: 12px; background: var(--primary); color: white; text-align: center; border-radius: 8px; font-weight: bold; cursor: pointer; }
        #upload-status { text-align: center; margin-top: 10px; font-size: 0.85rem; color: var(--text-sub); }
        
        /* 월간 네비게이션 */
        .month-nav { display: flex; justify-content: space-between; align-items: center; margin: 10px 0 20px; }
        .month-nav button { background: none; border: none; font-size: 1.5rem; color: var(--primary); cursor: pointer; padding: 0 15px; }
        .month-nav h2 { font-size: 1.2rem; }
        .date-range { text-align: center; font-size: 0.8rem; color: var(--text-sub); margin-top: -15px; margin-bottom: 15px; }
        
        /* 자산 및 예산 UI */
        .asset-total { font-size: 1.8rem; font-weight: bold; color: var(--primary); text-align: center; margin: 10px 0; }
        .budget-inputs { display: flex; gap: 8px; margin-bottom: 15px; }
        .budget-inputs input { flex: 1; padding: 10px; border: 1px solid #ddd; border-radius: 6px; }
        .budget-inputs button { padding: 10px; background: var(--bg); border: 1px solid #ccc; border-radius: 6px; cursor: pointer; }
        .progress-bg { width: 100%; height: 20px; background: #eee; border-radius: 10px; overflow: hidden; }
        .progress-bar { height: 100%; width: 0%; transition: 0.3s; }
        #budget-text { margin-top: 8px; font-size: 0.85rem; text-align: right; }
        
        /* 하단 탭 */
        .bottom-nav { position: fixed; bottom: 0; left: 0; width: 100%; height: 60px; background: var(--card); display: flex; border-top: 1px solid #eee; }
        .nav-btn { flex: 1; border: none; background: none; color: var(--text-sub); font-size: 0.95rem; cursor: pointer; }
        .nav-btn.active { color: var(--primary); font-weight: bold; border-top: 3px solid var(--primary); }
    </style>
</head>
<body>

    <header>스마트 가계부 PWA</header>

    <main>
        <div class="card">
            <label for="excel-upload" class="upload-btn">뱅크샐러드 엑셀 파일 업로드</label>
            <input type="file" id="excel-upload" accept=".xlsx, .xls" style="display: none;">
            <p id="upload-status">엑셀 파일을 업로드하면 브라우저에서 즉시 분석합니다.</p>
        </div>

        <div class="month-nav">
            <button id="prev-month">◀</button>
            <h2 id="current-month">2026년 6월</h2>
            <button id="next-month">▶</button>
        </div>
        <p class="date-range" id="date-range-text">(2026-05-10 ~ 2026-06-09)</p>

        <div class="card">
            <h3>실시간 총 자산 (뱅샐 연동 + 군인공제회)</h3>
            <div class="asset-total" id="total-asset">0 원</div>
        </div>

        <div class="card">
            <h3>이번 달 예산 관리</h3>
            <div class="budget-inputs">
                <input type="number" id="budget-input" placeholder="목표 예산 입력 (원)">
                <button onclick="saveBudget()">저장</button>
            </div>
            <div class="progress-bg"><div class="progress-bar" id="budget-bar"></div></div>
            <p id="budget-text">예산을 설정해주세요.</p>
        </div>

        <div class="card">
            <h3>지출 흐름도 (Sankey)</h3>
            <div id="sankey-chart" style="width: 100%; height: 300px;"></div>
        </div>
    </main>

    <nav class="bottom-nav">
        <button class="nav-btn active">월간 대시보드</button>
        <button class="nav-btn" onclick="alert('연간 결산 기능은 준비중입니다.')">연간 결산</button>
    </nav>

    <script>
        /** PWA 설정을 위한 인라인 처리 (단일 파일 구동용) **/
        const manifest = {
            name: "스마트 가계부", short_name: "가계부", start_url: ".", display: "standalone",
            background_color: "#f4f7fb", theme_color: "#4a90e2"
        };
        const manifestBlob = new Blob([JSON.stringify(manifest)], {type: 'application/manifest+json'});
        const manifestUrl = URL.createObjectURL(manifestBlob);
        const link = document.createElement('link');
        link.rel = 'manifest'; link.href = manifestUrl;
        document.head.appendChild(link);

        const swCode = `self.addEventListener('install', e => self.skipWaiting()); self.addEventListener('fetch', e => {});`;
        const swBlob = new Blob([swCode], {type: 'application/javascript'});
        if ('serviceWorker' in navigator) navigator.serviceWorker.register(URL.createObjectURL(swBlob));

        /** 전역 변수 및 DOM **/
        let rawTx = [];
        let rawAssets = 0;
        let currentDate = new Date(); // 현재 날짜 기준
        let echartInstance = null;

        document.getElementById('excel-upload').addEventListener('change', handleUpload);
        document.getElementById('prev-month').addEventListener('click', () => changeMonth(-1));
        document.getElementById('next-month').addEventListener('click', () => changeMonth(1));

        /** 1. 엑셀 파싱 **/
        function handleUpload(e) {
            const file = e.target.files[0];
            if (!file) return;
            document.getElementById('upload-status').innerText = "분석 중...";
            
            const reader = new FileReader();
            reader.onload = (evt) => {
                const data = new Uint8Array(evt.target.result);
                const workbook = XLSX.read(data, { type: 'array' });
                
                // 가계부 내역 시트 파싱
                const txSheet = workbook.SheetNames.find(n => n.includes('가계부'));
                if (txSheet) rawTx = XLSX.utils.sheet_to_json(workbook.Sheets[txSheet]);
                
                // 뱅샐현황 시트 파싱 (잔액 추정 합산)
                const assetSheet = workbook.SheetNames.find(n => n.includes('뱅샐'));
                if (assetSheet) {
                    const rows = XLSX.utils.sheet_to_json(workbook.Sheets[assetSheet], {header: 1});
                    rawAssets = 0;
                    rows.forEach(row => {
                        // 가장 흔한 엑셀 서식 상, 특정 행에 문자열과 큰 숫자가 같이 있으면 잔액으로 간주
                        const numbers = row.filter(cell => typeof cell === 'number' && cell > 1000);
                        if(numbers.length > 0 && row.some(cell => typeof cell === 'string')) {
                            rawAssets += Math.max(...numbers); // 해당 행의 가장 큰 숫자를 잔액으로 합산
                        }
                    });
                }
                document.getElementById('upload-status').innerText = "업로드 및 파싱 완료!";
                updateUI();
            };
            reader.readAsArrayBuffer(file);
        }

        /** 2. 월 변경 및 날짜 계산 **/
        function changeMonth(delta) {
            currentDate.setMonth(currentDate.getMonth() + delta);
            updateUI();
        }

        function getCycleDates(dateObj) {
            const y = dateObj.getFullYear(), m = dateObj.getMonth();
            const start = new Date(y, m - 1, 10);
            const end = new Date(y, m, 9, 23, 59, 59);
            return { start, end, y, m };
        }

        /** 3. 데이터 필터링 및 UI 갱신 **/
        function updateUI() {
            const { start, end, y, m } = getCycleDates(currentDate);
            
            document.getElementById('current-month').innerText = `${y}년 ${m + 1}월`;
            document.getElementById('date-range-text').innerText = 
                `(${start.getFullYear()}-${String(start.getMonth()+1).padStart(2,'0')}-10 ~ ${end.getFullYear()}-${String(end.getMonth()+1).padStart(2,'0')}-09)`;

            // 군인공제회 하드코딩 로직 (예: 24년 1월 기준 1,190만 원 + 매달 5.5만 원)
            const baseDate = new Date(2024, 0, 1);
            const diffMonths = (y - baseDate.getFullYear()) * 12 + (m - baseDate.getMonth());
            const militaryAid = 11900000 + (Math.max(0, diffMonths) * 55000);
            
            document.getElementById('total-asset').innerText = Math.floor(rawAssets + militaryAid).toLocaleString() + " 원";

            // 전월 10일 ~ 당월 9일, 이체 제외 필터링
            const filteredTx = rawTx.filter(tx => {
                if (tx['타입'] === '이체') return false;
                const txDate = new Date(tx['날짜'] || tx['Date']);
                return txDate >= start && txDate <= end;
            });

            updateBudget(filteredTx, y, m);
            drawSankey(filteredTx);
        }

        /** 4. 예산 로직 **/
        function saveBudget() {
            const { y, m } = getCycleDates(currentDate);
            const val = document.getElementById('budget-input').value;
            localStorage.setItem(`budget_${y}_${m}`, val);
            updateUI();
        }

        function updateBudget(txList, y, m) {
            const budget = Number(localStorage.getItem(`budget_${y}_${m}`)) || 0;
            document.getElementById('budget-input').value = budget > 0 ? budget : '';

            let spent = 0;
            txList.forEach(tx => {
                if (tx['타입'] === '지출') spent += Math.abs(tx['금액']);
            });

            const bar = document.getElementById('budget-bar');
            const txt = document.getElementById('budget-text');
            
            if (budget > 0) {
                const ratio = (spent / budget) * 100;
                bar.style.width = Math.min(ratio, 100) + '%';
                bar.style.backgroundColor = ratio < 80 ? 'var(--safe)' : (ratio <= 100 ? 'var(--warn)' : 'var(--danger)');
                txt.innerText = `사용: ${spent.toLocaleString()}원 / 잔여: ${(budget - spent).toLocaleString()}원`;
            } else {
                bar.style.width = '0%';
                txt.innerText = "예산을 설정해주세요.";
            }
        }

        /** 5. 시각화 (Sankey) **/
        function drawSankey(txList) {
            if (!echartInstance) echartInstance = echarts.init(document.getElementById('sankey-chart'));
            
            let totalSpent = 0;
            const categories = {};
            
            txList.forEach(tx => {
                if (tx['타입'] === '지출') {
                    const cat = tx['대분류'] || '미분류';
                    const amt = Math.abs(tx['금액']);
                    categories[cat] = (categories[cat] || 0) + amt;
                    totalSpent += amt;
                }
            });

            const nodes = [{ name: '총 지출' }];
            const links = [];

            Object.entries(categories).forEach(([cat, amt]) => {
                nodes.push({ name: cat });
                links.push({ source: '총 지출', target: cat, value: amt });
            });

            // 지출 내역이 없으면 차트 초기화
            if (links.length === 0) {
                echartInstance.clear();
                return;
            }

            echartInstance.setOption({
                tooltip: { trigger: 'item' },
                series: {
                    type: 'sankey', layout: 'none',
                    data: nodes, links: links,
                    lineStyle: { color: 'gradient', curveness: 0.5 },
                    nodeAlign: 'left'
                }
            }, true);
        }

        // 초기화
        updateUI();
    </script>
</body>
</html>
