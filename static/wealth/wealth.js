(function () {
    const app = document.getElementById("wealth-app");
    if (!app) return;

    const form = document.getElementById("wealth-unlock-form");
    const passwordInput = document.getElementById("wealth-password");
    const status = document.getElementById("wealth-status");
    const dashboard = document.getElementById("wealth-dashboard");
    const lockButton = document.getElementById("wealth-lock-button");
    const lockedView = document.querySelector("[data-view='locked']");
    const payloadUrl = app.dataset.payloadUrl || "wealth-data.enc.json";

    const decoder = new TextDecoder();
    const encoder = new TextEncoder();

    const setStatus = (message, tone) => {
        status.textContent = message;
        if (tone) {
            status.dataset.tone = tone;
        } else {
            delete status.dataset.tone;
        }
    };

    const fromBase64 = (value) => {
        const binary = atob(value);
        const bytes = new Uint8Array(binary.length);
        for (let index = 0; index < binary.length; index += 1) {
            bytes[index] = binary.charCodeAt(index);
        }
        return bytes;
    };

    const deriveKey = async (password, payload) => {
        const material = await crypto.subtle.importKey(
            "raw",
            encoder.encode(password),
            "PBKDF2",
            false,
            ["deriveKey"]
        );
        return crypto.subtle.deriveKey(
            {
                name: "PBKDF2",
                salt: fromBase64(payload.kdf.salt),
                iterations: payload.kdf.iterations,
                hash: payload.kdf.hash,
            },
            material,
            { name: "AES-GCM", length: 256 },
            false,
            ["decrypt"]
        );
    };

    const decryptPayload = async (password, payload) => {
        const key = await deriveKey(password, payload);
        const clearBytes = await crypto.subtle.decrypt(
            {
                name: "AES-GCM",
                iv: fromBase64(payload.iv),
                additionalData: encoder.encode(payload.aad),
            },
            key,
            fromBase64(payload.ciphertext)
        );
        return JSON.parse(decoder.decode(clearBytes));
    };

    const formatMoney = (value) => {
        return new Intl.NumberFormat("zh-CN", {
            style: "currency",
            currency: "CNY",
            maximumFractionDigits: 0,
        }).format(value || 0);
    };

    const formatPercent = (value) => `${((value || 0) * 100).toFixed(2)}%`;

    const clearNode = (node) => {
        while (node.firstChild) node.removeChild(node.firstChild);
    };

    const text = (tag, value, className) => {
        const node = document.createElement(tag);
        node.textContent = value;
        if (className) node.className = className;
        return node;
    };

    const renderMetrics = (summary) => {
        const metrics = document.getElementById("wealth-metrics");
        clearNode(metrics);
        [
            ["总资产", summary.totalAssets],
            ["金融资产", summary.financialAssets],
            ["现金", summary.cash],
            ["投资资产", summary.investmentAssets],
            ["净资产", summary.netAssets],
        ].forEach(([label, value]) => {
            const item = document.createElement("div");
            item.className = "wealth-metric";
            item.append(text("span", label));
            item.append(text("strong", formatMoney(value)));
            metrics.append(item);
        });
    };

    const renderBars = (id, rows, denominatorKey) => {
        const container = document.getElementById(id);
        clearNode(container);
        rows.forEach((row) => {
            const item = document.createElement("div");
            const head = document.createElement("div");
            const ratio = denominatorKey ? row[denominatorKey] : row.ratio;
            head.className = "wealth-bar-head";
            head.append(text("span", row.name));
            head.append(text("strong", `${formatMoney(row.amount)} · ${formatPercent(ratio)}`));

            const track = document.createElement("div");
            const fill = document.createElement("div");
            track.className = "wealth-bar-track";
            fill.className = "wealth-bar-fill";
            fill.style.width = `${Math.min(Math.max((ratio || 0) * 100, 0), 100)}%`;
            track.append(fill);

            item.append(head, track);
            container.append(item);
        });
    };

    const renderAdvice = (items) => {
        const container = document.getElementById("wealth-advice");
        clearNode(container);
        items.forEach((item) => {
            const row = document.createElement("div");
            row.className = "wealth-advice-item";
            row.append(text("strong", `${item.priority} | ${item.action}: ${item.recommendation}`));
            row.append(text("p", item.reason));
            container.append(row);
        });
    };

    const renderScores = (summary) => {
        const container = document.getElementById("wealth-scores");
        clearNode(container);
        [
            ["流动性评分", summary.liquidityScore, summary.liquidityNote],
            ["风险评分", summary.riskScore, summary.riskNote],
        ].forEach(([label, score, note]) => {
            const row = document.createElement("div");
            row.className = "wealth-score-card";
            row.append(text("strong", `${label}: ${score}`));
            row.append(text("p", note));
            container.append(row);
        });
    };

    const renderDca = (dca) => {
        const summary = document.getElementById("wealth-dca-summary");
        const table = document.getElementById("wealth-dca-table");
        clearNode(summary);
        clearNode(table);

        if (!dca || !dca.rows || dca.rows.length === 0) {
            summary.append(text("p", "暂无定投数据。"));
            return;
        }

        [
            ["基金数", `${dca.fundCount} 只`],
            ["计划数", `${dca.planCount} 条`],
            ["持续计划", `${dca.activeCount} 条`],
            ["暂停计划", `${dca.pausedCount} 条`],
            ["每周定投", formatMoney(dca.weeklyAmount)],
            ["每月估算", formatMoney(dca.monthlyAmount)],
        ].forEach(([label, value]) => {
            const card = document.createElement("div");
            card.className = "wealth-dca-card";
            card.append(text("span", label));
            card.append(text("strong", value));
            summary.append(card);
        });

        const columns = [
            ["assetName", "标的"],
            ["planName", "计划"],
            ["frequency", "频率"],
            ["singleAmount", "单次金额"],
            ["weeklyAmount", "每周金额"],
            ["returnRate", "收益率"],
            ["nextDebitDate", "下次扣款"],
            ["status", "状态"],
        ];
        const thead = document.createElement("thead");
        const headRow = document.createElement("tr");
        columns.forEach(([, label]) => headRow.append(text("th", label)));
        thead.append(headRow);

        const tbody = document.createElement("tbody");
        dca.rows.forEach((row) => {
            const tr = document.createElement("tr");
            columns.forEach(([key]) => {
                const value = key.endsWith("Amount") ? formatMoney(row[key]) : row[key];
                tr.append(text("td", value || "-"));
            });
            tbody.append(tr);
        });
        table.append(thead, tbody);
    };

    const renderNextActions = (actions) => {
        const list = document.getElementById("wealth-next-actions");
        clearNode(list);
        actions.forEach((item) => list.append(text("li", item)));
    };

    const renderDashboard = (data) => {
        document.getElementById("wealth-snapshot-date").textContent = data.summary.snapshotDate;
        renderMetrics(data.summary);
        renderBars("wealth-category-bars", data.categoryRows, "ratio");
        renderBars("wealth-allocation-bars", data.allocationRows, "ratio");
        renderAdvice(data.weeklyAdvice);
        renderScores(data.summary);
        renderDca(data.dca);
        renderNextActions(data.summary.nextActions || []);
        lockedView.hidden = true;
        dashboard.hidden = false;
    };

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const password = passwordInput.value;
        if (!password) return;

        setStatus("正在读取加密数据...");
        try {
            const response = await fetch(payloadUrl, { cache: "no-store" });
            if (!response.ok) {
                throw new Error("encrypted-data-missing");
            }
            const encryptedPayload = await response.json();
            setStatus("正在本地解密...");
            const data = await decryptPayload(password, encryptedPayload);
            passwordInput.value = "";
            setStatus("解锁成功。", "success");
            renderDashboard(data);
        } catch (error) {
            if (error.message === "encrypted-data-missing") {
                setStatus("尚未生成加密数据文件，请先运行 scripts/export_wealth_payload.py。", "error");
                return;
            }
            setStatus("解锁失败，请检查密码或重新生成加密数据。", "error");
        }
    });

    lockButton.addEventListener("click", () => {
        dashboard.hidden = true;
        lockedView.hidden = false;
        setStatus("已锁定。密码不会发送到服务器，也不会写入本地存储。");
        passwordInput.focus();
    });
})();
