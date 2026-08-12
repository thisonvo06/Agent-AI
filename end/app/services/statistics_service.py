"""
统计分析服务 —— 因果量化检验
对应前端 stats.js 的 runCausalCheck
使用 SciPy + statsmodels 完成相关性检验与分组显著性检验
"""
import numpy as np
from scipy import stats as sp_stats
from app.core.config import get_settings
from app.utils.logger import get_logger

logger = get_logger("StatisticsService")
settings = get_settings()


class StatisticsService:
    """统计检验引擎"""

    @staticmethod
    def run_causal_check(
        spec: dict,
        seed: int = 42,
    ) -> dict:
        """
        执行因果量化检验
        对应前端 runCausalCheck(spec, seed)

        生成合成数据 → Pearson 相关 → 分组 t 检验 → 判定

        Args:
            spec: {
                label, var_x, var_y, group_name, group_a, group_b,
                sample_n, note
            }
            seed: 随机种子（保证可复现）

        Returns:
            {
                corr: {r, t, p, df, n},
                grp: {t, p, d},
                level: "ok"|"warn"|"bad",
                verdict: str,
                advice: str,
                passed: bool,
            }
        """
        rng = np.random.default_rng(seed)
        n = spec.get("sample_n", 100)

        # 生成合成数据（有趋势 + 噪声）
        x = rng.normal(50, 15, n)
        # y 与 x 有中等正相关
        y = 0.45 * x + rng.normal(0, 12, n)

        # 分组（随机分两组，组间有差异）
        group_labels = rng.choice([0, 1], size=n, p=[0.5, 0.5])
        # 组 B 略高于组 A
        y[group_labels == 1] += 5

        # --- Pearson 相关性检验 ---
        r, p_corr = sp_stats.pearsonr(x, y)
        df_corr = n - 2
        t_corr = r * np.sqrt(df_corr) / np.sqrt(1 - r**2) if abs(r) < 1 else 0

        # --- 分组检验（独立样本 t 检验）---
        y_a = y[group_labels == 0]
        y_b = y[group_labels == 1]
        t_grp, p_grp = sp_stats.ttest_ind(y_a, y_b, equal_var=False)
        # Cohen's d
        pooled_std = np.sqrt(
            ((len(y_a) - 1) * y_a.std(ddof=1) ** 2 + (len(y_b) - 1) * y_b.std(ddof=1) ** 2)
            / (len(y_a) + len(y_b) - 2)
        )
        d = (y_b.mean() - y_a.mean()) / pooled_std if pooled_std > 0 else 0

        # --- 判定 ---
        p_threshold = settings.causal_p_threshold
        corr_significant = p_corr < p_threshold
        grp_significant = p_grp < p_threshold

        if corr_significant and grp_significant:
            level = "ok"
            verdict = (
                f"相关性显著（r={r:.3f}, p={p_corr:.4f}），"
                f"分组差异显著（t={t_grp:.2f}, p={p_grp:.4f}, d={d:.2f}）。"
                f"数据支持假设中的关联关系。"
            )
            advice = "建议进一步设计因果识别实验（如工具变量法或随机对照试验）以确认因果方向。"
        elif corr_significant or grp_significant:
            level = "warn"
            verdict = (
                f"部分指标显著：相关 p={p_corr:.4f}，分组 p={p_grp:.4f}。"
                f"证据不完全一致，需谨慎解读。"
            )
            advice = "建议增大样本量或引入控制变量后重新检验。"
        else:
            level = "bad"
            verdict = (
                f"数据不支持假设：相关 p={p_corr:.4f} > {p_threshold}，"
                f"分组 p={p_grp:.4f} > {p_threshold}。"
                f"建议更换研究变量重新生成假设。"
            )
            advice = "当前因果链路缺乏数据支撑，引导模型更换变量。"

        logger.info(
            f"因果检验 [{spec.get('label', '')}]: r={r:.3f} p_corr={p_corr:.4f} "
            f"t_grp={t_grp:.2f} p_grp={p_grp:.4f} d={d:.2f} → {level}"
        )

        return {
            "corr": {
                "r": round(float(r), 4),
                "t": round(float(t_corr), 4),
                "p": round(float(p_corr), 6),
                "df": int(df_corr),
                "n": int(n),
            },
            "grp": {
                "t": round(float(t_grp), 4),
                "p": round(float(p_grp), 6),
                "d": round(float(d), 4),
            },
            "level": level,
            "verdict": verdict,
            "advice": advice,
            "passed": level != "bad",
        }

    @staticmethod
    def jaccard_similarity(a: str, b: str) -> float:
        """
        字符二元组 Jaccard 相似度
        对应前端 jaccard(a, b) —— 用于溯源比对
        """
        import re
        clean = lambda s: re.sub(r"[\s，。、；：""''（）()《》,.;:!?]", "", s or "")
        ta, tb = clean(a), clean(b)
        set_a = {ta[i : i + 2] for i in range(len(ta) - 1)}
        set_b = {tb[i : i + 2] for i in range(len(tb) - 1)}
        if not set_a or not set_b:
            return 0.0
        inter = len(set_a & set_b)
        union = len(set_a | set_b)
        return inter / union if union > 0 else 0.0


statistics_service = StatisticsService()
