# app.py 修复记录：从卡死无数据到正常刷新

> 文件：`code/chapter6/AutoGenDemo/output/app.py`
> 现象：首次截图卡在 `加载中...` 点刷新无变化 + 顶部显示 `#main-title`；第二次截图价格已出来但显示 `<div class='info-label'>` 原始标签。

## 1. 致命 Bug：`is_loading + st.stop()` 死锁

### 原始代码

```python
def init_session_state():
    if 'is_loading' not in st.session_state:
        st.session_state.is_loading = True  # 默认 True

init_session_state()  # 顶层先执行

def main():
    if st.session_state.is_loading:
        st.markdown('加载中...', unsafe_allow_html=True)
        st.stop()  # 直接停，后面永不执行
    # ...
    result = fetch_btc_price()  # 在 stop() 后面，永远到不了
```

### 为什么卡死？

1. 首次运行 `is_loading=True`，进入分支 `st.stop()`，`fetch` 一次没调过。
2. 点刷新只是 `rerun` 重进 `main()`，还是 `True` 还是 `stop()`。
3. `is_loading=False` 的赋值写在 `fetch` 成功之后，但 `fetch` 到不了，状态机永远解不开。

### 修复后（现行版）

```python
st.button("刷新价格", use_container_width=True)  # 点即 rerun
with st.spinner("正在获取最新价格..."):
    result = fetch_btc_price()  # 每次 rerun 都重拉 = 刷新有效
if not result['success']:
    st.markdown(f'...{result["error"]}...', unsafe_allow_html=True)
    return  # 用 return，不用 stop()+rerun，避免递归
```

删掉整套 `is_loading/is_refreshing` 状态机，改直通式：按钮 -> rerun -> fetch -> 渲染。

## 2. 标题显示 `#main-title` 字面量

原始：`st.markdown("#main-title")`，会被当 Markdown 文本原样显示，CSS `#main-title` 根本没命中。

修复：`st.markdown('<div id="main-title">比特币价格</div>', unsafe_allow_html=True)`，用 `id` 才能命中金色样式。

## 3. `set_page_config` 位置违规

原始顶层先 `init_session_state()` 用了 `st.session_state`，`main()` 里才调 `set_page_config`。Streamlit 要求它是第一个 `st` 命令。

修复：提到模块顶层第 8 行，第一行就执行。

## 4. 刷新按钮是空操作

原始：`st.button(..., on_click=lambda: st.session_state.update())`，`update()` 无参什么都不做。在 Streamlit 里点按钮本身就会 `rerun`，不需要 on_click。

修复：`st.button("刷新价格", use_container_width=True)`，点即 rerun 即重新 fetch。

## 5. 24h 涨跌额算错

原始：`change_amount = current_price - st.session_state.last_price`，这是本次与上次刷新的差，不是 24h 差，首次还显示 0 误导。

修复：`simple/price` 只给 `usd_24h_change(%)`，反推 `ago = now/(1+pct/100)`，`amount = now - ago`。这才和 `+0.47% / +$364.16` 自洽。另把取值改为 `.get('usd_24h_change',0.0) or 0.0` 防缺 Key 崩溃。

## 6. `<div class='info-label'>` 露标签 - 漏 unsafe_allow_html

原始（原 L188/L195）：

```python
st.markdown(f"<div class='info-label'>24小时涨跌幅</div>")  # 漏参数
st.markdown(f"<div class='info-label'>24小时涨跌额</div>")  # 漏参数
```

修复（现 L89/L95）：

```python
st.markdown("<div class='info-label'>24小时涨跌幅</div>", unsafe_allow_html=True)
st.markdown("<div class='info-label'>24小时涨跌额</div>", unsafe_allow_html=True)
```

`st.markdown` 默认转义 HTML，只有加 `unsafe_allow_html=True` 才渲染。同文件 `price-value / change-positive` 都加了所以正常，只有这两行漏了，第二张截图才一半正常一半露标签。

## 7. 其他加固

- 超时 5s -> 10s：国内到 CoinGecko 慢。
- 429 限流：原来统一归服务器错误，现在显式提示等待 1 分钟，不让用户狂点加重限流。
- 加载提示：自定义 loading-text + stop() 改为 `with st.spinner()`，随 fetch 自动消失。
- 自动刷新：原来 `elapsed>=5s` 几乎每次 rerun，易递归+429；改为 sidebar 默认关，需手动开，`sleep(30)+rerun()` 放末尾。

## 验证

```bash
python -m py_compile output/app.py  # COMPILE_OK
streamlit run output/app.py
```

必须重启 streamlit 旧进程。应看到金色标题 + 三列数据 + 更新时间，点刷新时间变化即有效。

