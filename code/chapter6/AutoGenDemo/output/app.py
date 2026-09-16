import streamlit as st
import requests
import json
from datetime import datetime
import time

# 页面配置必须是第一个 st 命令
st.set_page_config(page_title="比特币价格", page_icon="₿", layout="centered")

# 配置常量
API_URL = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd&include_24hr_change=true"
TIMEOUT = 10

def fetch_btc_price():
    """从 CoinGecko API 获取比特币价格，返回统一结构."""
    try:
        response = requests.get(API_URL, timeout=TIMEOUT)
        response.raise_for_status()
        data = response.json()
        if not data or 'bitcoin' not in data:
            return {'success': False, 'error': '数据为空，请检查 API 返回'}
        return {'success': True, 'data': data}
    except requests.exceptions.Timeout:
        return {'success': False, 'error': '请求超时，请稍后重试'}
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 429:
            return {'success': False, 'error': '请求过于频繁（429 限流），请等待 1 分钟后重试'}
        return {'success': False, 'error': f'服务器返回错误，请稍后重试'}
    except requests.exceptions.RequestException as e:
        return {'success': False, 'error': f'网络异常：{str(e)}'}
    except json.JSONDecodeError:
        return {'success': False, 'error': '数据格式异常，无法解析'}
    except Exception as e:
        return {'success': False, 'error': f'未知错误：{str(e)}'}

def apply_custom_style():
    st.markdown("""
    <style>
    #main-title {
        color: #FFA500;
        font-size: 32px;
        font-weight: bold;
        text-align: center;
        margin-bottom: 10px;
    }
    .price-value {
        color: #FFFFFF;
        font-size: 42px;
        font-weight: bold;
        margin: 10px 0;
    }
    .change-positive { color: #00C853; font-size: 24px; font-weight: bold; }
    .change-negative { color: #FF3B30; font-size: 24px; font-weight: bold; }
    .info-label { color: #B0B0B0; font-size: 16px; }
    .error-text {
        color: #FF3B30; text-align: center; font-size: 18px;
        padding: 20px; background-color: #2A1A1A; border-radius: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

def main():
    apply_custom_style()
    # 修复截图里显示 #main-title 字面量的问题：原来写的是 st.markdown("#main-title")
    st.markdown('<div id="main-title">₿ 比特币价格</div>', unsafe_allow_html=True)
    st.markdown("### 比特币价格 (BTC/USD)")
    auto_refresh = st.sidebar.checkbox("自动刷新(30 秒)", value=False)
    st.button("🔄 刷新价格", use_container_width=True)
    with st.spinner("正在获取最新价格..."):
        result = fetch_btc_price()
    if not result['success']:
        st.markdown(f'<div class="error-text">⚠️ {result["error"]}</div>', unsafe_allow_html=True)
        st.caption("请检查网络后点击“🔄 刷新价格”重试。CoinGecko 免费 API 有限流，频繁刷新会出现 429。")
        return
    data = result['data']
    current_price = data['bitcoin']['usd']
    change_percent = data['bitcoin'].get('usd_24h_change', 0.0) or 0.0
    # simple/price 只给涨跌幅，反推 24h 前价格再算涨跌额
    if change_percent <= -100:
        price_24h_ago = current_price
    else:
        price_24h_ago = current_price / (1 + change_percent / 100)
    change_amount = current_price - price_24h_ago
    current_time = datetime.now()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f'<div class="price-value">${current_price:,.2f}</div>', unsafe_allow_html=True)
    with col2:
        st.markdown("<div class='info-label'>24小时涨跌幅</div>", unsafe_allow_html=True)
        if change_percent >= 0:
            st.markdown(f'<div class="change-positive">+{change_percent:.2f}%</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="change-negative">{change_percent:.2f}%</div>', unsafe_allow_html=True)
    with col3:
        st.markdown("<div class='info-label'>24小时涨跌额</div>", unsafe_allow_html=True)
        if change_amount >= 0:
            st.markdown(f'<div class="change-positive">+${change_amount:,.2f}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="change-negative">-${abs(change_amount):,.2f}</div>', unsafe_allow_html=True)
    st.caption(f"数据更新时间：{current_time.strftime('%Y-%m-%d %H:%M:%S')} | 数据来源：CoinGecko")
    if auto_refresh:
        time.sleep(30)
        st.rerun()

if __name__ == "__main__":
    main()
