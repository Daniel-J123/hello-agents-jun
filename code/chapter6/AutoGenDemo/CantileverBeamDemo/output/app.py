import streamlit as st
import numpy as np
import matplotlib
import matplotlib.pyplot as plt

# --- Matplotlib 中文显示修复: 默认 DejaVu Sans 无 CJK 字形, 会显示为口口口 ---
# 按优先级尝试本机常见中文字体, 全都不存在时回退 DejaVu(此时请改用英文标签).
matplotlib.rcParams["font.family"] = "sans-serif"
matplotlib.rcParams["font.sans-serif"] = [
    "Microsoft YaHei", "SimHei", "PingFang SC", "Hiragino Sans GB",
    "Noto Sans CJK SC", "WenQuanYi Micro Hei", "DejaVu Sans",
]
matplotlib.rcParams["axes.unicode_minus"] = False  # 防止负号变方框

# 1. Streamlit 页面配置 (必须放在第一行)
st.set_page_config(page_title="悬臂梁挠度应力计算", layout="wide")

# 2. 侧边栏输入区域(标签内变量用行内 LaTeX 渲染, 与页面风格一致)
with st.sidebar:
    st.header("参数输入")

    # 用 form 打包参数输入: 修改参数不会立刻重算, 点击"开始计算"按钮才提交(带计算按钮的交互).
    with st.form("beam_params"):
        # 几何与材料参数
        L_in = st.number_input("梁长 $L$ (m)", min_value=0.0, value=1.0, step=0.1, format="%.4f")
        b_in = st.number_input("截面宽度 $b$ (mm)", min_value=0.0, value=50.0, step=1.0, format="%.4f")
        h_in = st.number_input("截面高度 $h$ (mm)", min_value=0.0, value=100.0, step=1.0, format="%.4f")
        E_in = st.number_input("弹性模量 $E$ (GPa)", min_value=0.0, value=200.0, step=1.0, format="%.4f")

        st.divider()

        # 载荷参数
        P_in = st.number_input("尖端集中力 $P$ (N)", min_value=0.0, value=1000.0, step=10.0, format="%.4f")
        q_in = st.number_input("全跨均布载荷 $q$ (N/m)", min_value=0.0, value=0.0, step=10.0, format="%.4f")

        st.divider()

        # 计算按钮: form 提交后才用新参数重算
        submitted = st.form_submit_button("开始计算")

    # 交互控制(放在 form 外: 切换 V 图显示立即生效, 无需再点计算按钮)
    show_V = st.checkbox("显示剪力 $V(x)$ 曲线", value=True)

# 3. 主界面标题
st.title("CAE 悬臂梁计算工具")
st.markdown("基于 Euler-Bernoulli 梁理论, 支持集中力与均布载荷叠加.")

# 4. 数据校验与单位转换
# 定义局部变量用于逻辑判断
L = float(L_in)
b_mm = float(b_in)
h_mm = float(h_in)
E_GPa = float(E_in)
P = float(P_in)
q = float(q_in)

# 校验规则
errors = []
if L <= 0:
    errors.append("错误: 梁长 L 必须大于 0.")
if b_mm <= 0:
    errors.append("错误: 截面宽度 b 必须大于 0.")
if h_mm <= 0:
    errors.append("错误: 截面高度 h 必须大于 0.")
if E_GPa <= 0:
    errors.append("错误: 弹性模量 E 必须大于 0.")
if P < 0 or q < 0:
    errors.append("错误: 载荷 P 和 q 不能为负数.")
if P == 0 and q == 0:
    errors.append("错误: 载荷不能全为零 (P=0 且 q=0).")

if errors:
    for err in errors:
        st.error(err)
    st.stop() # 终止执行, 不显示后续结果

# 单位转换为 SI (计算全程使用 SI)
L_si = L
b_si = b_mm / 1000.0
h_si = h_mm / 1000.0
E_si = E_GPa * 1e9

# 计算惯性矩 I
I = b_si * h_si**3 / 12.0

