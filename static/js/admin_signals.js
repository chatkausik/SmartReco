// Admin Live Signals — polls /admin/signals/data and re-renders one card per user with their
// recent behavioral chips. Admin-only (the endpoint is behind require_admin).
(function () {
    "use strict";
    var root = document.getElementById("admin-signals");
    if (!root) return;

    function esc(s) { var d = document.createElement("div"); d.textContent = s == null ? "" : String(s); return d.innerHTML; }
    function ago(iso) {
        if (!iso) return "no activity";
        var s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
        if (s < 5) return "just now";
        if (s < 60) return s + "s ago";
        if (s < 3600) return Math.floor(s / 60) + "m ago";
        if (s < 86400) return Math.floor(s / 3600) + "h ago";
        return Math.floor(s / 86400) + "d ago";
    }

    function render(data) {
        var users = (data && data.users) || [];
        if (!users.length) { root.innerHTML = '<p class="muted">No registered users yet.</p>'; return; }
        root.innerHTML = "";
        users.forEach(function (u) {
            var chips = (u.signals || []).map(function (c) {
                return '<span class="chip"><span class="k">' + esc(c.k) + '</span><span class="v">' + esc(c.v) + '</span></span>';
            }).join("");
            if (!chips) chips = '<span class="muted small">no recent signals</span>';
            var card = document.createElement("div");
            card.className = "signal-user-card";
            card.innerHTML =
                '<div class="signal-user-head">' +
                    '<div class="signal-user-id"><span class="signal-user-email">' + esc(u.email) + "</span>" +
                    (u.role === "admin" ? ' <span class="role-tag">admin</span>' : "") + "</div>" +
                    '<span class="muted small mono">' + esc(ago(u.last_active)) + "</span>" +
                "</div>" +
                '<div class="signal-user-chips">' + chips + "</div>";
            root.appendChild(card);
        });
    }

    function poll() {
        fetch("/admin/signals/data")
            .then(function (r) { return r.json(); })
            .then(render)
            .catch(function () { /* transient errors stay silent */ });
    }
    poll();
    setInterval(poll, 2500);
})();
