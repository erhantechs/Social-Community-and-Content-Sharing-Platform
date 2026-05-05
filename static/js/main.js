/* SocialHub — small UI behaviors: AJAX like, AJAX follow. */

(function () {
    "use strict";

    // CSRF helper (Django docs pattern)
    function getCookie(name) {
        const cookies = document.cookie ? document.cookie.split(";") : [];
        for (let c of cookies) {
            c = c.trim();
            if (c.startsWith(name + "=")) {
                return decodeURIComponent(c.slice(name.length + 1));
            }
        }
        return null;
    }

    const csrftoken = getCookie("csrftoken");

    async function postAjax(url) {
        const res = await fetch(url, {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "X-Requested-With": "XMLHttpRequest",
                "X-CSRFToken": csrftoken,
                "Accept": "application/json",
            },
        });
        if (!res.ok) throw new Error("Request failed: " + res.status);
        return res.json();
    }

    // ---------- AJAX like ----------
    document.body.addEventListener("click", async function (ev) {
        const btn = ev.target.closest(".js-like-btn");
        if (!btn) return;
        ev.preventDefault();
        if (btn.disabled) return;
        btn.disabled = true;
        try {
            const data = await postAjax(btn.dataset.url);
            if (data && data.ok) {
                const icon = btn.querySelector("i");
                const label = btn.querySelector(".js-like-label");
                const count = btn.querySelector(".js-like-count");
                if (data.liked) {
                    btn.classList.add("post-card__action--active");
                    if (icon) { icon.classList.remove("bi-heart"); icon.classList.add("bi-heart-fill"); }
                    if (label) label.textContent = "Liked";
                } else {
                    btn.classList.remove("post-card__action--active");
                    if (icon) { icon.classList.remove("bi-heart-fill"); icon.classList.add("bi-heart"); }
                    if (label) label.textContent = "Like";
                }
                if (count) count.textContent = data.likes_count;
            }
        } catch (err) {
            // Auth required or server error — let the form fall back to a normal nav.
            window.location.href = btn.dataset.url;
        } finally {
            btn.disabled = false;
        }
    });

    // ---------- AJAX bookmark ----------
    document.body.addEventListener("click", async function (ev) {
        const btn = ev.target.closest(".js-bookmark-btn");
        if (!btn) return;
        ev.preventDefault();
        if (btn.disabled) return;
        btn.disabled = true;
        try {
            const data = await postAjax(btn.dataset.url);
            if (data && data.ok) {
                const icon = btn.querySelector("i");
                const label = btn.querySelector(".js-bookmark-label");
                if (data.bookmarked) {
                    btn.classList.add("post-card__action--bookmarked");
                    if (icon) { icon.classList.remove("bi-bookmark"); icon.classList.add("bi-bookmark-fill"); }
                    if (label) label.textContent = "Saved";
                } else {
                    btn.classList.remove("post-card__action--bookmarked");
                    if (icon) { icon.classList.remove("bi-bookmark-fill"); icon.classList.add("bi-bookmark"); }
                    if (label) label.textContent = "Save";
                }
            }
        } catch (err) {
            window.location.reload();
        } finally {
            btn.disabled = false;
        }
    });

    // ---------- AJAX follow ----------
    document.body.addEventListener("click", async function (ev) {
        const btn = ev.target.closest(".js-follow-btn");
        if (!btn) return;
        ev.preventDefault();
        if (btn.disabled) return;
        btn.disabled = true;
        try {
            const data = await postAjax(btn.dataset.url);
            if (data && data.ok) {
                if (data.following) {
                    btn.textContent = "Following";
                    btn.classList.add("is-following");
                } else {
                    btn.textContent = "Follow";
                    btn.classList.remove("is-following");
                }
            }
        } catch (err) {
            window.location.href = btn.dataset.url;
        } finally {
            btn.disabled = false;
        }
    });

    // ---------- Reply form toggle ----------
    document.body.addEventListener("click", function (ev) {
        const btn = ev.target.closest(".js-reply-toggle");
        if (!btn) return;
        const target = document.getElementById(btn.dataset.target);
        if (!target) return;
        target.hidden = !target.hidden;
        if (!target.hidden) {
            const input = target.querySelector("input[name='body']");
            if (input) input.focus();
        }
    });

    // ---------- AJAX comment like ----------
    document.body.addEventListener("click", async function (ev) {
        const btn = ev.target.closest(".js-comment-like-btn");
        if (!btn) return;
        ev.preventDefault();
        if (btn.disabled) return;
        btn.disabled = true;
        try {
            const data = await postAjax(btn.dataset.url);
            if (data && data.ok) {
                const icon = btn.querySelector("i");
                const count = btn.querySelector(".js-cl-count");
                if (data.liked) {
                    btn.classList.add("is-active");
                    if (icon) { icon.classList.remove("bi-heart"); icon.classList.add("bi-heart-fill"); }
                } else {
                    btn.classList.remove("is-active");
                    if (icon) { icon.classList.remove("bi-heart-fill"); icon.classList.add("bi-heart"); }
                }
                if (count) count.textContent = data.likes_count;
            }
        } catch (err) {
            // Fall back to a normal navigation if AJAX failed (e.g. session expired).
            window.location.reload();
        } finally {
            btn.disabled = false;
        }
    });

    // ---------- Dark mode toggle ----------
    document.querySelectorAll(".js-theme-toggle").forEach(function (btn) {
        btn.addEventListener("click", function () {
            const current = document.documentElement.getAttribute("data-theme") || "light";
            const next = current === "dark" ? "light" : "dark";
            document.documentElement.setAttribute("data-theme", next);
            try { localStorage.setItem("socialhub-theme", next); } catch (e) {}
        });
    });

    // ---------- Notification dropdown ----------
    const bell = document.querySelector(".js-notif-bell");
    const drop = document.querySelector(".js-notif-dropdown");
    if (bell && drop) {
        const list = drop.querySelector(".js-notif-list");
        const badge = bell.querySelector(".js-notif-badge");
        const markBtn = drop.querySelector(".js-notif-mark-read");
        let loaded = false;

        function escapeHtml(s) {
            const div = document.createElement("div");
            div.textContent = s == null ? "" : s;
            return div.innerHTML;
        }

        function timeAgo(iso) {
            const seconds = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
            const intervals = [
                [60, "s"], [60, "m"], [24, "h"], [7, "d"], [4, "w"], [12, "mo"], [10, "y"],
            ];
            let value = seconds;
            let unit = "s";
            for (const [step, label] of intervals) {
                if (value < step) { unit = label; break; }
                value = Math.floor(value / step);
                unit = label;
            }
            return value + unit;
        }

        async function loadNotifications() {
            try {
                const res = await fetch(bell.dataset.url, {
                    credentials: "same-origin",
                    headers: { "X-Requested-With": "XMLHttpRequest", "Accept": "application/json" },
                });
                if (!res.ok) throw new Error();
                const data = await res.json();
                if (badge) {
                    if (data.unread > 0) {
                        badge.textContent = data.unread;
                        badge.hidden = false;
                    } else {
                        badge.hidden = true;
                    }
                }
                if (data.items.length === 0) {
                    list.innerHTML = '<li class="empty-tiny text-center py-3">No notifications yet</li>';
                    return;
                }
                list.innerHTML = data.items.map(function (n) {
                    const avatar = n.actor.avatar_url
                        ? `<img src="${escapeHtml(n.actor.avatar_url)}" alt="${escapeHtml(n.actor.name)}">`
                        : '<div class="avatar-placeholder"><i class="bi bi-person-fill"></i></div>';
                    const target = n.post_url || n.actor.profile_url;
                    return `
                        <li class="notif-dropdown__item ${n.is_read ? "" : "notif-dropdown__item--unread"}">
                            <a href="${escapeHtml(target)}">
                                <span class="notif-dropdown__avatar">${avatar}</span>
                                <span class="notif-dropdown__text">
                                    <strong>${escapeHtml(n.actor.name)}</strong>
                                    ${escapeHtml(n.verb)}
                                </span>
                                <span class="notif-dropdown__time">${timeAgo(n.created_at)}</span>
                            </a>
                        </li>`;
                }).join("");
            } catch (e) {
                list.innerHTML = '<li class="empty-tiny text-center py-3">Couldn\'t load notifications</li>';
            }
        }

        bell.addEventListener("click", function (ev) {
            ev.stopPropagation();
            const willShow = drop.hidden;
            drop.hidden = !willShow;
            if (willShow && !loaded) {
                loaded = true;
                loadNotifications();
            }
        });

        document.addEventListener("click", function (ev) {
            if (!drop.hidden && !drop.contains(ev.target) && !bell.contains(ev.target)) {
                drop.hidden = true;
            }
        });

        if (markBtn) {
            markBtn.addEventListener("click", async function () {
                try {
                    await fetch(bell.dataset.markUrl, {
                        method: "POST",
                        credentials: "same-origin",
                        headers: {
                            "X-Requested-With": "XMLHttpRequest",
                            "X-CSRFToken": csrftoken,
                        },
                    });
                    loaded = false;
                    if (badge) badge.hidden = true;
                    loadNotifications();
                } catch (e) { /* ignore */ }
            });
        }

        // Refresh badge every 60 seconds while the page is open.
        setInterval(loadNotifications, 60000);
    }

    // ---------- Composer image preview ----------
    document.querySelectorAll(".js-composer").forEach(function (form) {
        const input = form.querySelector(".js-composer-image");
        const preview = form.querySelector(".js-composer-preview");
        const previewImg = form.querySelector(".js-composer-preview-img");
        const clearBtn = form.querySelector(".js-composer-preview-clear");
        if (!input || !preview) return;

        input.addEventListener("change", function () {
            const file = input.files && input.files[0];
            if (!file || !file.type.startsWith("image/")) {
                preview.hidden = true;
                return;
            }
            const reader = new FileReader();
            reader.onload = function (e) {
                previewImg.src = e.target.result;
                preview.hidden = false;
            };
            reader.readAsDataURL(file);
        });

        if (clearBtn) {
            clearBtn.addEventListener("click", function () {
                input.value = "";
                preview.hidden = true;
                previewImg.src = "";
            });
        }
    });

    // ---------- Standalone image input preview (post_form / story_form) ----------
    document.querySelectorAll(".js-image-input").forEach(function (input) {
        const previewId = input.dataset.preview;
        const preview = previewId && document.getElementById(previewId);
        if (!preview) return;
        const img = preview.querySelector("img") || (function () {
            const i = document.createElement("img");
            preview.appendChild(i);
            return i;
        })();
        input.addEventListener("change", function () {
            const file = input.files && input.files[0];
            if (!file || !file.type.startsWith("image/")) {
                preview.hidden = true;
                return;
            }
            const reader = new FileReader();
            reader.onload = function (e) {
                img.src = e.target.result;
                preview.hidden = false;
            };
            reader.readAsDataURL(file);
        });
    });

    // ---------- Story modal (animated zoom-from-card) ----------
    const storyModalEl = document.getElementById("storyModal");
    if (storyModalEl) {
        const bsModal = new bootstrap.Modal(storyModalEl);
        const dialogEl = storyModalEl.querySelector(".modal-dialog");
        const imgEl = storyModalEl.querySelector(".story-modal__image");
        const avatarEl = storyModalEl.querySelector(".story-modal__avatar");
        const authorEl = storyModalEl.querySelector(".story-modal__author");
        const timeEl = storyModalEl.querySelector(".story-modal__time");
        const captionEl = storyModalEl.querySelector(".story-modal__caption");
        const progressEl = storyModalEl.querySelector(".story-modal__progress-bar");

        const STORY_DURATION_MS = 5000;
        let autoCloseTimer = null;

        function startProgress() {
            if (!progressEl) return;
            progressEl.style.transition = "none";
            progressEl.style.width = "0%";
            // Force a reflow so the next assignment actually animates.
            void progressEl.offsetWidth;
            progressEl.style.transition = `width ${STORY_DURATION_MS}ms linear`;
            progressEl.style.width = "100%";
        }

        function clearTimers() {
            if (autoCloseTimer) { clearTimeout(autoCloseTimer); autoCloseTimer = null; }
        }

        // Animate the modal so it appears to grow OUT of the clicked card.
        // We compute a transform-origin in viewport-percent space so the spring
        // animation in CSS pivots from the card's centre.
        function setOriginFrom(cardEl) {
            if (!dialogEl || !cardEl) {
                if (dialogEl) dialogEl.style.transformOrigin = "";
                return;
            }
            const rect = cardEl.getBoundingClientRect();
            const cx = rect.left + rect.width / 2;
            const cy = rect.top + rect.height / 2;
            const xPct = (cx / window.innerWidth) * 100;
            const yPct = (cy / window.innerHeight) * 100;
            dialogEl.style.transformOrigin = `${xPct}% ${yPct}%`;
        }

        document.body.addEventListener("click", function (ev) {
            const card = ev.target.closest(".js-story-open");
            if (!card) return;
            ev.preventDefault();

            // Populate content first so the open-animation has the right size.
            imgEl.src = card.dataset.image || "";
            const av = card.dataset.avatar;
            if (av) {
                avatarEl.src = av;
                avatarEl.style.display = "";
            } else {
                avatarEl.style.display = "none";
            }
            authorEl.textContent = card.dataset.author || "";
            timeEl.textContent = card.dataset.time || "";
            captionEl.textContent = card.dataset.caption || "";
            captionEl.style.display = card.dataset.caption ? "" : "none";

            // Pivot the zoom animation from the clicked card's centre.
            setOriginFrom(card);

            // Wait until the image is loaded before starting the progress bar
            // and auto-close timer — otherwise a slow image makes the timer
            // race ahead and close the modal before the picture is even up.
            const onReadyToCount = () => {
                startProgress();
                clearTimers();
                autoCloseTimer = setTimeout(() => bsModal.hide(), STORY_DURATION_MS);
            };

            if (imgEl.complete && imgEl.naturalWidth > 0) {
                onReadyToCount();
            } else {
                imgEl.addEventListener("load", onReadyToCount, { once: true });
                imgEl.addEventListener("error", onReadyToCount, { once: true });
            }

            bsModal.show();
        });

        storyModalEl.addEventListener("hidden.bs.modal", function () {
            clearTimers();
            // Reset transform-origin so the next open recalculates fresh.
            if (dialogEl) dialogEl.style.transformOrigin = "";
            if (progressEl) {
                progressEl.style.transition = "none";
                progressEl.style.width = "0%";
            }
        });

        // Pause auto-close while the user is hovering / pressing on the modal
        // (Instagram behaviour — tap and hold pauses the story).
        let pausedAt = null;
        storyModalEl.addEventListener("pointerdown", function () {
            pausedAt = Date.now();
            clearTimers();
            if (progressEl) {
                const cs = getComputedStyle(progressEl);
                progressEl.style.transition = "none";
                progressEl.style.width = cs.width;
            }
        });
        storyModalEl.addEventListener("pointerup", function () {
            if (pausedAt == null || !progressEl) return;
            const currentPct = parseFloat(progressEl.style.width) /
                               progressEl.parentElement.getBoundingClientRect().width * 100;
            const remaining = STORY_DURATION_MS * (1 - Math.min(currentPct / 100, 1));
            void progressEl.offsetWidth;
            progressEl.style.transition = `width ${remaining}ms linear`;
            progressEl.style.width = "100%";
            autoCloseTimer = setTimeout(() => bsModal.hide(), remaining);
            pausedAt = null;
        });
    }

    // Auto-dismiss flash messages after 4s
    setTimeout(function () {
        document.querySelectorAll(".messages-area .alert").forEach(function (el) {
            el.classList.remove("show");
            setTimeout(function () { el.remove(); }, 300);
        });
    }, 4000);
})();