# 5. 物理计算 (线性叠加)
# 初始化结果数组
w_max_si = 0.0
theta_max_si = 0.0
sigma_max_si = 0.0

# 存储曲线数据的列表, 用于后续绘图
x_plot = np.linspace(0, L_si, 200)
w_curve = np.zeros_like(x_plot)
M_curve = np.zeros_like(x_plot)
V_curve = np.zeros_like(x_plot)

# --- Case P: 尖端集中力 ---
if P > 0:
    w_max_si += P * L_si**3 / (3 * E_si * I)
    theta_max_si += P * L_si**2 / (2 * E_si * I)
    sigma_max_si += 6 * P * L_si / (b_si * h_si**2)

    # 曲线计算
    # w(x) = P*x^2*(3*L-x)/(6*E*I)
    w_curve += P * x_plot**2 * (3 * L_si - x_plot) / (6 * E_si * I)
    # M(x) = P*(L-x)
    M_curve += P * (L_si - x_plot)
    # V(x) = P (常数)
    V_curve += np.full_like(x_plot, P)

# --- Case q: 全跨均布载荷 ---
if q > 0:
    w_max_si += q * L_si**4 / (8 * E_si * I)
    theta_max_si += q * L_si**3 / (6 * E_si * I)
    sigma_max_si += 3 * q * L_si**2 / (b_si * h_si**2)

    # 曲线计算
    # w(x) = q*x^2*(6*L^2 - 4*L*x + x^2)/(24*E*I)
    w_curve += q * x_plot**2 * (6 * L_si**2 - 4 * L_si * x_plot + x_plot**2) / (24 * E_si * I)
    # M(x) = q*(L-x)^2/2
    M_curve += q * (L_si - x_plot)**2 / 2
    # V(x) = q*(L-x)
    V_curve += q * (L_si - x_plot)

# 6. 输出结果转换 (SI -> 显示单位)
w_max_mm = w_max_si * 1000.0
theta_max_mrad = theta_max_si * 1000.0
sigma_max_MPa = sigma_max_si / 1e6

# 7. 工程告警检查 (必须在 SI 制下比较, 即转换回显示单位之前或直接用原始值比较比率)
# 注意: 需求规定 w_max/L >= 0.1 和 h/L > 0.1
# w_max_si 是米, L_si 是米, 比值无量纲
ratio_w_L = w_max_si / L_si
ratio_h_L = h_si / L_si

if ratio_w_L >= 0.1:
    st.warning(rf"告警: 最大挠度与长度之比 $w_{{\max}}/L = {ratio_w_L:.3f} \geq 0.1$, "
               f"小变形假设可能失效, 几何非线性误差显著 (约 3%+).")

if ratio_h_L > 0.1:
    st.warning(rf"告警: 高跨比 $h/L = {ratio_h_L:.3f} > 0.1$, "
               f"剪切变形不可忽略, 欧拉-伯努利梁理论误差可能较大.")

# 8. 结果显示区域(顶部三项用行内 LaTeX, 左对齐, 与下方图表区对齐)
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown("**最大挠度**")
    st.markdown(rf"$w_{{\max}} = {w_max_mm:.4f}\ \mathrm{{mm}}$")
with col2:
    st.markdown("**最大转角**")
    st.markdown(rf"$\theta_{{\max}} = {theta_max_mrad:.4f}\ \mathrm{{mrad}}$")
with col3:
    st.markdown("**最大弯曲应力**")
    st.markdown(rf"$\sigma_{{\max}} = {sigma_max_MPa:.4f}\ \mathrm{{MPa}}$")

st.divider()

# 9. 图表绘制(三图一行三列并排, 一屏显示完整; 字号按小图尺寸同步缩小, dpi 提高保证清晰)
fig, axes = plt.subplots(1, 3, figsize=(15, 4.6), dpi=130)

# 小图统一字号: 标题/轴标签/刻度/图例, 与缩小后的图幅匹配, 避免文字拥挤或过小
FS_TITLE, FS_LABEL, FS_TICK, FS_LEG = 11, 9.5, 8.5, 8.5

