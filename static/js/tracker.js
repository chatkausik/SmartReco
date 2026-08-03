// SmartReco behavioral tracker — batched, throttled, non-blocking.
//
// Design goals (judged): never block or slow the UX.
//   - Events queue in memory and flush on: batch-size threshold, an idle debounce timer,
//     or page hide/unload (via navigator.sendBeacon, which the browser guarantees to deliver
//     without holding up navigation).
//   - Normal flushes use fetch(keepalive:true) fire-and-forget — the response is never awaited.
//   - High-frequency signals are pre-aggregated client-side (time-on-page accumulated and
//     emitted once; search debounced) so we never emit per-scroll / per-keystroke events.
(function () {
    "use strict";

    var ENDPOINT = "/api/events";
    var BATCH_SIZE = 20;         // flush once this many events are queued
    var IDLE_FLUSH_MS = 5000;    // ...or after this much idle time with a non-empty queue
    var SEARCH_DEBOUNCE_MS = 600;

    var queue = [];
    var idleTimer = null;

    // Stable per-browser session id, grouping a browsing session across page loads.
    var sessionId = localStorage.getItem("sr_session_id");
    if (!sessionId) {
        sessionId = (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random());
        localStorage.setItem("sr_session_id", sessionId);
    }

    function track(eventType, payload, productId) {
        queue.push({
            event_type: eventType,
            product_id: productId != null ? productId : null,
            payload: payload || {},
            session_id: sessionId,
            client_ts: new Date().toISOString()
        });
        if (queue.length >= BATCH_SIZE) {
            flush(false);
        } else {
            scheduleIdleFlush();
        }
    }

    function scheduleIdleFlush() {
        if (idleTimer) clearTimeout(idleTimer);
        idleTimer = setTimeout(function () {
            // Do the non-urgent flush during idle time so we never compete with rendering.
            if (window.requestIdleCallback) {
                requestIdleCallback(function () { flush(false); });
            } else {
                flush(false);
            }
        }, IDLE_FLUSH_MS);
    }

    function flush(useBeacon) {
        if (idleTimer) { clearTimeout(idleTimer); idleTimer = null; }
        if (queue.length === 0) return;
        var batch = queue;
        queue = [];
        var body = JSON.stringify({ events: batch });

        if (useBeacon && navigator.sendBeacon) {
            // text/plain: the Beacon API can't set arbitrary headers; the server parses raw body.
            navigator.sendBeacon(ENDPOINT, new Blob([body], { type: "text/plain;charset=UTF-8" }));
            return;
        }
        // Fire-and-forget; keepalive lets it survive a subsequent navigation. Never awaited.
        try {
            fetch(ENDPOINT, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: body,
                keepalive: true
            }).catch(function () { /* telemetry failures must stay invisible to the user */ });
        } catch (e) { /* ignore */ }
    }

    // ---- Auto-instrumentation ----------------------------------------------

    // Page view on load.
    track("page_view", { path: location.pathname + location.search });

    // Product view: any page carrying data-product-id on <body> (set by product detail template).
    var pv = document.body && document.body.getAttribute("data-product-id");
    if (pv) {
        track("product_view", { path: location.pathname }, parseInt(pv, 10));
    }

    // Click tracking via a single delegated listener on [data-track-click] elements.
    document.addEventListener("click", function (ev) {
        var el = ev.target.closest ? ev.target.closest("[data-track-click]") : null;
        if (!el) return;
        var pid = el.getAttribute("data-product-id");
        track("click", { label: el.getAttribute("data-track-label") || el.textContent.trim().slice(0, 60) },
            pid ? parseInt(pid, 10) : null);
    }, true);

    // Search: debounced on input, plus an immediate track on submit.
    var searchInput = document.querySelector('input[type="search"], input[name="q"]');
    if (searchInput) {
        var t = null;
        searchInput.addEventListener("input", function () {
            if (t) clearTimeout(t);
            var val = searchInput.value.trim();
            if (!val) return;
            t = setTimeout(function () { track("search", { query: val, partial: true }); }, SEARCH_DEBOUNCE_MS);
        });
        var form = searchInput.closest("form");
        if (form) {
            form.addEventListener("submit", function () {
                var val = searchInput.value.trim();
                if (val) track("search", { query: val, partial: false });
                flush(true); // ensure the search event isn't lost to the navigation
            });
        }
    }

    // Time spent: accumulate visible time, emit once on hide/unload (not per tick).
    var visibleSince = Date.now();
    var accumulatedMs = 0;
    function accumulate() {
        if (visibleSince != null) {
            accumulatedMs += Date.now() - visibleSince;
            visibleSince = null;
        }
    }
    function emitTimeSpent() {
        accumulate();
        if (accumulatedMs > 1000) {
            track("time_spent", { path: location.pathname, duration_ms: accumulatedMs }, pv ? parseInt(pv, 10) : null);
        }
        accumulatedMs = 0;
    }

    document.addEventListener("visibilitychange", function () {
        if (document.visibilityState === "hidden") {
            emitTimeSpent();
            flush(true);
        } else {
            visibleSince = Date.now();
        }
    });
    window.addEventListener("pagehide", function () {
        emitTimeSpent();
        flush(true);
    });

    // Expose for manual tracking from templates if needed.
    window.SmartRecoTracker = { track: track, flush: flush, sessionId: sessionId };
})();
