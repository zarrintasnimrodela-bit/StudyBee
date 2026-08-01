(function () {
    "use strict";

    const toggle = document.querySelector("[data-menu-toggle]");
    const navigation = document.querySelector("[data-site-nav]");

    function closeMenu() {
        if (!toggle || !navigation) return;
        toggle.setAttribute("aria-expanded", "false");
        toggle.setAttribute("aria-label", "Open navigation");
        navigation.classList.remove("is-open");
    }

    if (toggle && navigation) {
        toggle.addEventListener("click", function () {
            const open = toggle.getAttribute("aria-expanded") === "true";
            toggle.setAttribute("aria-expanded", String(!open));
            toggle.setAttribute("aria-label", open ? "Open navigation" : "Close navigation");
            navigation.classList.toggle("is-open", !open);
        });

        navigation.addEventListener("click", function (event) {
            if (event.target.closest("a, button")) closeMenu();
        });

        document.addEventListener("click", function (event) {
            if (!navigation.contains(event.target) && !toggle.contains(event.target)) {
                closeMenu();
            }
        });
    }

    document.querySelectorAll("[data-message-dismiss]").forEach(function (button) {
        button.addEventListener("click", function () {
            const message = button.closest(".site-message");
            if (message) message.remove();
        });
    });

    const modals = new Map();
    document.querySelectorAll("[data-modal]").forEach(function (modal) {
        modals.set(modal.dataset.modal, modal);
    });

    let activeModal = null;
    let previousFocus = null;

    function focusableElements(modal) {
        return Array.from(
            modal.querySelectorAll(
                "a[href], button:not([disabled]), input:not([disabled]):not([type='hidden']), " +
                "select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex='-1'])"
            )
        ).filter(function (element) {
            return !element.hidden && element.offsetParent !== null;
        });
    }

    function openModal(name, trigger) {
        const modal = modals.get(name);
        if (!modal) return false;

        if (activeModal && activeModal !== modal) {
            closeModal(activeModal, false);
        }

        previousFocus = trigger || document.activeElement;
        modal.hidden = false;
        modal.setAttribute("aria-hidden", "false");
        modal.classList.add("is-open");
        document.body.classList.add("modal-open");
        activeModal = modal;

        window.requestAnimationFrame(function () {
            const focusTarget = modal.querySelector("[autofocus]") || focusableElements(modal)[0];
            if (focusTarget) focusTarget.focus();
        });
        return true;
    }

    function closeModal(modal, restoreFocus) {
        const target = modal || activeModal;
        if (!target) return;

        target.classList.remove("is-open");
        target.setAttribute("aria-hidden", "true");
        target.hidden = true;
        document.body.classList.remove("modal-open");

        if (activeModal === target) activeModal = null;
        if (restoreFocus !== false && previousFocus && typeof previousFocus.focus === "function") {
            previousFocus.focus();
        }
    }

    function getNextFromTrigger(trigger) {
        if (trigger && trigger.dataset.authNext) return trigger.dataset.authNext;
        if (trigger && trigger.href) {
            try {
                const url = new URL(trigger.href, window.location.href);
                return url.searchParams.get("next") || window.location.pathname + window.location.search;
            } catch (_error) {
                return window.location.pathname + window.location.search;
            }
        }
        return window.location.pathname + window.location.search;
    }

    function setAuthNext(nextValue) {
        document.querySelectorAll("[data-auth-next-input]").forEach(function (input) {
            input.value = nextValue || "/";
        });
    }

    function showAuthPanel(name) {
        const requested = name === "1" ? "login" : (name || "login");
        const panels = Array.from(document.querySelectorAll("[data-auth-panel]"));
        if (!panels.length) return;
        const available = panels.some(function (panel) {
            return panel.dataset.authPanel === requested;
        });
        const targetName = available ? requested : "login";

        panels.forEach(function (panel) {
            panel.hidden = panel.dataset.authPanel !== targetName;
        });
        document.querySelectorAll("[data-auth-show='login'], [data-auth-show='signup']").forEach(function (button) {
            const active = button.dataset.authShow === targetName;
            if (button.closest(".auth-mode-tabs")) {
                button.classList.toggle("is-active", active);
                button.setAttribute("aria-selected", String(active));
            }
        });
        document.querySelectorAll("[data-auth-errors]").forEach(function (errors) {
            renderErrors(errors, null, "");
        });
        window.requestAnimationFrame(function () {
            const panel = document.querySelector(`[data-auth-panel='${targetName}']`);
            const firstInput = panel ? panel.querySelector("input:not([type='hidden'])") : null;
            if (firstInput) firstInput.focus();
        });
    }

    function prepareReportModal(trigger) {
        const modal = modals.get("report");
        if (!modal) return;

        const formPanel = modal.querySelector("[data-report-form-panel]");
        const successPanel = modal.querySelector("[data-report-success]");
        const form = modal.querySelector("[data-report-form]");
        const errors = modal.querySelector("[data-report-errors]");
        const context = modal.querySelector("[data-report-context]");
        const resourceInput = modal.querySelector("[data-report-resource]");
        const courseInput = modal.querySelector("[data-report-course]");
        const titleInput = modal.querySelector("[data-report-title]");
        const nextInput = modal.querySelector("[data-report-next]");

        if (formPanel) formPanel.hidden = false;
        if (successPanel) successPanel.hidden = true;
        if (errors) errors.replaceChildren();
        if (form) {
            form.reset();
            const signedInEmail = form.querySelector("#reportEmail[readonly]");
            if (signedInEmail) signedInEmail.value = signedInEmail.defaultValue;
        }

        let resourceId = trigger ? trigger.dataset.reportResource || "" : "";
        let courseCode = trigger ? trigger.dataset.reportCourse || "" : "";
        let resourceTitle = trigger ? trigger.dataset.reportTitle || "" : "";
        let nextValue = window.location.pathname + window.location.search;

        if (trigger && trigger.href) {
            try {
                const url = new URL(trigger.href, window.location.href);
                resourceId = resourceId || url.searchParams.get("resource") || "";
                nextValue = url.searchParams.get("next") || nextValue;
            } catch (_error) {
                // Keep safe local defaults.
            }
        }

        if (resourceInput) resourceInput.value = resourceId;
        if (courseInput) courseInput.value = courseCode;
        if (titleInput) titleInput.value = resourceTitle;
        if (nextInput) nextInput.value = nextValue;

        if (context) {
            context.textContent = resourceTitle
                ? `Reporting: ${courseCode ? courseCode + " — " : ""}${resourceTitle}`
                : "Tell us about a broken link, wrong resource, removal request, or another problem.";
        }
    }

    document.addEventListener("click", function (event) {
        const opener = event.target.closest("[data-modal-open]");
        if (opener) {
            const name = opener.dataset.modalOpen;
            if (modals.has(name)) {
                event.preventDefault();
                closeMenu();
                if (name === "auth") {
                    setAuthNext(getNextFromTrigger(opener));
                    showAuthPanel(opener.dataset.authMode || "login");
                }
                if (name === "report") prepareReportModal(opener);
                openModal(name, opener);
            }
            return;
        }

        const closer = event.target.closest("[data-modal-close]");
        if (closer) {
            event.preventDefault();
            closeModal(closer.closest("[data-modal]"));
        }
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape") {
            closeMenu();
            if (activeModal) closeModal(activeModal);
            return;
        }

        if (event.key === "Tab" && activeModal) {
            const items = focusableElements(activeModal);
            if (!items.length) return;
            const first = items[0];
            const last = items[items.length - 1];
            if (event.shiftKey && document.activeElement === first) {
                event.preventDefault();
                last.focus();
            } else if (!event.shiftKey && document.activeElement === last) {
                event.preventDefault();
                first.focus();
            }
        }
    });

    function setButtonBusy(button, busy, busyText) {
        if (!button) return;
        if (busy) {
            button.dataset.originalText = button.textContent;
            button.disabled = true;
            button.textContent = busyText;
        } else {
            button.disabled = false;
            button.textContent = button.dataset.originalText || button.textContent;
        }
    }

    function renderErrors(container, errors, fallback) {
        if (!container) return;
        container.replaceChildren();

        const messages = [];
        if (errors && typeof errors === "object") {
            Object.keys(errors).forEach(function (field) {
                const fieldMessages = Array.isArray(errors[field]) ? errors[field] : [errors[field]];
                fieldMessages.forEach(function (message) {
                    if (message) messages.push(String(message));
                });
            });
        }
        if (!messages.length && fallback) messages.push(fallback);

        messages.forEach(function (message) {
            const paragraph = document.createElement("p");
            paragraph.textContent = message;
            container.appendChild(paragraph);
        });
    }

    async function postForm(form) {
        const response = await fetch(form.action, {
            method: "POST",
            body: new FormData(form),
            headers: {"X-Requested-With": "XMLHttpRequest"},
            credentials: "same-origin"
        });
        let payload;
        try {
            payload = await response.json();
        } catch (_error) {
            payload = {ok: false, message: "StudyBee could not process the request."};
        }
        return {response: response, payload: payload};
    }

    document.querySelectorAll("[data-auth-show]").forEach(function (button) {
        button.addEventListener("click", function () {
            showAuthPanel(button.dataset.authShow);
        });
    });

    document.querySelectorAll("[data-password-toggle]").forEach(function (button) {
        button.addEventListener("click", function () {
            const wrapper = button.closest(".password-field-wrap");
            const input = wrapper ? wrapper.querySelector("input") : null;
            if (!input) return;
            const reveal = input.type === "password";
            input.type = reveal ? "text" : "password";
            button.textContent = reveal ? "Hide" : "Show";
            button.setAttribute("aria-label", reveal ? "Hide password" : "Show password");
        });
    });

    function wireAuthForm(selector, options) {
        const form = document.querySelector(selector);
        if (!form) return;
        form.addEventListener("submit", async function (event) {
            event.preventDefault();
            const button = form.querySelector("button[type='submit']");
            const errors = document.querySelector(`[data-auth-errors='${options.errorKey}']`);
            setButtonBusy(button, true, options.busyText);
            renderErrors(errors, null, "");

            try {
                const result = await postForm(form);
                if (!result.response.ok || !result.payload.ok) {
                    renderErrors(
                        errors,
                        result.payload.errors,
                        result.payload.message || options.failureText
                    );
                    return;
                }

                if (options.emailDisplay && result.payload.email) {
                    document.querySelectorAll(options.emailDisplay).forEach(function (element) {
                        element.textContent = result.payload.email;
                    });
                }
                if (options.nextPanel) {
                    showAuthPanel(options.nextPanel);
                    return;
                }
                window.location.assign(result.payload.redirect || "/");
            } catch (_error) {
                renderErrors(errors, null, options.connectionText);
            } finally {
                setButtonBusy(button, false);
            }
        });
    }

    wireAuthForm("[data-auth-login-form]", {
        errorKey: "login",
        busyText: "Logging in…",
        failureText: "The email or password could not be verified.",
        connectionText: "Login failed. Check your connection and try again."
    });
    wireAuthForm("[data-auth-signup-request-form]", {
        errorKey: "signup",
        busyText: "Sending code…",
        failureText: "The sign-up code could not be sent.",
        connectionText: "The sign-up code could not be sent. Check your connection and try again.",
        emailDisplay: "[data-signup-email-display]",
        nextPanel: "signup-complete"
    });
    wireAuthForm("[data-auth-signup-complete-form]", {
        errorKey: "signup-complete",
        busyText: "Creating account…",
        failureText: "The account could not be created.",
        connectionText: "The account could not be created. Check your connection and try again."
    });
    wireAuthForm("[data-auth-reset-request-form]", {
        errorKey: "reset",
        busyText: "Sending code…",
        failureText: "The reset code could not be sent.",
        connectionText: "The reset code could not be sent. Check your connection and try again.",
        emailDisplay: "[data-reset-email-display]",
        nextPanel: "reset-complete"
    });
    wireAuthForm("[data-auth-reset-complete-form]", {
        errorKey: "reset-complete",
        busyText: "Saving password…",
        failureText: "The password could not be reset.",
        connectionText: "The password could not be reset. Check your connection and try again."
    });

    const reportForm = document.querySelector("[data-report-form]");
    if (reportForm) {
        reportForm.addEventListener("submit", async function (event) {
            event.preventDefault();
            const button = reportForm.querySelector("button[type='submit']");
            const errors = document.querySelector("[data-report-errors]");
            setButtonBusy(button, true, "Submitting…");
            renderErrors(errors, null, "");

            try {
                const result = await postForm(reportForm);
                if (!result.response.ok || !result.payload.ok) {
                    renderErrors(errors, result.payload.errors, result.payload.message || "The report could not be submitted.");
                    return;
                }

                const modal = modals.get("report");
                if (modal) {
                    const formPanel = modal.querySelector("[data-report-form-panel]");
                    const successPanel = modal.querySelector("[data-report-success]");
                    const reference = modal.querySelector("[data-report-reference]");
                    if (formPanel) formPanel.hidden = true;
                    if (successPanel) successPanel.hidden = false;
                    if (reference) reference.textContent = result.payload.reference || "submitted";
                    const doneButton = successPanel ? successPanel.querySelector("button") : null;
                    if (doneButton) doneButton.focus();
                }
            } catch (_error) {
                renderErrors(errors, null, "The report could not be submitted. Check your connection and try again.");
            } finally {
                setButtonBusy(button, false);
            }
        });
    }

    const filterToggle = document.querySelector("[data-filter-toggle]");
    const filterSidebar = document.querySelector("[data-filter-sidebar]");
    if (filterToggle && filterSidebar) {
        filterToggle.addEventListener("click", function () {
            const open = filterToggle.getAttribute("aria-expanded") === "true";
            filterToggle.setAttribute("aria-expanded", String(!open));
            filterSidebar.classList.toggle("is-open", !open);
            const label = filterToggle.querySelector("[data-filter-label]");
            if (label) label.textContent = open ? "Show filters" : "Hide filters";
        });
    }

    document.querySelectorAll("input[type='file']").forEach(function (input) {
        input.addEventListener("change", function () {
            const field = input.closest(".report-field");
            if (!field) return;
            let summary = field.querySelector(".file-selection-summary");
            if (!summary) {
                summary = document.createElement("div");
                summary.className = "file-selection-summary field-hint";
                field.appendChild(summary);
            }
            summary.textContent = input.files && input.files.length
                ? `Selected: ${input.files[0].name}`
                : "No file selected";
        });
    });

    const query = new URLSearchParams(window.location.search);
    if (query.get("auth") && modals.has("auth")) {
        setAuthNext(query.get("next") || "/");
        showAuthPanel(query.get("auth") || "login");
        openModal("auth", null);
        query.delete("auth");
        query.delete("next");
        const cleanQuery = query.toString();
        window.history.replaceState(
            {},
            document.title,
            window.location.pathname + (cleanQuery ? `?${cleanQuery}` : "") + window.location.hash
        );
    }
})();

(function () {
    const submissionForm = document.querySelector("[data-submission-form]");
    if (!submissionForm) return;

    const category = submissionForm.querySelector("#id_category");
    const questionType = submissionForm.querySelector("#id_question_type");
    const questionSection = submissionForm.querySelector("[data-question-section]");
    const solutionFields = questionSection
        ? questionSection.querySelectorAll("input, select, textarea")
        : [];

    function syncQuestionFields() {
        const isQuestion = category && category.value === "QUESTION";
        if (questionSection) questionSection.hidden = !isQuestion;
        if (questionType) {
            questionType.disabled = !isQuestion;
            if (!isQuestion) questionType.value = "";
        }
        solutionFields.forEach(function (field) {
            field.disabled = !isQuestion;
            if (!isQuestion) field.value = "";
        });
    }

    if (category) {
        category.addEventListener("change", syncQuestionFields);
        syncQuestionFields();
    }

    submissionForm.addEventListener("submit", function () {
        const button = submissionForm.querySelector("button[type='submit']");
        if (!button || button.disabled) return;
        button.disabled = true;
        button.dataset.originalText = button.textContent;
        button.textContent = "Submitting…";
    });
})();