# --- 图 1: 挠度 w(x) ---
ax1 = axes[0]
# 计算全程 SI, 显示时将 SI 位移转为 mm, Y 轴 mm / X 轴 m
w_plot_mm = w_curve * 1000.0
ax1.plot(x_plot, w_plot_mm, 'b-', linewidth=1.8, label='$w(x)$')
ax1.set_ylabel('挠度 $w$ (mm)', fontsize=FS_LABEL)
ax1.set_xlabel('位置 $x$ (m)', fontsize=FS_LABEL)
ax1.set_title('挠度分布 $w(x)$', fontsize=FS_TITLE)
ax1.grid(True, linestyle='--', alpha=0.7)
ax1.legend(loc='best', fontsize=FS_LEG)
ax1.tick_params(labelsize=FS_TICK)

# --- 图 2: 弯矩 M(x) ---
ax2 = axes[1]
ax2.plot(x_plot, M_curve, 'g-', linewidth=1.8, label='$M(x)$')
ax2.fill_between(x_plot, M_curve, 0, color='green', alpha=0.1)
# 单位 N·m 用 mathtext 渲染, 变量斜体, 与页面 LaTeX 风格一致
ax2.set_ylabel(r'弯矩 $M$ ($\mathrm{N\cdot m}$)', fontsize=FS_LABEL)
ax2.set_xlabel('位置 $x$ (m)', fontsize=FS_LABEL)
ax2.set_title('弯矩分布 $M(x)$', fontsize=FS_TITLE)
ax2.grid(True, linestyle='--', alpha=0.7)
ax2.legend(loc='best', fontsize=FS_LEG)
ax2.tick_params(labelsize=FS_TICK)

# --- 图 3: 剪力 V(x) ---
ax3 = axes[2]
if show_V:
    ax3.plot(x_plot, V_curve, 'r-', linewidth=1.8, label='$V(x)$')
    ax3.fill_between(x_plot, V_curve, 0, color='red', alpha=0.1)
    ax3.set_ylabel('剪力 $V$ (N)', fontsize=FS_LABEL)
    ax3.set_xlabel('位置 $x$ (m)', fontsize=FS_LABEL)
    ax3.set_title('剪力分布 $V(x)$', fontsize=FS_TITLE)
    ax3.grid(True, linestyle='--', alpha=0.7)
    ax3.legend(loc='best', fontsize=FS_LEG)
    ax3.tick_params(labelsize=FS_TICK)
else:
    ax3.axis('off')
    ax3.text(0.5, 0.5, '$V(x)$ 曲线已隐藏', ha='center', va='center',
             transform=ax3.transAxes, fontsize=FS_TITLE, color='gray')

# 设置 X 轴范围(隐藏态的 ax3 不再动刻度, 避免残留孤立数字)
for ax in [ax1, ax2, ax3]:
    ax.set_xlim(0, L_si)

# tight_layout 必须放在所有 plot 之后, st.pyplot 之前, 否则中文 label 会重叠/裁切
fig.tight_layout(pad=2.0, w_pad=2.5)
st.pyplot(fig, width='stretch')

# 计算公式速查(移到图表下方: 展开/收起都不会把图表推出首屏)
with st.expander("计算公式(Euler-Bernoulli 悬臂梁, P 与 q 线性叠加)"):
    st.latex(r"w(x)=\frac{P x^{2}(3L-x)}{6EI}+\frac{q x^{2}(6L^{2}-4Lx+x^{2})}{24EI}")
    st.latex(r"\theta(x)=\frac{P x(2L-x)}{2EI}+\frac{q x(3L^{2}-3Lx+x^{2})}{6EI}")
    st.latex(r"M(x)=P(L-x)+\frac{q(L-x)^{2}}{2}")
    st.latex(r"V(x)=P+q(L-x),\quad V_{\max}=V(0)=P+qL")
    st.latex(r"\sigma_{\max}=\frac{M_{\max} c}{I}=\frac{6PL}{bh^{2}}+\frac{3qL^{2}}{bh^{2}},\quad c=\frac{h}{2}")
