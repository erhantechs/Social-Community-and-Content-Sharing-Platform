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

    async function postAjax(url, body) {
        const opts = {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "X-Requested-With": "XMLHttpRequest",
                "X-CSRFToken": csrftoken,
                "Accept": "application/json",
            },
        };
        if (body !== undefined) {
            opts.body = body;
        }
        const res = await fetch(url, opts);
        if (!res.ok) throw new Error("Request failed: " + res.status);
        return res.json();
    }

    // Toggle a button's loading state. Adds .btn--loading (CSS draws a spinner
    // overlay and hides label) while the request is in flight, then restores.
    function setBtnLoading(btn, loading) {
        if (!btn) return;
        if (loading) {
            btn.classList.add("btn--loading");
            btn.setAttribute("aria-busy", "true");
            btn.disabled = true;
        } else {
            btn.classList.remove("btn--loading");
            btn.removeAttribute("aria-busy");
            btn.disabled = false;
        }
    }

    // ---------- AJAX like (optimistic) ----------
    // Update the UI immediately, then reconcile with the server. If the
    // request fails we revert to the previous state — matches modern
    // social-app feel (Twitter, Instagram, etc.).
    const EMOJI_MAP = {
        heart: "❤️", laugh: "😂", fire: "🔥",
        sad: "😢", wow: "😮", clap: "👏",
    };

    function applyReactionState(btn, emoji, count) {
        const emojiEl = btn.querySelector(".js-like-emoji");
        const label = btn.querySelector(".js-like-label");
        const cnt = btn.querySelector(".js-like-count");
        const isReacted = !!emoji;
        btn.classList.toggle("post-card__action--active", isReacted);
        btn.dataset.emoji = emoji || "";
        if (emojiEl) {
            emojiEl.innerHTML = isReacted
                ? EMOJI_MAP[emoji] || "❤️"
                : '<i class="bi bi-heart"></i>';
        }
        if (label) label.textContent = isReacted ? "Reacted" : "React";
        if (cnt && typeof count === "number") cnt.textContent = count;
    }

    async function sendReaction(btn, emoji) {
        const cnt = btn.querySelector(".js-like-count");
        const oldCount = parseInt((cnt && cnt.textContent) || "0", 10) || 0;
        const oldEmoji = btn.dataset.emoji || "";

        // Optimistic update.
        let nextEmoji, nextCount;
        if (oldEmoji === emoji) {
            // Toggle off.
            nextEmoji = ""; nextCount = Math.max(0, oldCount - 1);
        } else if (!oldEmoji) {
            nextEmoji = emoji; nextCount = oldCount + 1;
        } else {
            // Switching reaction — count stays the same.
            nextEmoji = emoji; nextCount = oldCount;
        }
        applyReactionState(btn, nextEmoji, nextCount);

        // Pop animation.
        btn.classList.remove("post-card__action--pop");
        void btn.offsetWidth;
        btn.classList.add("post-card__action--pop");

        btn.disabled = true;
        try {
            const fd = new FormData();
            fd.append("emoji", emoji);
            const data = await postAjax(btn.dataset.url, fd);
            if (data && data.ok) {
                applyReactionState(btn, data.emoji || "", data.likes_count);
            }
        } catch (err) {
            applyReactionState(btn, oldEmoji, oldCount);
        } finally {
            btn.disabled = false;
        }
    }

    // Default-click on the like button = toggle heart.
    document.body.addEventListener("click", function (ev) {
        const pickItem = ev.target.closest(".js-reaction-pick");
        if (pickItem) {
            ev.preventDefault();
            const wrap = pickItem.closest(".reaction-wrap");
            const btn = wrap && wrap.querySelector(".js-like-btn");
            const picker = wrap && wrap.querySelector(".js-reaction-picker");
            if (picker) picker.hidden = true;
            if (btn) sendReaction(btn, pickItem.dataset.emoji);
            return;
        }
        const btn = ev.target.closest(".js-like-btn");
        if (!btn) return;
        ev.preventDefault();
        if (btn.disabled) return;
        const wrap = btn.closest(".reaction-wrap");
        const picker = wrap && wrap.querySelector(".js-reaction-picker");
        // If picker is currently open, treat click as "close + toggle current".
        if (picker && !picker.hidden) {
            picker.hidden = true;
            return;
        }
        const current = btn.dataset.emoji || "";
        sendReaction(btn, current || "heart");
    });

    // Hover (desktop) or long-press (touch) opens the reaction picker.
    // Open on the like button OR when the cursor enters the picker itself,
    // so traveling from the button up to the emojis keeps it open.
    document.body.addEventListener("mouseenter", function (ev) {
        const t = ev.target;
        if (!t.closest) return;
        const wrap = t.closest(".reaction-wrap");
        if (!wrap) return;
        if (!t.closest(".js-like-btn") && !t.closest(".js-reaction-picker")) return;
        const picker = wrap.querySelector(".js-reaction-picker");
        if (picker) {
            clearTimeout(wrap._hideTimer);
            picker.hidden = false;
        }
    }, true);
    document.body.addEventListener("mouseleave", function (ev) {
        const wrap = ev.target.closest && ev.target.closest(".reaction-wrap");
        if (!wrap) return;
        const picker = wrap.querySelector(".js-reaction-picker");
        if (!picker) return;
        clearTimeout(wrap._hideTimer);
        wrap._hideTimer = setTimeout(() => { picker.hidden = true; }, 220);
    }, true);

    // Long-press for touch devices.
    let lpTimer = null;
    document.body.addEventListener("touchstart", function (ev) {
        const btn = ev.target.closest(".js-like-btn");
        if (!btn) return;
        const wrap = btn.closest(".reaction-wrap");
        const picker = wrap && wrap.querySelector(".js-reaction-picker");
        if (!picker) return;
        lpTimer = setTimeout(() => { picker.hidden = false; }, 380);
    }, { passive: true });
    document.body.addEventListener("touchend", function () { clearTimeout(lpTimer); });
    document.body.addEventListener("touchmove", function () { clearTimeout(lpTimer); });

    // Keyboard navigation for the reaction picker (when it's open).
    document.body.addEventListener("keydown", function (ev) {
        const picker = ev.target.closest(".reaction-picker");
        if (!picker || picker.hidden) return;
        const items = [...picker.querySelectorAll(".js-reaction-pick")];
        if (!items.length) return;
        const idx = items.indexOf(document.activeElement);
        if (ev.key === "ArrowRight" || ev.key === "ArrowDown") {
            ev.preventDefault();
            const next = items[(idx + 1 + items.length) % items.length];
            next && next.focus();
        } else if (ev.key === "ArrowLeft" || ev.key === "ArrowUp") {
            ev.preventDefault();
            const prev = items[(idx - 1 + items.length) % items.length];
            prev && prev.focus();
        } else if (ev.key === "Escape") {
            picker.hidden = true;
            const wrap = picker.closest(".reaction-wrap");
            const btn = wrap && wrap.querySelector(".js-like-btn");
            btn && btn.focus();
        } else if (ev.key === "Home") {
            ev.preventDefault();
            items[0].focus();
        } else if (ev.key === "End") {
            ev.preventDefault();
            items[items.length - 1].focus();
        }
    });

    // Open the picker when the like-button receives keyboard focus & is pressed
    // with ArrowDown/ArrowUp (industry pattern for menu buttons).
    document.body.addEventListener("keydown", function (ev) {
        const btn = ev.target.closest(".js-like-btn");
        if (!btn) return;
        if (ev.key !== "ArrowDown" && ev.key !== "ArrowUp") return;
        ev.preventDefault();
        const wrap = btn.closest(".reaction-wrap");
        const picker = wrap && wrap.querySelector(".js-reaction-picker");
        if (!picker) return;
        picker.hidden = false;
        const items = picker.querySelectorAll(".js-reaction-pick");
        if (items.length) items[0].focus();
    });

    // ---------- Poll voting ----------
    // Single-choice: clicking an option submits immediately.
    // Multiple-choice: clicking toggles selection; user clicks "Submit vote" to send.
    document.body.addEventListener("click", async function (ev) {
        const opt = ev.target.closest(".js-poll-vote");
        if (!opt) return;
        ev.preventDefault();
        if (opt.disabled) return;
        const poll = opt.closest(".poll");
        if (!poll) return;
        const isMultiple = poll.dataset.multiple === "true";

        if (isMultiple) {
            opt.classList.toggle("poll-option--selected");
            opt.setAttribute("aria-pressed", opt.classList.contains("poll-option--selected"));
            updateMultiSelectState(poll);
            return;
        }

        const fd = new FormData();
        fd.append("option_id", opt.dataset.optionId);
        await submitPollVote(poll, fd, opt);
    });

    document.body.addEventListener("click", async function (ev) {
        const submit = ev.target.closest(".js-poll-submit");
        if (!submit || submit.disabled) return;
        ev.preventDefault();
        const poll = submit.closest(".poll");
        if (!poll) return;
        const fd = new FormData();
        poll.querySelectorAll(".poll-option--selected").forEach(o => {
            fd.append("option_ids", o.dataset.optionId);
        });
        if (![...fd.keys()].length) return;
        await submitPollVote(poll, fd, submit);
    });

    function updateMultiSelectState(poll) {
        const selected = poll.querySelectorAll(".poll-option--selected").length;
        const submit = poll.querySelector(".js-poll-submit");
        const counter = poll.querySelector(".js-poll-selected-count");
        if (submit) submit.disabled = selected === 0;
        if (counter) {
            counter.textContent = selected === 0
                ? "No options selected"
                : `${selected} option${selected === 1 ? "" : "s"} selected`;
        }
    }

    async function submitPollVote(poll, formData, busyEl) {
        const url = poll.dataset.voteUrl;
        if (busyEl) busyEl.disabled = true;
        try {
            const data = await postAjax(url, formData);
            if (data && data.ok) {
                renderPollResults(poll, data);
            }
        } catch (err) {
            poll.querySelectorAll(".poll-option--selected").forEach(o => {
                o.classList.remove("poll-option--selected");
                o.setAttribute("aria-pressed", "false");
            });
            updateMultiSelectState(poll);
        } finally {
            if (busyEl) busyEl.disabled = false;
        }
    }

    function renderPollResults(poll, data) {
        const optionsWrap = poll.querySelector(".poll__options");
        const total = data.total || 0;
        const votedFor = new Set((data.voted_for || []).map(String));
        if (!optionsWrap) return;
        optionsWrap.innerHTML = "";
        (data.options || []).forEach(o => {
            const isMine = votedFor.has(String(o.id));
            const html = `
                <div class="poll-option poll-option--result ${isMine ? "poll-option--mine" : ""}" data-option-id="${o.id}">
                    <div class="poll-option__bar" style="width: ${o.percent}%;"></div>
                    <div class="poll-option__row">
                        <span class="poll-option__text">
                            ${isMine ? '<i class="bi bi-check-circle-fill" aria-hidden="true"></i> ' : ""}
                            ${escapeHtml(o.text)}
                        </span>
                        <span class="poll-option__pct">${o.percent}%</span>
                    </div>
                </div>`;
            optionsWrap.insertAdjacentHTML("beforeend", html);
        });
        poll.classList.add("poll--results");
        const totalEl = poll.querySelector(".js-poll-total");
        if (totalEl) totalEl.textContent = total;
    }

    function escapeHtml(s) {
        const d = document.createElement("div");
        d.textContent = s == null ? "" : s;
        return d.innerHTML;
    }

    // ---------- Poll builder toggle (post create form) ----------
    document.body.addEventListener("click", function (ev) {
        const tog = ev.target.closest(".js-poll-toggle");
        if (!tog) return;
        const fields = document.getElementById("poll-fields");
        if (!fields) return;
        const open = fields.hidden;
        fields.hidden = !open;
        tog.setAttribute("aria-expanded", open ? "true" : "false");
        tog.classList.toggle("active", open);
    });

    // ---------- AJAX bookmark ----------
    document.body.addEventListener("click", async function (ev) {
        const btn = ev.target.closest(".js-bookmark-btn");
        if (!btn) return;
        ev.preventDefault();
        if (btn.disabled) return;
        setBtnLoading(btn, true);
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
            setBtnLoading(btn, false);
        }
    });

    // ---------- AJAX follow ----------
    document.body.addEventListener("click", async function (ev) {
        const btn = ev.target.closest(".js-follow-btn");
        if (!btn) return;
        ev.preventDefault();
        if (btn.disabled) return;
        setBtnLoading(btn, true);
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
            setBtnLoading(btn, false);
        }
    });

    // ---------- Comment edit (toggle + AJAX submit) ----------
    document.body.addEventListener("click", function (ev) {
        const btn = ev.target.closest(".js-comment-edit-btn, .js-comment-edit-cancel");
        if (!btn) return;
        const target = document.getElementById(btn.dataset.target);
        if (!target) return;
        const isCancel = btn.classList.contains("js-comment-edit-cancel");
        target.hidden = isCancel ? true : !target.hidden;
        if (!target.hidden) {
            const input = target.querySelector("input[name='body']");
            if (input) { input.focus(); input.setSelectionRange(input.value.length, input.value.length); }
        }
    });

    document.body.addEventListener("submit", async function (ev) {
        const form = ev.target.closest(".js-comment-edit-form");
        if (!form) return;
        ev.preventDefault();
        const fd = new FormData(form);
        try {
            const res = await fetch(form.action, {
                method: "POST",
                body: fd,
                credentials: "same-origin",
                headers: { "X-Requested-With": "XMLHttpRequest", "X-CSRFToken": csrftoken },
            });
            const data = await res.json();
            if (data.ok) {
                const bubble = form.closest(".comment-list__bubble");
                if (bubble) {
                    const bodyEl = bubble.querySelector(".js-comment-body");
                    if (bodyEl) bodyEl.innerHTML = data.body_html;
                    const meta = bubble.querySelector(".text-muted.small");
                    if (meta && data.edited && !meta.textContent.includes("edited")) {
                        meta.insertAdjacentHTML("beforeend", " · <em>edited</em>");
                    }
                }
                form.hidden = true;
            }
        } catch (e) {
            form.submit();   // fall back to normal POST
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
            // Refresh on every open so the list never goes stale.
            if (willShow) loadNotifications();
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

        // Group navigation (prev/next + keyboard arrows + touch swipe).
        let storyGroup = [];
        let storyIndex = 0;

        function loadStory(card) {
            imgEl.src = card.dataset.image || "";
            const av = card.dataset.avatar;
            if (av) { avatarEl.src = av; avatarEl.style.display = ""; }
            else    { avatarEl.style.display = "none"; }
            authorEl.textContent = card.dataset.author || "";
            timeEl.textContent = card.dataset.time || "";
            captionEl.textContent = card.dataset.caption || "";
            captionEl.style.display = card.dataset.caption ? "" : "none";

            const navPrev = storyModalEl.querySelector(".js-story-prev");
            const navNext = storyModalEl.querySelector(".js-story-next");
            if (navPrev) navPrev.style.visibility = storyGroup.length > 1 ? "" : "hidden";
            if (navNext) navNext.style.visibility = storyGroup.length > 1 ? "" : "hidden";

            const onReady = () => {
                startProgress();
                clearTimers();
                // Auto-advance to the next story when the timer elapses.
                autoCloseTimer = setTimeout(() => {
                    if (storyIndex < storyGroup.length - 1) {
                        storyIndex += 1;
                        loadStory(storyGroup[storyIndex]);
                    } else {
                        bsModal.hide();
                    }
                }, STORY_DURATION_MS);
            };
            if (imgEl.complete && imgEl.naturalWidth > 0) onReady();
            else {
                imgEl.addEventListener("load", onReady, { once: true });
                imgEl.addEventListener("error", onReady, { once: true });
            }
        }

        function gotoStory(delta) {
            const next = storyIndex + delta;
            if (next < 0 || next >= storyGroup.length) return;
            storyIndex = next;
            loadStory(storyGroup[storyIndex]);
        }

        document.body.addEventListener("click", function (ev) {
            const card = ev.target.closest(".js-story-open");
            if (!card) return;
            ev.preventDefault();
            storyGroup = Array.from(document.querySelectorAll(".js-story-open"));
            storyIndex = Math.max(0, storyGroup.indexOf(card));
            setOriginFrom(card);
            loadStory(card);
            bsModal.show();
        });

        const navPrevBtn = storyModalEl.querySelector(".js-story-prev");
        const navNextBtn = storyModalEl.querySelector(".js-story-next");
        if (navPrevBtn) navPrevBtn.addEventListener("click", (e) => { e.stopPropagation(); gotoStory(-1); });
        if (navNextBtn) navNextBtn.addEventListener("click", (e) => { e.stopPropagation(); gotoStory(1); });

        document.addEventListener("keydown", (ev) => {
            if (!storyModalEl.classList.contains("show")) return;
            if (ev.key === "ArrowLeft")  gotoStory(-1);
            if (ev.key === "ArrowRight") gotoStory(1);
        });

        // Touch swipe between stories.
        let touchStartX = null;
        storyModalEl.addEventListener("touchstart", (e) => {
            if (e.touches.length === 1) touchStartX = e.touches[0].clientX;
        }, { passive: true });
        storyModalEl.addEventListener("touchend", (e) => {
            if (touchStartX == null) return;
            const dx = e.changedTouches[0].clientX - touchStartX;
            if (Math.abs(dx) > 50) gotoStory(dx < 0 ? 1 : -1);
            touchStartX = null;
        }, { passive: true });

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

    // Show all server-rendered toasts on page load. Bootstrap handles
    // the entrance animation, hover-pause and the auto-dismiss timer
    // (data-bs-delay on the element).
    document.querySelectorAll(".toast-container .toast").forEach(function (el) {
        try {
            const t = bootstrap.Toast.getOrCreateInstance(el);
            t.show();
        } catch (e) { /* bootstrap not yet loaded — silent fallback */ }
    });

    // ---------- Bootstrap tooltips ----------
    // Any element with `data-bs-toggle="tooltip"` becomes hover-discoverable.
    document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(function (el) {
        try { new bootstrap.Tooltip(el, { delay: { show: 350, hide: 100 } }); }
        catch (e) { /* fallback to native title attribute */ }
    });

    // ---------- Onboarding modal ----------
    const onbEl = document.getElementById("onboardingModal");
    if (onbEl) {
        try {
            const m = new bootstrap.Modal(onbEl);
            m.show();
            const steps = onbEl.querySelectorAll(".js-onb-step");
            const dots = onbEl.querySelectorAll(".js-onb-dot");
            const nextBtn = onbEl.querySelector(".js-onb-next");
            const skipBtn = onbEl.querySelector(".js-onb-skip");
            const dismissUrl = onbEl.dataset.dismissUrl;
            let current = 1;
            function showStep(n) {
                current = n;
                steps.forEach(s => s.hidden = parseInt(s.dataset.step, 10) !== n);
                dots.forEach(d => d.classList.toggle(
                    "onboarding__dot--active",
                    parseInt(d.dataset.step, 10) === n,
                ));
                if (n === steps.length) {
                    nextBtn.innerHTML = 'Get started <i class="bi bi-check2"></i>';
                }
            }
            function dismiss() {
                fetch(dismissUrl, {
                    method: "POST",
                    credentials: "same-origin",
                    headers: { "X-CSRFToken": csrftoken, "X-Requested-With": "XMLHttpRequest" },
                }).catch(() => {});
                m.hide();
            }
            nextBtn.addEventListener("click", () => {
                if (current < steps.length) showStep(current + 1);
                else dismiss();
            });
            skipBtn.addEventListener("click", dismiss);
            showStep(1);
        } catch (e) { /* bootstrap not loaded yet */ }
    }

    // ---------- Password show/hide toggle ----------
    document.body.addEventListener("click", function (ev) {
        const btn = ev.target.closest(".js-password-toggle");
        if (!btn) return;
        const wrap = btn.closest(".password-wrap");
        const input = wrap && wrap.querySelector("input");
        if (!input) return;
        const isPwd = input.type === "password";
        input.type = isPwd ? "text" : "password";
        btn.setAttribute("aria-label", isPwd ? "Hide password" : "Show password");
        btn.setAttribute("aria-pressed", isPwd ? "true" : "false");
        const icon = btn.querySelector("i");
        if (icon) {
            icon.classList.toggle("bi-eye", !isPwd);
            icon.classList.toggle("bi-eye-slash", isPwd);
        }
    });

    // ---------- Password strength meter ----------
    function passwordStrength(pwd) {
        if (!pwd) return { score: 0, label: "" };
        let score = 0;
        if (pwd.length >= 8)  score += 1;
        if (pwd.length >= 12) score += 1;
        if (/[a-z]/.test(pwd) && /[A-Z]/.test(pwd)) score += 1;
        if (/\d/.test(pwd))   score += 1;
        if (/[^A-Za-z0-9]/.test(pwd)) score += 1;
        return { score, label: ["very weak", "weak", "okay", "good", "strong", "excellent"][score] };
    }
    document.querySelectorAll(".js-password-strength").forEach(function (wrap) {
        const targetId = wrap.dataset.target;
        const input = targetId && document.getElementById(targetId);
        if (!input) return;
        const fill = wrap.querySelector(".password-strength__fill");
        const label = wrap.querySelector(".password-strength__label");
        input.addEventListener("input", function () {
            const { score, label: text } = passwordStrength(input.value);
            wrap.hidden = !input.value;
            const pct = (score / 5) * 100;
            fill.style.width = pct + "%";
            const colors = ["#ec4f76", "#ec4f76", "#f7831b", "#ffaa3b", "#1aa67a", "#0f9bbf"];
            fill.style.background = colors[score];
            if (label) label.textContent = text;
        });
    });

    // ---------- Character counter ----------
    // Warns proportionally to the field's max length: orange at 80% used,
    // red at 95% used. This way short and long fields both get warnings
    // at the same point in the user's writing rather than at fixed offsets.
    document.querySelectorAll(".js-char-counted").forEach(function (input) {
        const targetId = input.dataset.counterTarget;
        const counter = targetId && document.getElementById(targetId);
        if (!counter) return;
        const max = parseInt(input.getAttribute("maxlength"), 10) || 0;
        function update() {
            const used = input.value.length;
            const remaining = max - used;
            const ratio = max > 0 ? used / max : 0;
            counter.textContent = remaining;
            counter.classList.toggle("char-counter--warn", ratio >= 0.8 && ratio < 0.95);
            counter.classList.toggle("char-counter--danger", ratio >= 0.95);
        }
        input.addEventListener("input", update);
        update();
    });

    // ---------- Image lightbox ----------
    const lightbox = document.querySelector(".js-lightbox");
    if (lightbox) {
        const lbImg = lightbox.querySelector(".js-lightbox-img");
        const lbCounter = lightbox.querySelector(".js-lightbox-counter");
        const btnPrev = lightbox.querySelector(".js-lightbox-prev");
        const btnNext = lightbox.querySelector(".js-lightbox-next");
        const btnClose = lightbox.querySelector(".js-lightbox-close");
        let group = [];
        let idx = 0;

        function show(i) {
            if (!group.length) return;
            idx = (i + group.length) % group.length;
            lbImg.src = group[idx];
            lbCounter.textContent = group.length > 1 ? `${idx + 1} / ${group.length}` : "";
            const multi = group.length > 1;
            btnPrev.style.visibility = multi ? "" : "hidden";
            btnNext.style.visibility = multi ? "" : "hidden";
        }

        function open(g, i) {
            group = g;
            show(i);
            lightbox.hidden = false;
            document.body.style.overflow = "hidden";
        }

        function close() {
            lightbox.hidden = true;
            document.body.style.overflow = "";
            lbImg.src = "";
            group = [];
        }

        // Click any image with `data-lightbox-group="X"` to open. All images
        // sharing the same group are treated as a gallery.
        document.body.addEventListener("click", function (ev) {
            const a = ev.target.closest("[data-lightbox-src]");
            if (!a) return;
            ev.preventDefault();
            const grp = a.dataset.lightboxGroup;
            const all = grp
                ? Array.from(document.querySelectorAll(`[data-lightbox-group="${grp}"]`))
                : [a];
            const sources = all.map(el => el.dataset.lightboxSrc);
            const startIndex = all.indexOf(a);
            open(sources, Math.max(0, startIndex));
        });

        btnPrev.addEventListener("click", () => show(idx - 1));
        btnNext.addEventListener("click", () => show(idx + 1));
        btnClose.addEventListener("click", close);
        lightbox.addEventListener("click", (ev) => {
            // Click on the dimmed backdrop, but not on the image itself.
            if (ev.target === lightbox || ev.target.classList.contains("lightbox__stage")) close();
        });
        document.addEventListener("keydown", (ev) => {
            if (lightbox.hidden) return;
            if (ev.key === "Escape") close();
            else if (ev.key === "ArrowLeft") show(idx - 1);
            else if (ev.key === "ArrowRight") show(idx + 1);
        });
    }

    // ---------- Mention autocomplete ----------
    // Listens on inputs/textarea with `data-mention="1"`. When the user types
    // an `@word`, queries the server and shows a small dropdown.
    let mentionDropdown = null;
    let mentionAnchor = null;
    let mentionToken = null;

    function ensureDropdown() {
        if (mentionDropdown) return mentionDropdown;
        mentionDropdown = document.createElement("div");
        mentionDropdown.className = "mention-dropdown";
        mentionDropdown.hidden = true;
        document.body.appendChild(mentionDropdown);
        return mentionDropdown;
    }

    function closeMentionDropdown() {
        if (mentionDropdown) mentionDropdown.hidden = true;
        mentionAnchor = null;
        mentionToken = null;
    }

    function getMentionToken(input) {
        const value = input.value;
        const pos = input.selectionStart || 0;
        // Walk backwards from cursor to find a '@' that starts a token.
        const upto = value.slice(0, pos);
        const m = /(?:^|\s)@([A-Za-z0-9_]{1,30})$/.exec(upto);
        if (!m) return null;
        return { token: m[1], start: pos - m[1].length - 1, end: pos };
    }

    async function showMentionFor(input) {
        const t = getMentionToken(input);
        if (!t || t.token.length < 1) return closeMentionDropdown();
        try {
            const res = await fetch(`/accounts/autocomplete/mentions/?q=${encodeURIComponent(t.token)}`, {
                credentials: "same-origin",
                headers: { "X-Requested-With": "XMLHttpRequest" },
            });
            if (!res.ok) return closeMentionDropdown();
            const data = await res.json();
            if (!data.results.length) return closeMentionDropdown();
            const dd = ensureDropdown();
            dd.innerHTML = data.results.map(u => `
                <button type="button" class="mention-item" data-username="${escapeAttr(u.username)}">
                    ${u.avatar_url
                        ? `<img src="${escapeAttr(u.avatar_url)}" alt="">`
                        : `<span class="mention-item__initial">${escapeAttr(u.name[0] || u.username[0])}</span>`}
                    <span class="mention-item__name"><strong>${escapeAttr(u.name)}</strong>
                        <span class="text-muted">@${escapeAttr(u.username)}</span></span>
                </button>`).join("");
            const rect = input.getBoundingClientRect();
            dd.style.left = (window.scrollX + rect.left) + "px";
            dd.style.top = (window.scrollY + rect.bottom + 4) + "px";
            dd.style.minWidth = rect.width + "px";
            dd.hidden = false;
            mentionAnchor = input;
            mentionToken = t;
        } catch (e) {
            closeMentionDropdown();
        }
    }

    function escapeAttr(s) {
        return String(s == null ? "" : s)
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;");
    }

    document.body.addEventListener("input", function (ev) {
        const el = ev.target;
        if (!el.matches('[data-mention="1"]')) return;
        showMentionFor(el);
    });

    document.body.addEventListener("click", function (ev) {
        const item = ev.target.closest(".mention-item");
        if (!item || !mentionAnchor || !mentionToken) {
            // Click outside the dropdown closes it.
            if (!ev.target.closest(".mention-dropdown")) closeMentionDropdown();
            return;
        }
        const username = item.dataset.username;
        const v = mentionAnchor.value;
        const before = v.slice(0, mentionToken.start);
        const after = v.slice(mentionToken.end);
        mentionAnchor.value = `${before}@${username} ${after}`;
        const newPos = (before + "@" + username + " ").length;
        mentionAnchor.setSelectionRange(newPos, newPos);
        mentionAnchor.focus();
        closeMentionDropdown();
    });

    document.addEventListener("keydown", function (ev) {
        if (!mentionDropdown || mentionDropdown.hidden) return;
        if (ev.key === "Escape") { closeMentionDropdown(); ev.preventDefault(); }
    });

    // ---------- Native share / copy link ----------
    document.body.addEventListener("click", async function (ev) {
        const btn = ev.target.closest(".js-share-btn");
        if (!btn) return;
        ev.preventDefault();
        const url = btn.dataset.url || location.href;
        const title = btn.dataset.title || document.title;
        const text = btn.dataset.text || "";

        if (navigator.share) {
            try { await navigator.share({ title, text, url }); return; }
            catch (e) { /* fall through to clipboard */ }
        }
        try {
            await navigator.clipboard.writeText(url);
            const orig = btn.innerHTML;
            btn.innerHTML = '<i class="bi bi-check2"></i> Copied';
            setTimeout(() => { btn.innerHTML = orig; }, 1500);
        } catch (e) {
            window.prompt("Copy this link:", url);
        }
    });

    // ---------- Heart particle burst on like ----------
    function spawnHearts(originBtn) {
        const rect = originBtn.getBoundingClientRect();
        const cx = rect.left + rect.width / 2;
        const cy = rect.top + rect.height / 2;
        for (let i = 0; i < 6; i++) {
            const h = document.createElement("span");
            h.className = "heart-particle";
            h.textContent = "♥";
            h.style.left = cx + "px";
            h.style.top = cy + "px";
            const angle = (Math.PI / 3) * (i - 2.5) + (Math.random() - 0.5) * 0.4;
            const distance = 60 + Math.random() * 40;
            h.style.setProperty("--dx", Math.cos(angle - Math.PI / 2) * distance + "px");
            h.style.setProperty("--dy", Math.sin(angle - Math.PI / 2) * distance + "px");
            h.style.fontSize = (12 + Math.random() * 8) + "px";
            document.body.appendChild(h);
            h.addEventListener("animationend", () => h.remove());
        }
    }

    document.body.addEventListener("click", function (ev) {
        const btn = ev.target.closest(".js-like-btn");
        if (!btn) return;
        // Only burst when transitioning to liked state — read the current
        // class which the optimistic handler will update synchronously.
        // Use a microtask so we read the updated state.
        queueMicrotask(() => {
            if (btn.classList.contains("post-card__action--active")) {
                spawnHearts(btn);
            }
        });
    });
})();
