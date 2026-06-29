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
    const formatMoney2 = (value) => {
        return new Intl.NumberFormat("zh-CN", {
            style: "currency",
            currency: "CNY",
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        }).format(value || 0);
    };

    const formatPercent = (value) => `${((value || 0) * 100).toFixed(2)}%`;
    const formatSignedMoney = (value) => {
        const amount = value || 0;
        const sign = amount > 0 ? "+" : "";
        return `${sign}${formatMoney(amount)}`;
    };

    const clearNode = (node) => {
        while (node.firstChild) node.removeChild(node.firstChild);
    };

    const text = (tag, value, className) => {
        const node = document.createElement(tag);
        node.textContent = value;
        if (className) node.className = className;
        return node;
    };

    const svgNode = (tag, attributes = {}) => {
        const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
        Object.entries(attributes).forEach(([key, value]) => {
            if (value !== undefined && value !== null) node.setAttribute(key, value);
        });
        return node;
    };

    const pathLine = (points) => points.map(([x, y], index) => `${index === 0 ? "M" : "L"}${x},${y}`).join(" ");

    const renderWeeklyTrend = (trend) => {
        const container = document.getElementById("wealth-weekly-trend");
        clearNode(container);
        if (!trend || !trend.weeks || trend.weeks.length === 0) {
            container.append(text("p", "暂无周度趋势数据。"));
            return;
        }

        const width = 1080;
        const height = 430;
        const margin = { top: 22, right: 34, bottom: 56, left: 76 };
        const plotWidth = width - margin.left - margin.right;
        const plotHeight = height - margin.top - margin.bottom;
        const weeks = trend.weeks;
        const accounts = trend.accounts || [];
        const colors = trend.assetTypeColors || {};
        const metricColors = trend.metricColors || {};
        const minVisibleWeeks = Math.min(6, weeks.length);
        const chartState = {
            start: 0,
            end: weeks.length - 1,
            dragging: false,
            dragStartX: 0,
            dragStartWindow: [0, weeks.length - 1],
        };
        const svg = svgNode("svg", {
            viewBox: `0 0 ${width} ${height}`,
            role: "img",
            "aria-label": "每周财富变化",
        });
        const defs = svgNode("defs");
        const clip = svgNode("clipPath", { id: "wealth-trend-clip" });
        clip.append(svgNode("rect", { x: margin.left, y: margin.top, width: plotWidth, height: plotHeight }));
        defs.append(clip);
        svg.append(defs);

        const gridLayer = svgNode("g");
        const bars = svgNode("g", { "clip-path": "url(#wealth-trend-clip)" });
        const linesLayer = svgNode("g", { "clip-path": "url(#wealth-trend-clip)" });
        const axisLayer = svgNode("g");
        svg.append(gridLayer);

        const hoverBand = svgNode("rect", {
            x: margin.left,
            y: margin.top,
            width: 1,
            height: plotHeight,
            class: "wealth-trend-hover-band",
            hidden: "true",
        });
        svg.append(hoverBand);
        svg.append(bars);
        svg.append(linesLayer);
        svg.append(axisLayer);

        const interaction = svgNode("g");
        svg.append(interaction);

        const legend = document.createElement("div");
        legend.className = "wealth-trend-legend";
        Object.entries(colors).forEach(([name, color]) => {
            const item = document.createElement("span");
            item.append(svgNode("svg", { viewBox: "0 0 10 10", "aria-hidden": "true" }));
            item.firstChild.append(svgNode("circle", { cx: 5, cy: 5, r: 4, fill: color }));
            item.append(document.createTextNode(name));
            legend.append(item);
        });
        Object.entries(metricColors).forEach(([name, color]) => {
            const item = document.createElement("span");
            item.append(svgNode("svg", { viewBox: "0 0 14 10", "aria-hidden": "true" }));
            item.firstChild.append(svgNode("line", { x1: 1, x2: 13, y1: 5, y2: 5, stroke: color, "stroke-width": 2.5 }));
            item.append(document.createTextNode(name));
            legend.append(item);
        });

        const tooltip = document.createElement("div");
        tooltip.className = "wealth-trend-tooltip";
        tooltip.hidden = true;

        const tooltipColor = (label, color) => {
            if (label === "总资产") return "#111827";
            if (label === "金融资产") return "#6D28D9";
            return color || "#334155";
        };

        const renderTooltip = (week, index, event) => {
            tooltip.hidden = false;
            hoverBand.hidden = false;
            clearNode(tooltip);
            tooltip.append(text("strong", week.weekEnd));
            [
                ["总资产", week.totalAssets, metricColors["总资产"]],
                ["金融资产", week.financialAssets, metricColors["金融资产"]],
                ["周变化", week.weeklyChange, week.weeklyChange >= 0 ? "#16a34a" : "#dc2626", true],
                ...accounts.map((account) => [account, week.accountTotals?.[account] || 0, "#334155"]),
                ...(trend.assetTypes || []).map((assetType) => [assetType, week.assetTypeTotals?.[assetType] || 0, colors[assetType]]),
                ["银行净流水", week.bankNetFlow, week.bankNetFlow >= 0 ? "#16a34a" : "#dc2626", true],
                ["工资收入", week.salaryIncome, "#2563eb"],
            ].forEach(([label, value, color, signed]) => {
                const row = document.createElement("div");
                row.style.color = tooltipColor(label, color);
                row.append(text("span", label));
                row.append(text("b", signed ? formatSignedMoney(value) : formatMoney(value)));
                tooltip.append(row);
            });
            const rect = container.getBoundingClientRect();
            const tooltipWidth = tooltip.offsetWidth || 420;
            const tooltipHeight = Math.min(tooltip.scrollHeight || 560, window.innerHeight - 48);
            const left = Math.min(Math.max(event.clientX - rect.left + 14, 8), Math.max(8, rect.width - tooltipWidth - 8));
            const top = Math.min(Math.max(event.clientY - rect.top + 14, 8), Math.max(8, rect.height - tooltipHeight - 8));
            tooltip.style.left = `${left}px`;
            tooltip.style.top = `${top}px`;
        };

        const clearSvgNode = (node) => {
            while (node.firstChild) node.removeChild(node.firstChild);
        };

        const visibleWeeks = () => weeks.slice(chartState.start, chartState.end + 1);

        const clampWindow = (start, end) => {
            const length = end - start + 1;
            if (start < 0) {
                start = 0;
                end = Math.min(weeks.length - 1, length - 1);
            }
            if (end >= weeks.length) {
                end = weeks.length - 1;
                start = Math.max(0, end - length + 1);
            }
            chartState.start = Math.max(0, start);
            chartState.end = Math.min(weeks.length - 1, end);
        };

        const drawChart = () => {
            const data = visibleWeeks();
            const maxValue = Math.max(
                ...data.map((week) => week.totalAssets || 0),
                ...data.flatMap((week) => Object.values(week.accountTotals || {}))
            );
            const yMax = maxValue <= 0 ? 1 : maxValue * 1.08;
            const y = (value) => margin.top + plotHeight - ((value || 0) / yMax) * plotHeight;
            const weekStep = plotWidth / data.length;
            const groupWidth = Math.min(weekStep * 0.72, 82);
            const barGap = Math.max(2, groupWidth * 0.08);
            const barWidth = Math.max(5, (groupWidth - barGap * (accounts.length - 1)) / Math.max(accounts.length, 1));
            const weekX = (index) => margin.left + weekStep * index + weekStep / 2;
            const barX = (index, accountIndex) => weekX(index) - groupWidth / 2 + accountIndex * (barWidth + barGap);
            const lineX = (index) => weekX(index);

            clearSvgNode(gridLayer);
            clearSvgNode(bars);
            clearSvgNode(linesLayer);
            clearSvgNode(axisLayer);
            clearSvgNode(interaction);
            hoverBand.hidden = true;
            tooltip.hidden = true;

            [0, 0.25, 0.5, 0.75, 1].forEach((ratio) => {
                const value = yMax * ratio;
                const yPos = y(value);
                gridLayer.append(svgNode("line", {
                    x1: margin.left,
                    x2: margin.left + plotWidth,
                    y1: yPos,
                    y2: yPos,
                    class: "wealth-trend-grid",
                }));
                const label = svgNode("text", {
                    x: margin.left - 10,
                    y: yPos + 4,
                    "text-anchor": "end",
                    class: "wealth-trend-axis-label",
                });
                label.textContent = `${Math.round(value / 10000)}万`;
                gridLayer.append(label);
            });

            data.forEach((week, weekIndex) => {
                accounts.forEach((account, accountIndex) => {
                    let cursor = 0;
                    const stacks = (week.stacks || []).filter((item) => item.account === account);
                    stacks.forEach((item) => {
                        const amount = item.amount || 0;
                        const y1 = y(cursor);
                        cursor += amount;
                        const y2 = y(cursor);
                        bars.append(svgNode("rect", {
                            x: barX(weekIndex, accountIndex),
                            y: y2,
                            width: barWidth,
                            height: Math.max(y1 - y2, 1),
                            fill: colors[item.assetType] || "#64748b",
                            rx: 1.5,
                        }));
                    });
                });
            });

            [
                ["总资产", data.map((week, index) => [lineX(index), y(week.totalAssets)]), metricColors["总资产"] || "#F8FAFC"],
                ["金融资产", data.map((week, index) => [lineX(index), y(week.financialAssets)]), metricColors["金融资产"] || "#A78BFA"],
            ].forEach(([label, points, color]) => {
                linesLayer.append(svgNode("path", {
                    d: pathLine(points),
                    fill: "none",
                    stroke: color,
                    "stroke-width": label === "总资产" ? 3.2 : 2.7,
                    "stroke-linejoin": "round",
                    "stroke-linecap": "round",
                    class: "wealth-trend-line",
                }));
                points.forEach(([xPos, yPos]) => {
                    linesLayer.append(svgNode("circle", {
                        cx: xPos,
                        cy: yPos,
                        r: label === "总资产" ? 3.4 : 3,
                        fill: color,
                        stroke: "rgba(15, 23, 42, 0.92)",
                        "stroke-width": 1.5,
                    }));
                });
            });

            data.forEach((week, index) => {
                if (index % Math.ceil(data.length / 8) !== 0 && index !== data.length - 1) return;
                const label = svgNode("text", {
                    x: lineX(index),
                    y: height - 24,
                    "text-anchor": "middle",
                    class: "wealth-trend-axis-label",
                });
                label.textContent = week.weekEnd.slice(5);
                axisLayer.append(label);
            });

            data.forEach((week, index) => {
                const actualIndex = chartState.start + index;
                const hit = svgNode("rect", {
                    x: margin.left + weekStep * index,
                    y: margin.top,
                    width: weekStep,
                    height: plotHeight,
                    fill: "transparent",
                    "data-index": String(actualIndex),
                    "data-visible-index": String(index),
                    class: "wealth-trend-hit",
                });
                hit.addEventListener("mousemove", (event) => {
                    hoverBand.hidden = false;
                    hoverBand.setAttribute("x", margin.left + weekStep * index);
                    hoverBand.setAttribute("width", weekStep);
                    renderTooltip(weeks[actualIndex], actualIndex, event);
                });
                hit.addEventListener("mouseleave", () => {
                    tooltip.hidden = true;
                    hoverBand.hidden = true;
                });
                interaction.append(hit);
            });
        };

        svg.addEventListener("wheel", (event) => {
            if (weeks.length <= minVisibleWeeks) return;
            event.preventDefault();
            const currentLength = chartState.end - chartState.start + 1;
            const direction = event.deltaY > 0 ? 1 : -1;
            const nextLength = Math.min(
                weeks.length,
                Math.max(minVisibleWeeks, currentLength + direction * Math.max(1, Math.round(currentLength * 0.18)))
            );
            const rect = svg.getBoundingClientRect();
            const pointerRatio = Math.min(Math.max((event.clientX - rect.left) / rect.width, 0), 1);
            const anchor = chartState.start + Math.round((currentLength - 1) * pointerRatio);
            const nextStart = Math.round(anchor - (nextLength - 1) * pointerRatio);
            clampWindow(nextStart, nextStart + nextLength - 1);
            drawChart();
        }, { passive: false });

        svg.addEventListener("pointerdown", (event) => {
            chartState.dragging = true;
            chartState.dragStartX = event.clientX;
            chartState.dragStartWindow = [chartState.start, chartState.end];
            svg.setPointerCapture(event.pointerId);
            svg.classList.add("is-dragging");
        });

        svg.addEventListener("pointermove", (event) => {
            if (!chartState.dragging) return;
            const currentLength = chartState.dragStartWindow[1] - chartState.dragStartWindow[0] + 1;
            if (currentLength >= weeks.length) return;
            const dx = event.clientX - chartState.dragStartX;
            const step = plotWidth / currentLength;
            const offset = Math.round(-dx / step);
            clampWindow(chartState.dragStartWindow[0] + offset, chartState.dragStartWindow[1] + offset);
            drawChart();
        });

        svg.addEventListener("pointerup", (event) => {
            chartState.dragging = false;
            svg.releasePointerCapture(event.pointerId);
            svg.classList.remove("is-dragging");
        });

        svg.addEventListener("pointerleave", () => {
            if (!chartState.dragging) {
                tooltip.hidden = true;
                hoverBand.hidden = true;
            }
        });

        container.append(svg, legend, tooltip);
        drawChart();
    };

    const renderMetrics = (summary) => {
        const metrics = document.getElementById("wealth-metrics");
        clearNode(metrics);
        [
            ["总资产", summary.totalAssets],
            ["金融资产", summary.financialAssets],
            ["现金", summary.cash],
            ["投资资产", summary.investmentAssets],
            ["负债", summary.liabilities],
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

    const renderTable = (id, columns, rows) => {
        const table = document.getElementById(id);
        clearNode(table);
        if (!rows || rows.length === 0) {
            const tbody = document.createElement("tbody");
            const tr = document.createElement("tr");
            const td = text("td", "暂无数据。");
            td.colSpan = columns.length;
            tr.append(td);
            tbody.append(tr);
            table.append(tbody);
            return;
        }
        const thead = document.createElement("thead");
        const headRow = document.createElement("tr");
        columns.forEach(([, label]) => headRow.append(text("th", label)));
        thead.append(headRow);
        const tbody = document.createElement("tbody");
        rows.forEach((row) => {
            const tr = document.createElement("tr");
            columns.forEach(([key]) => tr.append(text("td", row[key] || "-")));
            tbody.append(tr);
        });
        table.append(thead, tbody);
    };

    const renderAnalysis = (analysis) => {
        const cashContainer = document.getElementById("wealth-cash-safety");
        const riskContainer = document.getElementById("wealth-risk-exposure");
        const riskConclusion = document.getElementById("wealth-risk-conclusion");
        const systemConclusion = document.getElementById("wealth-system-conclusion");
        clearNode(cashContainer);
        clearNode(riskContainer);
        clearNode(systemConclusion);
        riskConclusion.textContent = "";

        if (!analysis) {
            cashContainer.append(text("p", "暂无分析数据。"));
            return;
        }

        const cash = analysis.cashSafety || {};
        [
            ["当前现金", formatMoney2(cash.currentCash)],
            ["现金占比", formatPercent(cash.cashRatio)],
            ["状态", cash.status || "-"],
            ["距下一档", formatMoney2(cash.gapToNextTarget)],
        ].forEach(([label, value]) => {
            const row = document.createElement("div");
            row.className = "wealth-score-card";
            row.append(text("strong", `${label}: ${value}`));
            cashContainer.append(row);
        });
        if (cash.suggestion) cashContainer.append(text("p", cash.suggestion));

        (analysis.riskExposure?.rows || []).forEach((row) => {
            const item = document.createElement("div");
            const head = document.createElement("div");
            head.className = "wealth-bar-head";
            head.append(text("span", row.name));
            head.append(text("strong", `${formatMoney2(row.amount)} · ${formatPercent(row.ratio)}`));
            const track = document.createElement("div");
            const fill = document.createElement("div");
            track.className = "wealth-bar-track";
            fill.className = "wealth-bar-fill";
            fill.style.width = `${Math.min(Math.max((row.ratio || 0) * 100, 0), 100)}%`;
            track.append(fill);
            item.append(head, track, text("p", row.components || ""));
            riskContainer.append(item);
        });
        riskConclusion.textContent = analysis.riskExposure?.conclusion || "";

        (analysis.systemConclusions || []).slice(0, 3).forEach((item) => {
            const row = document.createElement("div");
            row.className = "wealth-advice-item";
            row.append(text("p", item));
            systemConclusion.append(row);
        });
        renderTable(
            "wealth-real-return-table",
            [
                ["资产类型", "资产类型"],
                ["市值变化", "市值变化"],
                ["本周净买入/卖出", "净买入/卖出"],
                ["本周估算市场损益", "估算市场损益"],
                ["备注", "备注"],
            ],
            analysis.realReturnRows || []
        );
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
        renderAnalysis(data.analysis);
        renderWeeklyTrend(data.weeklyTrend);
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
