// Lightweight client-side cart. Loaded on every page (independent of the signal panel).
// Stores items in localStorage as nc_cart_items = [{id, title, price}], keeps the nav badge
// in sync, and renders the /cart page.
(function () {
    "use strict";
    var KEY = "nc_cart_items";

    function load() {
        try { return JSON.parse(localStorage.getItem(KEY)) || []; } catch (e) { return []; }
    }
    function save(items) {
        try { localStorage.setItem(KEY, JSON.stringify(items)); } catch (e) {}
    }
    function updateBadge() {
        var cc = document.getElementById("cart-count");
        if (!cc) return;
        var n = load().length;
        if (n > 0) { cc.textContent = n; cc.hidden = false; } else { cc.hidden = true; }
    }

    function addItem(item) {
        var items = load();
        if (items.some(function (it) { return String(it.id) === String(item.id); })) return false; // already in cart
        items.push(item);
        save(items);
        updateBadge();
        return true;
    }

    function monogramFor(title) {
        var stop = { with: 1, for: 1, and: 1, the: 1, to: 1, of: 1, a: 1, in: 1, on: 1, your: 1, you: 1 };
        var letters = (title || "").split(/\s+/)
            .filter(function (w) { return w && !stop[w.toLowerCase()]; })
            .map(function (w) { return w[0]; }).join("").slice(0, 3);
        return (letters || (title || "?").slice(0, 3)).toUpperCase();
    }
    function gradient(hue) {
        var h = parseInt(hue, 10); if (isNaN(h)) h = 262;
        return "linear-gradient(150deg, hsl(" + h + " 72% 63%), hsl(" + ((h + 34) % 360) + " 64% 47%))";
    }
    function removeItem(id) {
        save(load().filter(function (it) { return String(it.id) !== String(id); }));
        updateBadge();
        renderCartPage();
    }

    // Add-to-cart buttons (delegated so it works no matter when they render).
    document.addEventListener("click", function (ev) {
        var btn = ev.target.closest ? ev.target.closest("[data-add-cart]") : null;
        if (!btn) return;
        ev.preventDefault();
        var added = addItem({
            id: btn.getAttribute("data-product-id"),
            title: btn.getAttribute("data-title") || "Course",
            price: parseFloat(btn.getAttribute("data-price") || "0"),
            category: btn.getAttribute("data-category") || "",
            monogram: btn.getAttribute("data-monogram") || "",
            hue: btn.getAttribute("data-hue") || ""
        });
        var original = btn.getAttribute("data-label") || btn.innerHTML;
        if (!btn.getAttribute("data-label")) btn.setAttribute("data-label", original);
        btn.textContent = added ? "✓ Added to cart" : "✓ Already in cart";
        setTimeout(function () { btn.innerHTML = btn.getAttribute("data-label"); }, 1400);
    });

    // /cart page rendering.
    function renderCartPage() {
        var root = document.getElementById("cart-page");
        if (!root) return;
        var items = load();
        if (!items.length) {
            root.innerHTML = '<p class="muted">Your cart is empty. <a href="/" style="color:var(--accent-2)">Browse courses →</a></p>';
            return;
        }
        var total = 0;
        var rows = items.map(function (it) {
            total += Number(it.price) || 0;
            var mono = it.monogram || monogramFor(it.title);
            var href = "/products/" + encodeURIComponent(it.id);
            return '<div class="cart-item">' +
                '<a class="cart-thumb" href="' + href + '" style="background:' + gradient(it.hue) + '">' +
                    '<span class="cart-mono">' + esc(mono) + "</span>" +
                "</a>" +
                '<div class="cart-item-info">' +
                    (it.category ? '<span class="cart-item-cat">' + esc(it.category) + "</span>" : "") +
                    '<a class="cart-item-title" href="' + href + '">' + esc(it.title) + "</a>" +
                    '<span class="cart-item-price">$' + (Number(it.price) || 0).toFixed(0) + "</span>" +
                "</div>" +
                '<button class="btn-ghost cart-remove" data-remove="' + esc(it.id) + '">Remove</button>' +
                "</div>";
        }).join("");
        root.innerHTML =
            '<div class="cart-list">' + rows + "</div>" +
            '<div class="cart-total"><span>Total</span><span>$' + total.toFixed(0) + "</span></div>" +
            '<a class="btn" href="/">Continue browsing</a>';
        root.querySelectorAll("[data-remove]").forEach(function (b) {
            b.addEventListener("click", function () { removeItem(b.getAttribute("data-remove")); });
        });
    }
    function esc(s) { var d = document.createElement("div"); d.textContent = s == null ? "" : String(s); return d.innerHTML; }

    updateBadge();
    renderCartPage();
})();
