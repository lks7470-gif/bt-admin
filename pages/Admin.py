def get_work_order_html(order_list):
    html = """
    <html>
    <head>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;700;900&display=swap');
            body { font-family: 'Noto Sans KR', sans-serif; padding: 20px; }
            
            /* 작업 카드 스타일 */
            .job-card {
                border: 2px solid #000;
                margin-bottom: 20px;
                page-break-inside: avoid; /* 인쇄 시 중간에 잘리지 않게 */
            }
            
            /* 헤더: ID와 날짜 */
            .header {
                background-color: #eee;
                padding: 10px;
                border-bottom: 1px solid #000;
                display: flex; justify-content: space-between; align-items: center;
            }
            .lot-id { font-size: 24px; font-weight: 900; }
            
            /* 핵심: QR + 정보 통합 박스 (공간 활용) */
            .info-container {
                display: flex;
                border-bottom: 1px solid #000;
            }
            
            /* 왼쪽: QR 코드 */
            .qr-box {
                width: 120px;
                padding: 10px;
                border-right: 1px solid #000;
                display: flex; align-items: center; justify-content: center;
            }
            
            /* 오른쪽: 상세 스펙 (여기에 원단, 커팅, 접합 다 넣음) */
            .spec-box {
                flex: 1; /* 남는 공간 다 씀 */
                padding: 10px;
            }
            
            /* 스펙 테이블 스타일 */
            .spec-table { width: 100%; border-collapse: collapse; }
            .spec-table td { padding: 4px; font-size: 14px; }
            .label { font-weight: bold; width: 80px; color: #555; }
            .value { font-weight: bold; font-size: 16px; color: #000; }
            
            /* 접합 여부 체크박스 스타일 */
            .check-box {
                display: inline-block; width: 15px; height: 15px; 
                border: 1px solid #000; text-align: center; line-height: 12px; margin-right: 5px;
            }
            
            /* 하단: 제품 규격 */
            .dim-box { padding: 15px; text-align: center; font-size: 22px; font-weight: bold; }
        </style>
    </head>
    <body>
    """

    # 최종 발행된 QR 리스트와 원본 주문 정보를 매칭해서 출력
    # (여기서는 편의상 order_list와 generated_qrs가 싱크되었다고 가정)
    
    # 만약 generated_qrs가 있다면 그것을 기준으로 루프
    # (실제 코드에서는 order_list와 generated_qrs를 매칭해야 합니다. 
    #  여기서는 'generated_qrs' 안에 모든 정보가 있다고 가정하고 작성합니다.)
    
    for item in st.session_state.get('generated_qrs', []):
        # Base64 이미지 변환은 위쪽 로직에서 처리됨
        img_b64 = image_to_base64(item['img']) 
        
        # 13자리 ID (예: ROLL250122G00)
        full_id = item['lot'] 
        
        # 원본 정보 찾기 (order_list나 DB 저장시 정보를 item에 같이 넣어뒀다고 가정)
        # * 중요: 발행 로직에서 new_qrs.append 할 때 spec_cut, spec_lam, fabric_full_name을 같이 넣어주세요!
        fabric_full = item.get('fabric_full', 'Roll-2314-a') # 원단 Full 명칭
        cut_cond = item.get('spec_cut', '50/80/20')
        lam_cond = item.get('spec_lam', '-')
        is_lam = item.get('is_lam', True)
        
        # 접합 체크박스 표시 (ㅁ 또는 V)
        lam_check_mark = "V" if is_lam else "&nbsp;"
        lam_style = "color: #000;" if is_lam else "color: #ccc; text-decoration: line-through;"

        html += f"""
        <div class="job-card">
            <div class="header">
                <span class="lot-id">{full_id}</span>
                <span>{datetime.now().strftime('%Y-%m-%d')}</span>
            </div>
            
            <div class="info-container">
                <div class="qr-box">
                    <img src="data:image/png;base64,{img_b64}" width="100">
                </div>
                
                <div class="spec-box">
                    <table class="spec-table">
                        <tr>
                            <td class="label">🧵 원단명</td>
                            <td class="value">{fabric_full}</td> </tr>
                        <tr>
                            <td colspan="2"><hr style="margin: 5px 0; border-top: 1px dashed #ccc;"></td>
                        </tr>
                        <tr>
                            <td class="label">✂️ 커팅</td>
                            <td class="value">{cut_cond}</td>
                        </tr>
                        <tr>
                            <td class="label">🔥 접합</td>
                            <td class="value" style="{lam_style}">
                                <span class="check-box">{lam_check_mark}</span>
                                {lam_cond}
                            </td>
                        </tr>
                    </table>
                </div>
            </div>
            
            <div class="dim-box">
                {item['prod']} / {item['w']} x {item['h']} / {item['elec']}
            </div>
        </div>
        """
        
    html += "</body></html>"
    return html
