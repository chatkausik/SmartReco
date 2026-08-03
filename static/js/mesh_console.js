// MeshAPI Console — polls the live call log and re-renders the summary tiles + table.
(function () {
    "use strict";
    var body = document.getElementById("console-body");
    if (!body) return;

    function fmtTime(ts) {
        var d = new Date(ts * 1000);
        return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    }
    function setText(id, v) { var el = document.getElementById(id); if (el) el.textContent = v; }

    function render(data) {
        var s = data.summary || {};
        setText("s-total", s.total || 0);
        setText("s-chat", s.chat || 0);
        setText("s-emb", s.embedding || 0);
        setText("s-tokens", (s.total_tokens || 0).toLocaleString());
        setText("s-lat", s.avg_latency_ms != null ? s.avg_latency_ms : "—");

        var calls = data.calls || [];
        if (!calls.length) return;
        body.innerHTML = "";
        calls.forEach(function (c) {
            var tr = document.createElement("tr");
            tr.innerHTML =
                '<td class="mono">' + fmtTime(c.ts) + "</td>" +
                '<td><span class="kind-pill kind-' + c.kind + '">' + c.kind + "</span></td>" +
                '<td class="mono">' + esc(c.model) + "</td>" +
                "<td>" + esc(c.purpose) + "</td>" +
                '<td class="mono">' + (c.tokens != null ? c.tokens : "—") + "</td>" +
                '<td class="mono">' + (c.latency_ms != null ? c.latency_ms + "ms" : "—") + "</td>" +
                '<td>' + (c.status === "ok" ? "✓" : '<span class="danger">' + esc(c.status) + "</span>") + "</td>";
            body.appendChild(tr);
        });
    }
    function esc(s) { var d = document.createElement("div"); d.textContent = s == null ? "" : String(s); return d.innerHTML; }

    function poll() {
        fetch("/api/mesh/console").then(function (r) { return r.json(); }).then(render).catch(function () {});
    }
    poll();
    setInterval(poll, 2000);
})();
