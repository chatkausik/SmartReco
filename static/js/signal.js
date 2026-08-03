// "Your Signal" — a live visualization of the behavioral tracker. Chips appear in real time
// as the user hovers, views, dwells, searches, and clicks. Purely presentational; the actual
// events are still batched to /api/events by tracker.js.
//
// The last MAX signals persist in localStorage so the panel carries history across page
// navigations instead of resetting each load. Logged-in users are also seeded server-side.
(function () {
    "use strict";

    var feed = document.getElementById("signal-feed");
    if (!feed) return;
    var panel = document.getElementById("signal-panel");
    var empty = document.getElementById("signal-empty");
    var MAX = 10;
    var HISTORY_KEY = "sr_signal_history";
    var categoryCounts = {};

    function loadHistory() {
        try { return JSON.parse(localStorage.getItem(HISTORY_KEY)) || []; } catch (e) { return []; }
    }
    function saveHistory(h) {
        try { localStorage.setItem(HISTORY_KEY, JSON.stringify(h.slice(0, MAX))); } catch (e) {}
    }
    var history = loadHistory();

    function chipEl(kind, value) {
        var chip = document.createElement("div");
        chip.className = "chip";
        var k = document.createElement("span"); k.className = "k"; k.textContent = kind;
        var v = document.createElement("span"); v.className = "v"; v.textContent = value;
        chip.appendChild(k); chip.appendChild(document.createTextNode(" · ")); chip.appendChild(v);
        return chip;
    }

    function clearEmpty() { if (empty) { empty.remove(); empty = null; } }

    // Add a live chip (prepend, newest on top) and persist to history.
    function addChip(kind, value) {
        if (history[0] && history[0].k === kind && history[0].v === value) return; // dedupe repeats
        clearEmpty();
        history.unshift({ k: kind, v: value });
        history = history.slice(0, MAX);
        saveHistory(history);
        feed.insertBefore(chipEl(kind, value), feed.firstChild);
        while (feed.children.length > MAX) feed.removeChild(feed.lastChild);
    }

    function noteCategory(cat) {
        if (!cat) return;
        categoryCounts[cat] = (categoryCounts[cat] || 0) + 1;
        updateTeaser();
    }

    // Anonymous product page: compose the AGENT · RECOMMENDATION teaser from live behavior.
    var recoBox = document.getElementById("agent-reco");
    var recoText = document.getElementById("agent-reco-text");
    function updateTeaser() {
        if (!recoBox || !recoBox.getAttribute("data-anon") || !recoText) return;
        var top = null, best = 0;
        for (var c in categoryCounts) if (categoryCounts[c] > best) { best = categoryCounts[c]; top = c; }
        if (top && best >= 2) {
            recoText.textContent = "You keep circling " + top +
                " — sign in and the agent will map the path builders like you actually finish, not just start.";
        }
    }

    // ---- initial render: MERGE server seed (logged-in recent activity) with local history ----
    var seed = [];
    if (panel) { try { seed = JSON.parse(panel.getAttribute("data-seed-signals") || "[]"); } catch (e) { seed = []; } }
    // Union seed + local history, newest-first, de-duplicated, capped at MAX. Server seed
    // comes first so a logged-in user immediately sees their real last-N signals; any
    // localStorage-only chips are preserved after it.
    var mergedSeen = {};
    var merged = [];
    seed.concat(history).forEach(function (h) {
        if (!h || !h.k) return;
        var key = h.k + "|" + h.v;
        if (mergedSeen[key]) return;
        mergedSeen[key] = 1;
        merged.push({ k: h.k, v: h.v });
    });
    history = merged.slice(0, MAX);
    saveHistory(history);
    if (history.length) {
        clearEmpty();
        history.forEach(function (h) { feed.appendChild(chipEl(h.k, h.v)); });
    }

    // 1) React to real user actions only: viewed, searched, added-to-cart. (No dwell/hover.)
    window.addEventListener("nc:signal", function (e) {
        var ev = e.detail || {};
        var p = ev.payload || {};
        if (ev.event_type === "product_view") {
            addChip("Viewed", p.title || ("course #" + ev.product_id));
            noteCategory(p.category);
        } else if (ev.event_type === "search") {
            if (!p.partial && p.query) addChip("Searched", "“" + p.query + "”");
        } else if (ev.event_type === "click" && p.label === "add_to_cart") {
            addChip("Added to cart", p.title || "a course");
        }
    });

    // 2) Seed a "Viewed" chip on the product detail page.
    if (panel && panel.getAttribute("data-seed-title")) {
        var title = panel.getAttribute("data-seed-title");
        var cat = panel.getAttribute("data-seed-category");
        setTimeout(function () { addChip("Viewed", title); noteCategory(cat); noteCategory(cat); }, 400);
    }
    // Cart handling lives in cart.js (loaded on every page, unlike this panel-scoped script).
})();
